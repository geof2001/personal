#!/usr/bin/python

import json
import yaml
import ast
import boto3
import botocore
import argparse
import time
import pprint
import distutils.util
try:
    from jinja2 import Environment, FileSystemLoader, Template
except ImportError:
    exit('Please install the jinja2 module. Try \'pip install Jinja2\'.')

# Argument Parser Configuration
parser = argparse.ArgumentParser(description='Jinja2 Python for Deployment')
parser.add_argument('--service', metavar='', help=' ServiceStack name', required=True)
parser.add_argument('-s', '--stack_name', metavar='', required=True, help='Stack Name')
parser.add_argument('-r', '--region', metavar='', help='AWS Region', required=True)
parser.add_argument('-p', '--profile', metavar='', help=' AWS Account Number', required=True)
parser.add_argument('-t', '--previous_template', help='Prev Template?', default=False, type=distutils.util.strtobool)
parser.add_argument('-b', '--buildnum', help='Build Number', default='', metavar='')
parser.add_argument('-g', '--git_repo', metavar='', help='name of the git repository', required=True)
parser.add_argument('--changeset', default=False, type=distutils.util.strtobool, help='If true, create a change set')
args = parser.parse_args()

if args.changeset and not args.buildnum:
    exit('The build number flag is required if the changeset flag is set to true.')

