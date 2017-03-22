# coding=utf-8
'''
Send metrics from AWS to the Google Stackdriver custom metrics API. 

Requires google-cloud

Sample configuration:

[[StackdriverHandler]]
group   = MyApp
version = 1
LABEL_app = www
LABEL_env = prod

Additional metric labels 'instanceType' and 'vpc_id' will
be created from the instance metadata by default. 

The sample config would produce the metric:

MyApp.1/loadavg/05

with the metric labels:

app : www
env : prd
instanceType: <instanceType>
vpc_id: <vpc_id>

The 'version' config item is required and must be changed if you add a new label. 
Metric labels are immutable, and
delete operations can take some time.
If you add/change a label without changing the version, 
the agent will not be able to write metrics. 

This handler supports the creation of labels from instance tags, with the caveat that you must
change the metric version number and restart the agent at the same time that you add new tags. 
To use instance tags as metric labels: 

use_tags = True

pacetownsley@gmail.com

'''
import datetime
import json
import urllib2
import socket

from configobj import Section
from google.cloud import monitoring, exceptions
from Handler import Handler

class StackdriverHandler(Handler):
    def __init__(self, config=None):
        """
          Create a new instance of class StackdriverHandler
        """
        Handler.__init__(self, config)
        self.aws_url = 'http://169.254.169.254/latest/'
        self.resource_type = 'aws_ec2_instance'
        self.resource_labels, self.metric_labels = self.get_labels()        
        self.client = self.make_client() 
        if self.config['group'] and self.config['version']:
            self.group  = self.config['group'] + '.' + self.config['version']
   
    def get_default_config(self):
        """
        Return the default config.
        """
        config = super(StackdriverHandler, self).get_default_config()

        config.update({
            'credential_file': '/etc/google/auth/application_default_credentials.json ',
            'group' : '',
            'version': '',
            'use_tags': False,
        })
        return config
  
    def get_labels(self):
        resource_labels, instanceType, region = self.get_instance_document()
        metric_labels = self.get_metric_labels(
            region=region,  
            instance_id=resource_labels['instance_id']
            ) 
        metric_labels['vpc_id'] = self.get_vpc()
        metric_labels['instanceType'] = instanceType
        return resource_labels, metric_labels 

    def get_instance_document(self):
        document = json.loads(self.metadata_request(url=self.aws_url + '/dynamic/instance-identity/document'))
        resource_labels = {
            'instance_id': document['instanceId'],
            'region': 'aws' + ':' + document['region'],
            'aws_account': document['accountId'],
        }
        instanceType = document['instanceType']
        region = document['region']
        return resource_labels, instanceType, region

    def get_metric_labels(self,region='', instance_id=''):
        metric_labels = {}
        if self.config['use_tags']:
            import boto.ec2
            conn = boto.ec2.connect_to_region(region)
            #TODO: Check for AttributeError on this call to indicate credential problems.
            reservations = conn.get_all_instances(instance_ids=instance_id)
            instance = reservations[0].instances[0]
        
            for k, v in instance.tags.iteritems():
                value = v.replace('_', '')
                metric_labels[k] = value
        else:
            for k, v in self.config.iteritems():
                if 'LABEL_' in k:
                    metric_labels[k.replace('LABEL_', '')] = v
            for i in metric_labels:
                self.log.info("Using label: %s" % i)
        return metric_labels
       
 
    def get_vpc(self,):
        my_mac = self.metadata_request(url=self.aws_url + '/meta-data/network/interfaces/macs/')
        vpc_id = self.metadata_request(url=self.aws_url + '/meta-data/network/interfaces/macs/' + my_mac + '/' + 'vpc-id'
        )
        return vpc_id


    def make_client(self):
        if self.config['credential_file']:
            try:
                with open(self.config['credential_file'], 'r') as cfile:
                    credentials = json.load(cfile)
                    monitoring_client = monitoring.Client.from_service_account_json(
                        self.config['credential_file'], 
                        project=credentials['project_id'],
                        )
            except IOError, e:
                self.log.error("ERROR: %s" % e)
        else:
            credentials = AppAssertionCredentials([])
            client = monitoring.Client(credentials=self.credentials)
        return monitoring_client
 
    def metadata_request(self, url="", headers=''):
        try:
            request = urllib2.Request(url, headers)
            metadata  = urllib2.urlopen(request, timeout=1)
            return metadata.read()
        except urllib2.URLError as e:
            self.log.error(e)
            return None

    def process(self, metric):
        collector   = str(metric.getCollectorPath())
        metricname  = str(metric.getMetricPath())
        metricvalue = float(metric.value)
        metrictype  = str(metric.metric_type)
        timestamp   = datetime.datetime.fromtimestamp(metric.timestamp)
        retry_with_old_labels = False
        
        if self.group:
            resource_descriptor = 'custom.googleapis.com' + '/' + self.group + '/' + collector + '/' + metricname
        else:
            resource_descriptor = 'custom.googleapis.com' + '/' +  collector + '/' + metricname
        self.log.info(resource_descriptor)
        
        resource = self.client.resource(self.resource_type, self.resource_labels)
        metric   = self.client.metric(resource_descriptor, self.metric_labels,)
        self.log.debug("Processing %s" % resource_descriptor) 
        self.client.write_point(resource=resource, metric=metric, value=metricvalue,)
