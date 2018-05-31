#!/usr/bin/python
import argparse
import boto3

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Service Tool')
PARSER.add_argument('service', metavar='', default=None, help='Service Name')
args = PARSER.parse_args()

boto3.setup_default_session(profile_name='661796028321', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb')
services_table = dynamodb.Table('ServiceInfo')
service = services_table.get_item(Key={'serviceName': args.service})
try:
    stack_path = service['Item']['serviceInfo']['deploy']['params']['stack_file']
    print stack_path
except:
    print 'The service may not exist in the ServiceInfo table, or the stack path does not exist...'

