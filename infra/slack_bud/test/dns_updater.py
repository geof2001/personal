from __future__ import print_function

import json
import pendulum
import boto3
from botocore.exceptions import ClientError


ENVIRONMENTS = {
    "dev": '638782101961',
    "qa": '181133766305',
    "prod": '886239521314'
}


def multiregion_dns_update_handler(event, context):

    print("Received event: %s" % json.dumps(event))

    dynamodb = boto3.resource('dynamodb')
    dns_table = dynamodb.Table('MultiregionServiceDnsState')

    # Get valid regions
    regions = get_item_from_table(dns_table, 'regions')
    region_list = regions.split(",")
    print(region_list)

    # Get valid environments
    aws_env = get_item_from_table(dns_table, 'env')
    env_list = aws_env.split(",")
    print(env_list)

    # Get the change in dynamodb table from the event.
    for recordIndex, record in enumerate(event['Records']):
        # print("Record: %s" % json.dumps(record))
        # print('eventId: %s' % record['eventID'])
        new_image = record['dynamodb']['NewImage']
        rec_key = new_image['key']['S']
        rec_val = new_image['value']['S']

        # Filter stream to only work on keys in format. <env>:<alias>
        if not is_service_item_key(rec_key):
            print('Skipping --> %s: %s ' % (rec_key, rec_val))
            return 'done'

        print('Processing --> %s: %s' % (rec_key, rec_val))

        target_env = get_aws_environment(rec_key, env_list)
        alias_target_name = get_alias_target_name(rec_key)

        region_name = get_region_name_from_key(rec_key, region_list)
        service_name = get_service_name_from_value(rec_val)
        action = get_record_set_action_from_value(rec_val)
        print(
            'Env: %s\nAction: %s\nAliasTarget: %s\nServiceName: %s\nRegion: %s'
            % (target_env, action, alias_target_name,
               service_name, region_name)
        )

        route53_client = \
            get_route53_client_for_account(ENVIRONMENTS, target_env)

        hosted_zone_id = get_route53_hosted_zone_id(
            route53_client, 'sr.roku.com.')
        print("HostedZoneId = %s" % hosted_zone_id)
        hosted_zone_name = get_route53_hosted_zone_name_from_id(
            route53_client, hosted_zone_id)
        print("HostedZoneName = %s" % hosted_zone_name)

        record_found = \
            check_record_set_exists(route53_client, service_name,
                                    region_name, hosted_zone_id,
                                    hosted_zone_name, alias_target_name,
                                    region_list)

        do_update = True
        if not record_found and action == 'DELETE':
            do_update = False
        if record_found and action == 'UPSERT':
            do_update = False

        if do_update:
            # Split the service name from the status.
            success = update_dns_record_latency_routing(
                route53_client, service_name, region_name,
                hosted_zone_id, hosted_zone_name, alias_target_name, action)

            # Notify result.
            notify_update_result(target_env, action, alias_target_name,
                                 service_name, region_name, success)

        else:
            print("Skipped updating record")

    return 'done'


def is_service_item_key(rec_key):
    """Check that key has ':' character, indicating <env>:<alias> format."""
    return ':' in rec_key


# Expected rec_key format is <env>:<alias_target>. Like: dev:api2-us-west-2
# return dev
def get_aws_environment(rec_key, env_list):
    for currEnv in env_list:
        if currEnv.lower() in rec_key:
            return currEnv.lower()
    print('ERROR: no record found for %s' % rec_key)
    return 'env-not-found'


# Expected rec_key format is ENV:alias_target. Like: DEV:api2-us-west-2
# return api2-us-west-2
def get_alias_target_name(rec_key):
    parts = rec_key.split(":")
    return parts[1]


# Get Region name from key
def get_region_name_from_key(rec_key, region_list):
    print('get_region_name_from_key')
    for currRegion in region_list:
        if currRegion.lower() in rec_key:
            return currRegion.lower()
    return 'region-not-found'


# Get service name from value
# rec_val:   expexted format like   <service-name>:<on | off>
# return: <service-name>
def get_service_name_from_value(rec_val):
    ret = rec_val.split(":")
    return ret[0]


