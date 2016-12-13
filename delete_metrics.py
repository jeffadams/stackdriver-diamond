#!/usr/bin/env python

'''
Quick utility script to delete custom metrics.
'''

from google.cloud import monitoring, exceptions
import sys

# To use a service account with credentials from a json file:
JSON_CREDS = './creds.json'
from oauth2client.service_account import ServiceAccountCredentials
scopes  = ["https://www.googleapis.com/auth/monitoring",]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    JSON_CREDS, scopes)

'''
# From inside a GCE instance, using the default instance credentials:
from oauth2client.contrib.gce import AppAssertionCredentials
credentials = AppAssertionCredentials([])
'''

# 'myproject' is the GCE connector project ID.
myproject = 'main-shade-732' 
client = monitoring.Client(project=myproject, credentials=credentials)

try:
    prefix = 'custom.googleapis.com' + '/' + sys.argv[1]
except IndexError:
    r = raw_input("Delete ALL custom metrics from %s? (y/n)" % myproject)
    if r.lower() != 'y':
        sys.exit(1)    
    prefix = 'custom.googleapis.com'

all = client.list_metric_descriptors(type_prefix=prefix)
for a in all:
    descriptor = client.metric_descriptor(str(a.type))
    print("deleting %s" % a.type)
    try:
        descriptor.delete()
    except exceptions.InternalServerError:
        next
