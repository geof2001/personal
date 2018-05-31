#!/usr/bin/python

import json
import yaml
import ast
import sys
import boto3
import botocore
import argparse
import time
import pprint
import pylint
import distutils.util
import os
try:
    from jinja2 import Environment, FileSystemLoader, Template
except ImportError:
    exit('Please install the jinja2 module. Try \'pip install Jinja2\'.')

# Argument Parser Configuration
parser = argparse.ArgumentParser(description='Jinja2 Python for Deployment')
parser.add_argument('--service', metavar='', help=' ServiceStack name')
parser.add_argument('--canary', action='store_true', help=' Create Canary')
parser.add_argument('--release', action='store_true', help=' release your canary')
parser.add_argument('--count', metavar='', help=' number of canary instances to launch')
parser.add_argument('-s', '--stack_name', metavar='', help=' Stack Name')
parser.add_argument('-r', '--region', metavar='', help='AWS Region')
parser.add_argument('-p', '--profile', metavar='', help=' AWS Account Number')
parser.add_argument('-b', '--buildnum', help='Build Number', default='', metavar='')
parser.add_argument('-g', '--git_repo', metavar='', help='name of the git repository')

if len(sys.argv)<2:
    parser.print_help()
    sys.exit(1)
args = parser.parse_args()