#  Get action from value
#  rec_val:   expexted format like   <service-name>:<on | off>
#  return:   either UPSERT - if 'on', or DELETE if 'off'
def get_record_set_action_from_value(rec_val):
    on_off_status = rec_val.split(":")
    ret = 'UPSERT'
    if on_off_status[1].lower() not in ['on', 'true', 't']:
        ret = 'DELETE'
    return ret


# Get an item from dynamo database
def get_item_from_table(dns_table, key_value):
    try:
        item = dns_table.get_item(Key={'key': key_value})
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        item_value = item['Item']['value']
        print('From get_item_from_table- %s: %s' % (key_value, item_value))
    return item_value


def notify_update_result(target_env, action, alias_target_name,
                         service_name, region_name, success):
    """Write result of action back into state table in the update attribute."""
    client = boto3.client('dynamodb')
    try:
        key = target_env+":"+alias_target_name
        update_value = create_update_value(success)

        print('Write to update attribute: %s %s' % (key, update_value))

        client.update_item(
            TableName='MultiregionServiceDnsState',
            Key={'key': {'S': key}},
            AttributeUpdates={
                "update":
                    {"Action": "PUT",
                     "Value": {"S": update_value}}}
        )
    except Exception as e:
        print('ERROR: failed to write result to table.')
        print(e)

    return 'done'


def create_update_value(success):
    """Create timestamp YYYYMMDD-HH:MM:SS format. Append ERROR if an error."""
    retval = ''
    if not success:
        retval += 'ERROR '
        time = pendulum.now('US/Pacific').strftime("%Y%m%d-%H:%M:%S")

    retval += time

    return retval


def check_record_set_exists(route53_client, service_name,
                            region_name, hosted_zone_id,
                            hosted_zone_name, alias_target_name, region_list):
    """Return True if record set it found otherwise false."""
    a_record_set_list = get_all_a_records(route53_client)

    print('check_record_set_exists()')
    print('service_name=%s, region_name=%s, hosted_zone_id=%s,'
          ' hosted_zone_name=%s, alias_target_name=%s'
          % (service_name, region_name, hosted_zone_id,
             hosted_zone_name, alias_target_name)
          )

    for curr_record in a_record_set_list:
        # print out the json (temporarily)
        # so we know what we are dealing with

        # Likely to be 'dns-demo.dev.sr.roku.com.'
        print(json.dumps(curr_record))
        curr_record_name = curr_record['Name']
        print('Route53 record name: %s' % curr_record_name)

        # Likely to be 'dns-demo-us-east-1.dev.sr.roku.com.'
        curr_record_alias_target_dns_name =\
            curr_record['AliasTarget']['DNSName']
        print('AliasTarget DNSName: %s' % curr_record_alias_target_dns_name)

        # Look for the service name to start the record Name
        print('')
        if curr_record_name.startswith(service_name):
            # Verify that it doesn't have any region name in it.
            if any([x in curr_record for x in region_list]):
                continue
            else:
                # Now look to see if the region is in the AliasTargetDNSName
                if region_name in curr_record_alias_target_dns_name:
                    print('check_record_set_exists: returns True')
                    return True
    # Record Set Not found
    print('check_record_set_exists: returns False')
    return False


def update_dns_record_latency_routing(
        route53_client, service_name, region_name,
        hosted_zone_id, hosted_zone_name, alias_target_name, action):
    """Update Route53 entry. Return True on success and False on error"""
    try:
        print("%s Route53 record for %s-%s"
              % (action, service_name, region_name))

        # This needs to be: <servicename>.<ZoneHostName>
        rs_name = service_name + "." + hosted_zone_name
        print("RecordSetName <servicename>.<zonehostname>: %s" % rs_name)
        set_identifier = service_name + "-" + region_name
        print(
            "SetIdentifier <service_name>-<region_name>: %s" % set_identifier
        )
        alias_target_dns = alias_target_name + "." + hosted_zone_name
        print("Alias Target: %s" % alias_target_dns)

        # boto3 call to change Route53 Record Set.
        response = route53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Comment': 'Multiregion: %s %s' % (service_name, region_name),
                'Changes': [
                    {
                        'Action': action,
                        'ResourceRecordSet': {
                            'Name': rs_name,
                            'Type': 'A',
                            'SetIdentifier': set_identifier,
                            'Region': region_name,
                            'AliasTarget': {
                                'HostedZoneId': hosted_zone_id,
                                'DNSName': alias_target_dns,
                                'EvaluateTargetHealth': False
                            }
                        },
                    }
                ]
            }
        )

        print("Finished RecordSet: %s for %s - %s"
              % (action, service_name, region_name))

        return True
    except Exception as e:
        print("Exception while adding %s for %s. Had : %s"
              % (service_name, region_name, e))
        return False


