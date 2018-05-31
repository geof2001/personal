"""The entry point for the AWS cost allocation tagging lambda function"""
from __future__ import print_function

import json
import boto3
import util.aws_util as aws_util
import util.aws_tag_utils as aws_tag_util

ENVIRONMENTS = {
    "dev": '638782101961',
    "qa": '181133766305'}


# This is a temporary map to be replace by a file in an S3 bucket.
# It is a map of stack names to spend categories.
# The eligible categories are:
#  content
#  ingest
#  recsys
#  net
#  videoservices
#  tracking
#
#  NOTE: the sr-data stack is a mixture of spend categories Need to look at on an
#  individual basis.
SPEND_CATEGORY = {
    'ingestor': 'ingest',
    'jwt-edge-token-dev': 'net',
    'recsys-wikipedia-extractor': 'recsys',
    'authtokens': 'net',
    'tvFeedService-dev': 'content',
    'recsys-redis-mass-inserter': 'recsys',
    'cms': 'content',
    'content-data-generator': 'content',
    'ota': 'content',
    'bifservice': 'videoservices',
    'idresolver': 'ingest',
    'search': 'content',
    'images': 'content',
    'downloader': 'content',
    'search-indexer': 'content',
    'bookmarker': 'recsys',
    'multiregion-notifications': 'ingest',
    'homescreen': 'content',
    'datafetcher': 'ingest',
    'sr-cap-content-differ': 'ingest',
    'popularity': 'tracking',
    'recsys-api': 'recsys',
    'recsys': 'recsys',
    'tracking': 'tracking',
    'deduper': 'ingest',
    'sr-global-services': 'content',
    'sr-blue-batch': 'ingest',
    'sr-docs': 'net',
    'sr-myfeed-data': 'ingest',
    'ecs-custom-metrics': 'net',
    'sr-search': 'content',
    'sr-search3-cloudfront': 'content',
    'sr-blue': 'content',
    'sr-data': '?',
    'roku-network': 'net',
}


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event))

    env = 'dev'
    region = 'us-east-1'

    print('Get the CF stack in dev{} account. - {}'.format(env, region))
    session = aws_util.create_session(env)
    cf_client = aws_util.get_cloudformation_client(session, region)
    tag_client = aws_util.get_tagging_client(session, region)

    print('List all of the stack names in this account and region')
    stack_name_list = list_stacks(cf_client)

    num_stacks = len(stack_name_list)
    print('Found {} stacks'.format(num_stacks))
    stack_count = 0
    for curr_stack_name in stack_name_list:
        stack_count += 1
        resource_count = 0
        print('\nListing resources for: stack#{}) {}'.format(stack_count, curr_stack_name))
        resource_list = get_resources_from_stack(cf_client, curr_stack_name)
        num_resource_ids = len(resource_list)
        print('Found {} resource ids'.format(num_resource_ids))
        for curr_resource in resource_list:
            resource_count += 1
            print('stack #{}:{}  {} ({})'.format(stack_count, resource_count, curr_resource['arn'], curr_resource['type']))
        apply_tags(tag_client, resource_list, curr_stack_name, env, region)

    # If time permits need to get all EC2 Instance and tag them based on name.
    tag_ecs_hosts_by_name(env, region)

    return 'done'


def get_resources_from_stack(cf_client, stack_name):
    """
    Return all the resource ids for this stack.
    :param cf_client:
    :param stack_name:
    :return:
    """
    resource_id_list = []

    response = cf_client.list_stack_resources(
        StackName=stack_name
    )

    for curr_resource_summary in response['StackResourceSummaries']:
        resource_type = curr_resource_summary['ResourceType']
        logical_id = curr_resource_summary['LogicalResourceId']
        physical_id = curr_resource_summary['PhysicalResourceId']
        if is_taggable_resource_type(resource_type):
            # print('\ntype: {}\nlogical_id: {}\nphysical_id: {}\n'.format(resource_type, logical_id, physical_id))
            resource_info = {
                "arn": physical_id,
                "type": resource_type
            }
            resource_id_list.append(resource_info)

    return resource_id_list