# Accounts Map
accounts = {"638782101961": "dev",
            "181133766305": "qa",
            "886239521314": "prod",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-prod": "prod"}

# Constants
paramsData = []
configData = []
stackData = []
tableExists = False
GITPATH=os.environ['GITPATH']

ecr_repo = '638782101961.dkr.ecr.us-east-1.amazonaws.com'
db1 = ecr_repo + '/content:master-a9a93c2-20180126-6048'
db2 = ecr_repo + '/content:es-6-upgrade-be0c06a-20180124-6017'
# demo_params_list='[{'ParameterValue':'db1','ParameterKey':'ContentImage'}]'

# Setup boto3 default configurations
boto3.setup_default_session(profile_name=args.profile, region_name=args.region)
repopath = GITPATH + '/' + args.git_repo + '/infra'
# os.chdir(repopath)

# Define templates used for S3/CF during deployment
service_template = '%s.stack.yaml' % args.service
canary_template = '%s.canary.yaml' % args.service
parameters_template = 'canary.params.json'  # % args.service
service_config = '%s.config.yaml' % args.service
repo_config = '%s.config.yaml' % args.git_repo

tempEnv = Environment(loader=FileSystemLoader('./'))
print(os.getcwd())
with open("service_info.yaml") as config_file:
    config_data = yaml.load(config_file)
config_data = []
try:
    with open(service_config) as service_config_file:
        service_config_data = yaml.load(service_config_file)

    config_data.update(service_config_data)
except:
    print ('no service config file')

if (repo_config != service_config):
    try:
        with open(repo_config) as repo_config_file:
            repo_config_data = yaml.load(repo_config_file)

        config_data.update(repo_config_data)
    except:
        print ('no repo config file')

print "Config data:"
pprint.pprint(config_data)
template = tempEnv.get_template(parameters_template)
params_list = ast.literal_eval(
    str(template.render(config_data,
                        region=args.region,
                        profile=args.profile,
                        accounts=accounts)
        )
)


# create an aws client of type clientName
def aws_client(clientName, profileName, regionName):
    boto3.setup_default_session(
        profile_name=profileName,
        region_name=regionName
        )
    client = boto3.client(clientName)
    return client


def cf_builder(serviceName, buildNum):
    print ('cf_builder')


def cf_scan(serviceName, profileName, regionName, buildNum):
    print ('cf_scan')
    cf = aws_client('cloudformation', profileName, regionName)
    stack_exists = False
    try:
        cf.describe_stacks(StackName='%s-%s' % (serviceName, buildNum))
        stack_exists = True
        print ('Your canary is fluttering around in the cage...')

    except botocore.exceptions.ClientError:
        print ('No Canaries were found in your cage...')
    return stack_exists


def cf_deploy(stackName, profileName, regionName):
    """
        Deploys canary cloudformation stack to the appropriate account
        and region.
    """
    cf = aws_client('cloudformation', profileName, regionName)
    if params_list:
        try:
            print ('Creating Cloudformation stack...')
            cf.create_stack(
              StackName='%s-%s' % (stackName, args.buildnum),
              Capabilities=['CAPABILITY_NAMED_IAM'],
              Parameters=params_list,
              TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml'
                % (args.profile.lower(), args.region, stackName)
                )

        except botocore.exceptions.ClientError as e:
            print ('Unable to create AWS Cloudformation stack...')
            print (e.response['Error']['Message'])
            exit(1)

    else:
        try:
            print ('Creating CloudFormation stack...')
            cf.create_stack(
              StackName='%s-%s' % (stackName, args.buildnum),
              Capabilities=['CAPABILITY_NAMED_IAM'],
              TemplateURL='https://cf-clusters-%s-%s.s3.amazonaws.com/%s.yaml'
                % (profileName.lower(), regionName, stackName)
                )

        except botocore.exceptions.ClientError as e:
            print ('Unable to create AWS Cloudformation stack...')
            print (e.response['Error']['Message'])
            exit(1)


def global_table_create(tableName):
    ddb = aws_client('dynamodb', args.profile, args.region)
    globalTable = ddb.create_global_table(
        GlobalTableName=tableName,
        ReplicationGroup=[
            {
                'RegionName': args.region
            }
        ]
    )


def global_table_add_region(tableName, regionName):
    ddb = aws_client('dynamodb', args.profile, args.region)
    globalTable = ddb.describe_global_table(GlobalTableName=tableName)
    regionFound = False
    regionList = []
    for region in globalTable['GlobalTableDescription']['ReplicationGroup']:
        if args.region in region['RegionName']:
            regionFound = True
            regionList.append(region)
            print regionFound
            # print globalTable['GlobalTableDescription']['ReplicationGroup']
    if not regionFound:
        ddb.update_global_table(
            GlobalTableName=tableName,
            ReplicaUpdates=[
                {
                    'Create': {
                        'RegionName': args.region
                    }
                }
            ]
        )
    else:
        return regionFound

def table_create(tableName):
    ddb = aws_client('dynamodb', args.profile, args.region)
    response = ddb.create_table(
        AttributeDefinitions=[
            {
                'AttributeName': 'stackName',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'deployTime',
                'AttributeType': 'S'
            }
        ],
        KeySchema=[
            {
                'AttributeName': 'stackName',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'deployTime',
                'KeyType': 'RANGE'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        },
        StreamSpecification={
            'StreamEnabled': True,
            'StreamViewType': 'NEW_AND_OLD_IMAGES'
        },
        TableName=tableName
    )

    isGlobal = False
    try:
        globalTable = ddb.describe_global_table(
            GlobalTableName=tableName,
        )
        isGlobal = True
    except botocore.exceptions.ClientError as e:
        print(e.response['Error']['Message'])
        print('Global still false. Converting table to global.')
        global_table_create(tableName)

    # print globalTable['GlobalTableDescription']['ReplicationGroup']

    return response


def table_check(tableName, profileName, regionName):
    ddb = aws_client('dynamodb', profileName, regionName)
    global tableExists
    while not tableExists:
        try:
            print('Checking if table exists')
            cage = ddb.describe_table(TableName=tableName)
            print('Table %s was found.' % tableName)
            tableExists = True

        except botocore.exceptions.ClientError as e:
            print('Canary cage %s was not found or not yet ready.'
                  'Checking status again in 10 seconds.' % tableName)
            print('Botocore error: %s' % e.response)
            tableInstance = table_create(tableName)
            print tableInstance
            time.sleep(10)
            table_check(tableName, args.profile, args.region)


# Remove the canary stack from cloudformation
def cf_reaper(stackName, profileName, regionName):
    """
        Deletes the canary cloudformation stack specified.
    """
    cf = aws_client('cloudformation', profileName, regionName)
    try:
        print ('Your Canary is being set free...')
        cf.delete_stack(StackName='%s-%s' % (args.stack_name, args.buildnum))

    except botocore.exceptions.ClientError as e:
        print (
            'Your Canary won\'t leave the cage' +
            'please check the Cloudformation console...'
            )
        print (e.response['Error']['Message'])
        exit(1)


# Locate build string
def canary_search(buildnum):
    ecr = aws_client('ecr', args.profile, args.region)
    # print repo_list
    list_images = ecr.list_images(repositoryName=args.service)
    imageIds = []
    next_token = list_images['nextToken']
    print (next_token)
    list2_images = ecr.list_images(repositoryName=args.service,
                                   nextToken=next_token)
    next2_token = list2_images['nextToken']
    list3_images = ecr.list_images(repositoryName=args.service,
                                   nextToken=next2_token)
    for i in list3_images:
        print (i)
    for i in list_images['imageIds']:
        imageIds.append(i['imageTag'])
    # l.sort(key = lambda x: int(x.rsplit(' ',1)[1]))
    print (len(imageIds) % 100)
    split_images = []
    for image in imageIds:
        split_images.append(image.rsplit('-', 2))
    # sorted_split_images = sorted(split_images, key=lambda x:x[1])
    # for image in sorted_split_images:
        # if image[2] == args.canary:
        # print image[2]

if args.canary:
    print ('Canary operations were requested..')
    # canary_search(args.canary)

s3 = boto3.client('s3')

# Create AWS S3 Bucket For Templates
if args.region == 'us-east-1':
    try:
        print ('Creating AWS S3 buckets for Template...')
        s3.create_bucket(
                            Bucket='cf-clusters-%s-%s'
                            % (args.profile.lower(), args.region)
                        )
    except botocore.exceptions.ClientError:
        print ('Unable to create AWS S3 buckets for Template...')

if args.region != 'us-east-1':
    try:
        print ('Creating AWS S3 buckets for Template...')
        s3.create_bucket(
                        Bucket='cf-clusters-%s-%s'
                        % (args.profile.lower(), args.region),
                        CreateBucketConfiguration={
                            'LocationConstraint': '%s' % args.region
                            }
                        )
    except botocore.exceptions.ClientError:
        print ('Unable to create AWS S3 buckets for Template...')

# Upload CF Template to AWS S3 Bucket
try:
    s3.upload_file(
                    canary_template, 'cf-clusters-%s-%s'
                    % (args.profile.lower(), args.region),
                    '%s.yaml' % args.stack_name
                    )
except botocore.exceptions.ClientError:
    print ('Unable to upload CloudFormation Template to AWS S3 Bucket...')

# Check if CF stack exists
stack_exists = cf_scan(
                args.stack_name,
                args.profile,
                args.region,
                args.buildnum
                )

# Create stack if it doesn't exist
if not stack_exists and not args.release:
    print (
          'Your canary is hatching and is named %s-%s...'
          % (args.stack_name, args.buildnum)
          )
    cf_deploy(args.stack_name, args.profile, args.region)

if stack_exists and args.release:
    cf_reaper(args.stack_name, args.profile, args.region)

accountId = boto3.client('sts').get_caller_identity()['Account']
# print accountId
tableName = "canary_cage_" + accountId
# print tableName
table_check(tableName, args.profile, args.region)
global_table_add_region(tableName, args.region)
