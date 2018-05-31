#!/usr/bin/python
import os
import yaml
import json
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
parser.add_argument('-n', '--name', metavar='', required=True, help='Name of the service from ServiceInfo')
parser.add_argument('-s', '--stack_name', metavar='', required=True, help='Stack Name')
parser.add_argument('-r', '--region', metavar='', help='AWS Region', required=True)
parser.add_argument('-p', '--profile', metavar='', help=' AWS Account Number', required=True)
parser.add_argument('-t', '--previous_template', help='Prev Template?', default=False, type=distutils.util.strtobool)
parser.add_argument('-b', '--buildnum', help='Build Number', default='', metavar='')
parser.add_argument('-g', '--git_repo', metavar='', help='name of the git repository', required=True)
parser.add_argument('-v', '--version', metavar='', help='version of deploy image', required=True)
parser.add_argument('--changeset', default=False, type=distutils.util.strtobool, help='If true, create a change set')
args = parser.parse_args()

if args.changeset and not args.buildnum:
    exit('The build number flag is required if the changeset flag is set to true.')

# Boolean to check if build job was the s3_copy_script_job for content-redis, recsys-emr-job, or recsys-wiki-extractor
s3_copy_script_job = False
recsys_emr_job = False
if 'jenkins' in args.version:
    args.version = args.version.split(':')[1]
    s3_copy_script_job = True
elif 'recsys-emr-jar' in args.version:
    args.version = args.version.split(':', 1)[1]
    recsys_emr_job = True
elif 'recsys-wikipedia-extractor-batch' in args.version:
    args.version = args.version.replace('-batch', '')

# Accounts Map
accounts = {"638782101961": "dev",
            "181133766305": "qa",
            "886239521314": "prod",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-prod": "prod"}

# Get info from ServiceInfo table
boto3.setup_default_session(profile_name='661796028321', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb')
services_table = dynamodb.Table('ServiceInfo')
service = services_table.get_item(Key={'serviceName': args.name})

# Setup boto3 default configurations
boto3.setup_default_session(profile_name=args.profile, region_name=args.region)

# Define templates used for S3/CF during deployment
service_template = '%s.stack.yaml' % args.service
parameters_template = '%s.params.json' % args.service
service_config = '%s.config.yaml' % args.service
repo_config = '%s.config.yaml' % args.git_repo

# Additional files to update to S3 if any
additional_templates = []
for filename in os.listdir('.'):
    if filename.endswith('.yaml') and args.service in filename and 'template' in filename:
        additional_templates.append(filename)

print service_template
print parameters_template
print service_config
print repo_config
print additional_templates

tempEnv = Environment(loader=FileSystemLoader('./'))

# Add docker image to config (config.yaml replacement)
config_data = {}
try:
    with open(service_config) as service_config_file:
        service_config_data = yaml.load(service_config_file)

    config_data.update(service_config_data)
except:
    print "no service config file"

if repo_config != service_config:
    try:
        with open(repo_config) as repo_config_file:
            repo_config_data = yaml.load(repo_config_file)

        config_data.update(repo_config_data)
    except:
        print "no repo config file"

print "Config data:"
pprint.pprint(config_data)

other_images = service['Item']['serviceInfo']['deploy']['other_images'] \
    if 'other_images' in service['Item']['serviceInfo']['deploy'] else ''

print 'Other images: {}'.format(other_images)

# Check servince info file to see if other images are required
other_images_list = []
if other_images:
    cf = boto3.client('cloudformation')
    stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
    stack_description = cf.describe_stacks(StackName=stack_name)
    params_map = stack_description['Stacks'][0]['Parameters']
    for image in other_images:
        for index, param in enumerate(params_map):
            if param['ParameterKey'] == image:
                version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
                dic = {
                    'ParameterKey': image,
                    'ParameterValue': version
                }
                other_images_list.append(dic)

# Check if there's a version name and set it
if 'image_name' in service['Item']['serviceInfo']['deploy'] and \
                service['Item']['serviceInfo']['deploy']['image_name'].lower() != 'none':
    if s3_copy_script_job or recsys_emr_job:
        current_image_list = [
            {
                'ParameterKey': service['Item']['serviceInfo']['deploy']['image_name'],
                'ParameterValue': args.version
            }
        ]
    else:
        current_image_list = [
            {
                'ParameterKey': service['Item']['serviceInfo']['deploy']['image_name'],
                'ParameterValue': '638782101961.dkr.ecr.us-east-1.amazonaws.com/' + args.version
            }
        ]
else:
    current_image_list = []

current_image_list = current_image_list + other_images_list
print 'CURRENT IMAGE LIST: %s' % current_image_list

if os.path.exists(parameters_template):
    # Check for duplicates and remove if theres a duplicate
    with open(parameters_template) as f:
        json_params_list = yaml.load(f)
        altered_list = json_params_list
        for param_key in json_params_list:
            print 'current parameter key: %s' % param_key['ParameterKey']
            current_check_list = filter(lambda p: p['ParameterKey'] == param_key['ParameterKey'], current_image_list)
            print 'current check list : %s' % current_check_list
            if current_check_list:
                print 'True'
                altered_list = [dic for dic in altered_list if dic['ParameterKey'] != param_key['ParameterKey']]

    print 'altered_params_lst: %s' % altered_list

    with open(parameters_template, 'w') as f:
        json.dump(altered_list, f)

    with open(parameters_template) as f:
        print f.read()

    template = tempEnv.get_template(parameters_template)

    params_list = ast.literal_eval(
        str(template.render(config_data, region=args.region, profile=args.profile, accounts=accounts)))

    params_list = params_list + current_image_list
else:
    params_list = current_image_list

# Set UsePreviousValue str to bool since that's needed if it exists
for index, dic in enumerate(params_list):
    if 'UsePreviousValue' in dic and dic['UsePreviousValue'] != '':
        params_list[index]['UsePreviousValue'] = bool(distutils.util.strtobool(params_list[index]['UsePreviousValue']))

print 'PARAMS LIST:'
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
    for template in additional_templates:
        s3.upload_file(template, 'cf-clusters-%s-%s' % (args.profile, args.region), template)
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
            if e.response['Error']['Message'] == 'No updates are to be performed.':
                exit(0)
            else:
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
            if e.response['Error']['Message'] == 'No updates are to be performed.':
                exit(0)
            else:
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