# Get the hosted zone id for a zone like "sr.roku.com."
def get_route53_hosted_zone_id(route53_client, base_url):
    print("Get Route53 Hosted Zone ID for %s" % base_url)
    hosted_zones = route53_client.list_hosted_zones()
    for zoneIndex, zones in enumerate(hosted_zones['HostedZones']):
        # print("Zone: %s" % json.dumps(hosted_zones))
        zone_name = zones['Name']
        if base_url in zone_name:
            ret_val = zones['Id']
            if ret_val.startswith('/hostedzone/'):
                return ret_val[len('/hostedzone/'):]
            return ret_val
    return 'not found'


# Get the Hosted Zone Name...    'dev.sr.roku.com', etc...
def get_route53_hosted_zone_name_from_id(route53_client, hosted_zone_id):
    response = route53_client.get_hosted_zone(Id=hosted_zone_id)
    ret_val = response['HostedZone']['Name']
    print("HostedZoneName: %s" % ret_val)
    return ret_val


# Get Route 53 client for a specific AWS account
def get_route53_client_for_account(environments, target_env):

    aws_account_num = environments[target_env]
    print(
        'get_route53_client_for_account(). Use %s for %s'
        % (aws_account_num, target_env)
    )

    sts = boto3.client('sts')
    session = sts.assume_role(
        RoleArn='arn:aws:iam::%s:role/SlackBudRole'
                % aws_account_num,
        RoleSessionName='SlackBudRole')

    route53_client = boto3.client(
        'route53',
        aws_access_key_id=session['Credentials']['AccessKeyId'],
        aws_secret_access_key=session['Credentials']['SecretAccessKey'],
        aws_session_token=session['Credentials']['SessionToken'],
        region_name='us-west-2')

    return route53_client


# Print a dictionary result
def print_dictionary(obj):
    if type(obj) == dict:
        for k, v in obj.items():
            if hasattr(v, '__iter__'):
                print(k)
                print_dictionary(v)
            else:
                print('%s : %s' % (k, v))
    elif type(obj) == list:
        for v in obj:
            if hasattr(v, '__iter__'):
                print_dictionary(v)
            else:
                print(v)
    else:
        print(obj)


#  For testing
#
#
# def multiregion_dns_update_handler(event, context):
#
#     print("Received event: %s" % json.dumps(event))
#
#     dynamodb = boto3.resource('dynamodb')
#     dns_table = dynamodb.Table('MultiregionServiceDnsState')
#     regions = get_item_from_table(dns_table, 'regions')
#     region_list = regions.split(",")
#     print(region_list)
#
#     # for curr_env in ENVIRONMENTS:
#     route53_client = get_route53_client_for_account(ENVIRONMENTS,'dev')
#
#     # list all of the route53 items
#     record_list = get_all_a_records(route53_client)
#
#     # find the ones that have a region in the name
#     regional_record_list = get_records_for_region(record_list)
#
#     # cross reference look for new entries in the old table
#
#     # send out a notification about detected updates.
#
#     return 'done'
#
#
# def get_records_for_region(record_list, aws_region_list):
#     """Get any records that have an AWS region in the name."""
#
#     for curr_record in record_list:
#         # print(json.dumps(curr_record))
#         curr_name = curr_record['Name']
#         print(curr_name)
#
#         if curr_name in aws_region_list:
#
#
#
#
def get_all_a_records(route53_client):
    hosted_zone_id = get_route53_hosted_zone_id(
        route53_client, 'sr.roku.com.')
    print("HostedZoneId = %s" % hosted_zone_id)
    hosted_zone_name = get_route53_hosted_zone_name_from_id(
        route53_client, hosted_zone_id)
    all_record_list = route53_client.list_resource_record_sets(
        HostedZoneId=hosted_zone_id,
    )

    a_type_record_list = []
    for i in all_record_list['ResourceRecordSets']:
        if i['Type'] == 'A':
            a_type_record_list.append(i)
            print('Adding A type record: %s' % i['Name'])

    print("Number route53 records: %s" % len(a_type_record_list))
    return a_type_record_list