def list_stacks(cf_client):
    """NOTE: Need permission updates to make this run"""
    print('List all of the stack names in this account.')
    stacks = cf_client.list_stacks(
        StackStatusFilter=['UPDATE_COMPLETE']
    )

    stack_name_list = []
    for curr_stack in stacks['StackSummaries']:
        stack_id = curr_stack['StackId']
        stack_name = curr_stack['StackName']
        stack_name_list.append(stack_name)
        last_update_time = curr_stack['LastUpdatedTime']

        print('---\nid: {}\nname: {}\nlast update: {}\n'.format(stack_id, stack_name, last_update_time))

    return stack_name_list


# def describe_stacks(cf_client, stack_name):
#     """
#     Describe a stack.
#     """
#     print('Describe stack: {}'.format(stack_name))
#     stacks = cf_client.describe_stacks(
#         StackName=stack_name
#     )
#
#     for curr_stack in stacks['Stacks']:
#         stack_id = curr_stack['StackId']
#         stack_name = curr_stack['StackName']
#         last_update_time = curr_stack['LastUpdatedTime']
#         stack_status = curr_stack['StackStatus']
#
#         print('---\nid: {}\nname: {}\nlast update: {}\nstatus: {}'.format(stack_id, stack_name, last_update_time,
#                                                                           stack_status))


def is_taggable_resource_type(resource_type):
    """
    Return True if this AWS Resource type can be tagged.
    :param resource_type: String of
    :return:
    """
    if resource_type == 'AWS::ElasticLoadBalancingV2::LoadBalancer':
        return True
    elif resource_type == 'AWS::Lambda::Function':
        return True
    elif resource_type == 'AWS::DynamoDB::Table':
        return True
    elif resource_type == 'AWS::SQS::Queue':
        return True
    elif resource_type == 'AWS::S3::Bucket':
        return True
    elif resource_type == 'AWS::EC2::Instance':
        return True
    elif resource_type == 'AWS::EC2::NatGateway':
        return True
    elif resource_type == 'AWS::EC2::VPCEndpoint':
        return True
    elif resource_type == 'AWS::EC2::VPCPeeringConnection':
        return True
    elif resource_type == 'AWS::ElasticLoadBalancingV2::TargetGroup':
        return True

    # ToDo: add elasticache, elasticsearch, eip, sns topic, rds, athena, kinesis

    # print('not taggable: {}'.format(resource_type))
    return False


def apply_tags(tag_client, resource_info_list, stack_name, env, region):
    """
    Check the tag for this resource.
    :param tag_client: boto3 tagging client
    :param resource_info_list: dictionary of resource arn and type
    :param stack_name: string of stack name
    :param env: string AWS Environment like 'dev' | 'qa' | 'prod'
    :param region: string AWS region like 'us-west-2'
    :return: None
    """
    arn_list = []
    for curr_resource_info in resource_info_list:
        arn = curr_resource_info['arn']
        aws_type = curr_resource_info['type']
        if arn is not None and len(arn) > 0:
            if 'arn:' in arn:
                arn_list.append(arn)
            else:
                print('type: {} needs to lookup ARN'.format(aws_type))
                created_arn = make_arn_from_type(env, region, arn, aws_type)
                if created_arn is not None:
                    arn_list.append(created_arn)
        else:
            print('excluding arn: {} of type: {}'.format(arn, aws_type))
    if len(arn_list) == 0:
        print("No resources to tag for stack: {}".format(stack_name))
        return None
    try:
        spend_category = get_spend_category_from_stack_name(stack_name)
        arn_list_size = len(arn_list)
        print('SpendCategory: {} for: {} has {} resources.'.format(spend_category, stack_name, arn_list_size))

        response = tag_client.tag_resources(
            ResourceARNList=arn_list,
            Tags={
                'Stack': stack_name,
                'Spend_Category': spend_category,
                'Department': 'SR'
            }
        )

        failed_map = response['FailedResourcesMap']
        failed_map_size = len(failed_map.keys())
        if failed_map_size > 0:
            print('No tags set for {} of {} possible resources.'.format(failed_map_size, arn_list_size))
            keys = failed_map.keys()
            first_key = next(iter(keys))
            status_code = failed_map[first_key]['StatusCode']
            error_code = failed_map[first_key]['ErrorCode']
            error_msg = failed_map[first_key]['ErrorMessage']
            print('Example error:\n{} - {}\n{}'.format(status_code, error_code, error_msg))

    except Exception as ex:
        print("ERROR: {}".format(ex.message))
        raise ex


