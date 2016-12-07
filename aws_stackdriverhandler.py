import datetime
import json
import urllib2
import socket

import boto.ec2
import boto.utils
from configobj import Section
from google.cloud import monitoring, exceptions
from Handler import Handler
from oauth2client.contrib.gce import AppAssertionCredentials

HOSTNAME = socket.gethostname()

class StackdriverHandler(Handler):
    def __init__(self, config=None):
        """
          Create a new instance of class StackdriverHandler
        """
        Handler.__init__(self, config)
        self.client = self.make_client() 
        self.type = 'aws_ec2_instance'

        self.resource_labels, self.metric_labels = self.get_aws_meta()
        for k,v in self.resource_labels.iteritems():
            print("Resource: %s %s" % (k,v))
        for k,v in self.metric_labels.iteritems():
            print("Metric: %s %s" % (k,v))
           
    def make_client(self):
        if self.config['credential_file']:
            try:
                with open(self.config['credential_file'], 'r') as cfile:
                    credentials = json.load(cfile)
                    client = monitoring.Client.from_service_account_json(
                    self.config['credential_file'], project=credentials['project_id'],
                    )
            except IOError as e:
                self.log.error("ERROR: %s" % e)
        else:
            credentials = AppAssertionCredentials([])
            client = monitoring.Client(credentials=self.credentials)
        return client
 
    def metadata_request(self, url="", headers=''):
        try:
            request = urllib2.Request(url, headers)
            metadata  = urllib2.urlopen(request, timeout=1)
            return metadata.read()
        except urllib2.URLError as e:
            print e
            return None

    def process(self, metric):
        collector = str(metric.getCollectorPath())
        metricname = str(metric.getMetricPath())
        metricvalue = float(metric.value)
        metric_kind = 'gauge'
        timestamp = datetime.datetime.fromtimestamp(metric.timestamp)
        
        resource = self.client.resource(self.type, self.resource_labels)
        resource_descriptor = 'custom.googleapis.com' + '/' +  collector + '/' + metricname
        metric = self.client.metric(resource_descriptor, self.metric_labels, )
        
        self.log.info(str(metric))
        try:
            self.client.write_point(metric=metric, resource=resource, value=metricvalue, )
        except exceptions.BadRequest:
            descriptor = self.client.metric_descriptor(
                resource_descriptor,
                metric_kind='GAUGE',
                value_type='DOUBLE',
            )
            descriptor.create()
            self.log.info("Created %s" % resource_descriptor)


    def get_vpc(self,):
        mac_url = 'http://169.254.169.254/latest/meta-data/network/interfaces/macs/'
        my_mac = self.metadata_request(url=mac_url)
        vpc_id = self.metadata_request(url=mac_url + my_mac + '/' + 'vpc-id')
        return vpc_id

    def get_aws_meta(self,):
        document_url = 'http://169.254.169.254/latest/dynamic/instance-identity/document'
        document = json.loads(self.metadata_request(url=document_url))
        resource_labels = {
            'instance_id': document['instanceId'],
            'region': 'aws' + ':' + document['region'],
            'aws_account': document['accountId'],
        }
        tags = boto.utils.get_instance_metadata()
        conn = boto.ec2.connect_to_region(document['region'])
        reservations = conn.get_all_instances(instance_ids=document['instanceId'])
        instance = reservations[0].instances[0]

        metric_labels = {}
        for k, v in instance.tags.iteritems():
            k = k.encode('utf-8')       
            v = v.encode('utf-8')       
            metric_labels[k] = v
        metric_labels['vpc_id'] = self.get_vpc()
        metric_labels['instanceType'] = document['instanceType']
        return resource_labels, metric_labels
