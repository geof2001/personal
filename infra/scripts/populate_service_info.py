#!/usr/bin/python
#
# updates two DynamoDBs with data from the CICD.yaml file

import argparse
import boto3
import os
from botocore.exceptions import ClientError
import yaml
import datetime
import pprint


if __name__ == '__main__':

    # Argument parser configuration
    parser = argparse.ArgumentParser(description='populate service tables')
    parser.add_argument('-r', '--repo', help=' Repository to upload to DynamoDB')
    args = parser.parse_args()

    timestamp = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())

    # find the CICD file
    config_file = '../../' + args.repo + '/infra/service_info.yaml'
    if not os.path.isfile(config_file):
        config_file = '../' + args.repo + '/infra/service_info.yaml'

    # load the file
    with open(config_file) as cf:
        config = yaml.load(cf)
        print "repository: ", args.repo
        pprint.pprint(config)

    boto3.setup_default_session(profile_name='661796028321', region_name='us-west-2')

    # write the whole CICD file to the DB table with the repo as the key
    dynamodb = boto3.resource('dynamodb')
    repo_table = dynamodb.Table('RepoInfo')

    try:

        print "updating repo table"
        result = repo_table.put_item(
            Item={
                'repo': args.repo,
                'config': config,
                'update': timestamp
            })
    except ClientError as e:
        print 'repo info table write failed'
        print e.response['Error']['Message']
        exit(1)

    # write each service's info to the service table

    service_table = dynamodb.Table('ServiceInfo')

    for service_name in config['components']:

        repo_from_ddb = service_table.get_item(
            Key={
                'serviceName': service_name
            }
        )

        if "Item" in repo_from_ddb:
            print 'Repo from ddb service table:', repo_from_ddb['Item']['repo']
            if repo_from_ddb['Item']['repo'] != args.repo:
                print "The repository listed in the service_info.yaml file is not the same as the one stored in the db."
                print "This is likely a duplicated service name."
                print "Not updating the service info table."
                exit(1)

        print "Service Name:", service_name
        pprint.pprint(config['components'][service_name])

        try:
            print "updating service table"
            result = service_table.put_item(
                Item={
                    'serviceName': service_name,
                    'repo': args.repo,
                    'serviceInfo': config['components'][service_name],
                    'update': timestamp
                }
            )
        except ClientError as e:
            print 'service info table write failed'
            print e.response['Error']['Message']
            exit(1)

    exit(0)