def make_arn_from_type(env, region, arn, aws_type):
    """
    Try to create AWS Arn for some types that don't have them.

    Example arn:
    arn:aws:elasticloadbalancing:us-east-1:638782101961:targetgroup/sr-bl-Defau-EE942IZT8L2O/f5fb9158804750ff

    arn:aws:dynamodb:us-west-2:661796028321:table/BudServices

    arn:aws:ec2:region:account-id:instance/instance-id

    arn:aws:kinesis:us-east-1:123456789012:stream/example-stream-name

    arn:aws:es:region:account - id:domain / domain - name

    https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html#genref-arns

    :param env:
    :param region:
    :param arn:
    :param aws_type:
    :return: string of arn if success otherwise None
    """
    type_lower = aws_type.lower()
    aws_account = ENVIRONMENTS.get(env)
    arn_kernel = 'arn:aws:{}:{}:{}:{}'.format('{}', region, aws_account, '{}', '{}')
    if 's3' in type_lower:
        # Need to fill in the s3 type and end
        # new_arn = arn_kernel.format('some-s3-type')
        return None
    elif 'dynamo' in type_lower:
        table = 'table/'+arn
        dynamo_arn = arn_kernel.format('dynamodb', table)
        print("Creating dynamo arn: {}".format(dynamo_arn))
        return dynamo_arn
    elif 'sqs' in type_lower:
        sqs_arn = arn_kernel.format('sqs', arn)
        print("Creating SQS arn: {}".format(sqs_arn))
        return sqs_arn
    elif 'lambda' in type_lower:
        fun = 'function:'+arn
        lambda_arn = arn_kernel.format('lambda', fun)
        print("Creating lambda arn: {}".format(lambda_arn))
        return lambda_arn
    elif 'sns'in type_lower:
        return None
    elif 'ec2' in type_lower and 'instance' in type_lower:
        instance = 'instance/'+arn
        ec2_instance_arn = arn_kernel.format('ec2', instance)
        print("Creating ec2 instance arn: {}".format(ec2_instance_arn))
        return ec2_instance_arn
    elif 'elasticsearch' in type_lower:
        es_domain = 'domain/'+arn
        es_arn = arn_kernel.format('es', es_domain)
        print("Creating elasticsearch domain arn: {}".format(es_arn))
        return es_arn
    elif 'kinesis' in type_lower:
        kinesis_stream = 'stream/'+arn
        ks_arn = arn_kernel.format('kinesis', kinesis_stream)
        return ks_arn
    else:
        print("WARNING: unrecognized type: {}".format(aws_type))
    return None


def get_spend_category_from_stack_name(stack_name):
    """
    Assign the spend category based on the stack name.

    Look this up in a table.
    :param stack_name:
    :return: spend category string, or '?' if unknown.
    """

    # Any stack name that contains 'recsys' is assigned 'recsys'
    if 'recsys' in stack_name:
        return 'recsys'

    # Look-up the remaining in the map.
    spend_category = SPEND_CATEGORY.get(stack_name, 'unknown_spend_category')
    if spend_category == 'unknown_spend_category':
        print('No spend_category found for {}'.format(stack_name))

    return spend_category


def tag_ecs_hosts_by_name(env, region, ec2_name, spend_category):
    """
    ECS doesn't as of 2/2018 let you tag at lower level like ECS Service
    or task level. So until that day we will just need to accept tagging
    at the host level, which gives only rough information (without including
    more stats like CPU usage) for example.

    The routine looks at EC2 host names and tags the ones that belong to
    the ECS Service and ECS Batch clusters.

    When lower level tags are available switch to those. An alternative
    follow-up is to combine this with Service or Task level CPU data
    to get more detailed information.
    :param env:
    :param region:
    :param ec2_name:
    :param spend_category:
    :return:
    """
    session = aws_util.create_session(env)
    ec2 = aws_util.get_ec2_resource(session, region)
    ec2_instance_count = 0
    instances = ec2.instances.filter(
        Filters=[{'Name': ec2_name, 'Values': ['running']}]
    )
    for instance in instances:
        print(instance.id)