# Accounts Map
accounts = {"638782101961": "dev",
            "181133766305": "qa",
            "886239521314": "prod",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-prod": "prod"}

# Setup boto3 default configurations
boto3.setup_default_session(profile_name=args.profile, region_name=args.region)

# Define templates used for S3/CF during deployment
service_template = '%s.stack.yaml' % args.service
parameters_template = '%s.params.json' % args.service
service_config = '%s.config.yaml' % args.service
repo_config = '%s.config.yaml' % args.git_repo

tempEnv = Environment(loader=FileSystemLoader('./'))

with open("config.yaml") as config_file:
    config_data = yaml.load(config_file)

try:
    with open(service_config) as service_config_file:
        service_config_data = yaml.load(service_config_file)

    config_data.update(service_config_data)
except:
    print "no service config file"

if ( repo_config != service_config):
    try:
        with open(repo_config) as repo_config_file:
            repo_config_data = yaml.load(repo_config_file)

        config_data.update(repo_config_data)
    except:
        print "no repo config file"

print "Config data:"
pprint.pprint(config_data)
template = tempEnv.get_template(parameters_template)

params_list = ast.literal_eval(
    str(template.render(config_data, region=args.region, profile=args.profile, accounts=accounts)))

for index, dic in enumerate(params_list):
    if 'UsePreviousValue' in dic and dic['UsePreviousValue'] != '':
        params_list[index]['UsePreviousValue'] = bool(distutils.util.strtobool(params_list[index]['UsePreviousValue']))

print 'PARAMS_LIST:'
print params_list

s3 = boto3.client('s3')

# Create AWS S3 Bucket For Templates
if args.region == 'us-east-1':
    try:
        print 'Creating AWS S3 buckets for Template...'
        s3.create_bucket(Bucket='cf-clusters-%s-%s' % (args.profile, args.region))
    except botocore.exceptions.ClientError:
        print 'Unable to create AWS S3 buckets for Template...'

if args.region != 'us-east-1':
    try:
        print 'Creating AWS S3 buckets for Template...'
        s3.create_bucket(Bucket='cf-clusters-%s-%s' % (args.profile, args.region),
                         CreateBucketConfiguration={'LocationConstraint': '%s' % args.region})
    except botocore.exceptions.ClientError:
        print 'Unable to create AWS S3 buckets for Template...'

# Upload CF Template to AWS S3 Bucket
try:
    s3.upload_file(service_template, 'cf-clusters-%s-%s' % (args.profile, args.region), '%s.yaml' % args.stack_name)
except botocore.exceptions.ClientError:
    print 'Unable to upload CloudFormation Template to AWS S3 Bucket...'

cf = boto3.client('cloudformation')

# Check if CF stack exists
stack_exists = False
try:
    print 'Checking if CloudFormation stack exists...'
    stack_events = cf.describe_stacks(StackName=args.stack_name)
    stack_exists = True
except botocore.exceptions.ClientError:
    print 'The stack does not exist and will be created...'

# Create stack if it doesn't exist
if not stack_exists:
    if service_template:
        try:
            print 'Creating Cloudformation stack...'
            stack_created = cf.create_stack(StackName=args.stack_name,
                                            Capabilities=['CAPABILITY_NAMED_IAM'],
                                            Parameters=params_list,
                                            TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                        (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Unable to create AWS Cloudformation stack...'
            print e.response['Error']['Message']
            exit(1)
    else:
        try:
            print 'Creating CloudFormation stack...'
            stack_created = cf.create_stack(StackName=args.stack_name,
                                            Capabilities=['CAPABILITY_NAMED_IAM'],
                                            TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                        (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Unable to create AWS Cloudformation stack...'
            print e.response['Error']['Message']
            exit(1)

# Update existing CF stack
if stack_exists and not args.changeset:
    if service_template:
        try:
            print 'Updating the existing Cloudformation stack...'
            if args.previous_template:
                stack_updated = cf.update_stack(StackName=args.stack_name,
                                                Capabilities=['CAPABILITY_NAMED_IAM'],
                                                Parameters=params_list,
                                                UsePreviousTemplate=True)
            else:
                stack_updated = cf.update_stack(StackName=args.stack_name,
                                                Capabilities=['CAPABILITY_NAMED_IAM'],
                                                Parameters=params_list,
                                                TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                            (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Cloudformation stack update could not be performed...'
            print e.response['Error']['Message']
            exit(1)
    else:
        try:
            print 'Updating the existing Cloudformation stack...'
            if args.previous_template:
                stack_updated = cf.update_stack(StackName=args.stack_name,
                                                Capabilities=['CAPABILITY_NAMED_IAM'],
                                                UsePreviousTemplate=True)
            else:
                stack_updated = cf.update_stack(StackName=args.stack_name,
                                                Capabilities=['CAPABILITY_NAMED_IAM'],
                                                TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                             (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Cloudformation stack update could not be performed...'
            print e.response['Error']['Message']
            exit(1)

# Create changeset for existing CF stack
changeset_created = ''
if stack_exists and args.changeset:
    if service_template:
        try:
            print 'Creating change set for the existing Cloudformation stack...'
            if args.previous_template:
                changeset_created = cf.create_change_set(StackName=args.stack_name,
                                                         ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum),
                                                         Capabilities=['CAPABILITY_NAMED_IAM'],
                                                         Parameters=params_list,
                                                         UsePreviousTemplate=True)
            else:
                changeset_created = cf.create_change_set(StackName=args.stack_name,
                                                         ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum),
                                                         Capabilities=['CAPABILITY_NAMED_IAM'],
                                                         Parameters=params_list,
                                                         TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                                     (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Stack changeset update could not be performed...'
            print e.response['Error']['Message']
            exit(1)

    else:
        try:
            print 'Creating change set for the existing Cloudformation stack...'
            if args.previous_template:
                changeset_created = cf.create_change_set(StackName=args.stack_name,
                                                         ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum),
                                                         Capabilities=['CAPABILITY_NAMED_IAM'],
                                                         UsePreviousTemplate=True)
            else:
                changeset_created = cf.create_change_set(StackName=args.stack_name,
                                                         ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum),
                                                         Capabilities=['CAPABILITY_NAMED_IAM'],
                                                         TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml' %
                                                                     (args.profile, args.region, args.stack_name))
        except botocore.exceptions.ClientError as e:
            print 'Stack changeset update could not be performed...'
            print e.response['Error']['Message']
            exit(1)

# Get/display change set information
if changeset_created:
    try:
        changeset_check = cf.describe_change_set(StackName=args.stack_name,
                                                 ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum))
        retries = 0

        while changeset_check['Status'] != 'CREATE_COMPLETE' and 'FAILED' not in changeset_check['Status'] and retries < 60:
            time.sleep(3)
            retries += 1
            print 'Changeset creation is still in progress... (Retrying - #%d)' % retries
            changeset_check = cf.describe_change_set(StackName=args.stack_name,
                                                     ChangeSetName='%s-build-%s' % (args.stack_name, args.buildnum))
        if 'FAILED' in changeset_check['Status']:
            print 'Changeset creation failed...'
            print changeset_check['Status'], '-', changeset_check['StatusReason']
        else:
            print '-----------------------------------------------------------'
            print '              === Change Set Changes ==='
            print '-----------------------------------------------------------'
            pprint.PrettyPrinter(indent=2).pprint(changeset_check)
    except botocore.exceptions.ClientError:
        print 'Unable to gather stack change set information...'
