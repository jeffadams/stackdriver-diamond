from configobj import Section
import datetime
from Handler import Handler
from pprint import pprint
from google.cloud import monitoring
from oauth2client.contrib.gce import AppAssertionCredentials

class stackdriverHandler(Handler):
    def __init__(self, config=None):
        """
          Create a new instance of class stackdriverHandler
        """
        Handler.__init__(self, config)
    def process(self, metric):
        collector = str(metric.getCollectorPath())
        metricname = str(metric.getMetricPath())
        metricvalue = float(metric.value)
        timestamp = datetime.datetime.fromtimestamp(metric.timestamp)

        credentials = AppAssertionCredentials([])
        client = monitoring.Client(project='main-shade-732', credentials=credentials)

        resource = client.resource('gce_instance', labels={
            'instance_id': '8722387387098324245',
            'zone': 'us-east1-b',
        })
        metric_descriptor = 'custom.googleapis.com' + '/' + 'my_app' + '/' + collector + '/' + metricname
        metric = client.metric(metric_descriptor, labels={
            'status': 'successful',
        })

        client.write_point(metric=metric, resource=resource,
            value=metricvalue, )
