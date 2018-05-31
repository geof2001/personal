#!/usr/bin/python
import boto3
import botocore
import argparse
import time
from datetime import datetime


def main(profile, region, timeout, stack_name):

    #
    # Starting time of script
    #

    start_time = datetime.now()

    #
    # Setup default AWS session
    #

    boto3.setup_default_session(profile_name=profile, region_name=region)

    #
    # Setup Cloudformation client, grab stack events, get current event resource status
    #

    cf = boto3.client('cloudformation')
    try:
        stack_events = cf.describe_stack_events(StackName=stack_name)
    except botocore.exceptions.ClientError:
        print 'The stack doesn\'t exist. Please specify a stack that already exists.'
        exit(1)
    current_status = stack_events['StackEvents'][0]['ResourceStatus']

    #
    # Flags for the stack event status
    #

    create_flag = True
    update_flag = True
    rollback_flag = True
    delete_flag = True

    while 'PROGRESS' in current_status:
        print 'CURRENT_STATUS: %s' % current_status
        #
        # Creating a stack
        #
        while current_status == 'CREATE_IN_PROGRESS':
            if create_flag:
                print 'Create currently in progress...'
                create_flag = False
            time_duration = datetime.now() - start_time
            if time_duration.total_seconds() > timeout:
                print 'Timeout: Create took too long...'
                exit(1)
            time.sleep(30)
            stack_events = cf.describe_stack_events(StackName=stack_name)
            current_status = stack_events['StackEvents'][0]['ResourceStatus']
            current_type = stack_events['StackEvents'][0]['ResourceType']
            if (current_status == 'CREATE_COMPLETE' or current_status == 'CREATE_FAILED') and current_type != 'AWS::CloudFormation::Stack':
                current_status = 'CREATE_IN_PROGRESS'

        #
        # Updating a stack
        #

        while current_status == 'UPDATE_IN_PROGRESS' or current_status == 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS':
            if update_flag:
                print 'Update currently in progress...'
                update_flag = False
            time_duration = datetime.now() - start_time
            if time_duration.total_seconds() > timeout:
                print 'Timeout: Update took too long...'
                exit(1)
            time.sleep(30)
            stack_events = cf.describe_stack_events(StackName=stack_name)
            current_status = stack_events['StackEvents'][0]['ResourceStatus']
            current_type = stack_events['StackEvents'][0]['ResourceType']
            if (current_status == 'UPDATE_COMPLETE' or current_status == 'UPDATE_FAILED') and current_type != 'AWS::CloudFormation::Stack':
                current_status = 'UPDATE_IN_PROGRESS'
        #
        # Deletion
        #

        while current_status == 'DELETE_IN_PROGRESS' or current_status == 'REVIEW_IN_PROGRESS':
            if delete_flag:
                print 'Deletion currently in progress...'
                delete_flag = False
            time_duration = datetime.now() - start_time
            if time_duration.total_seconds() > timeout:
                print 'Timeout: Update took too long...'
                exit(1)
            time.sleep(30)
            stack_events = cf.describe_stack_events(StackName=stack_name)
            current_status = stack_events['StackEvents'][0]['ResourceStatus']
            current_type = stack_events['StackEvents'][0]['ResourceType']
            if (current_status == 'DELETE_COMPLETE' or current_status == 'DELETE_FAILED') and current_type != 'AWS::CloudFormation::Stack':
                current_status = 'DELETE_IN_PROGRESS'


        #
        # Rollbacking a stack
        #

        while current_status == ('UPDATE_ROLLBACK_IN_PROGRESS'
                                 or current_status == 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS'
                                 or current_status == 'ROLLBACK_IN_PROGRESS'):
            if rollback_flag:
                print 'Rollback currently in progress...'
                rollback_flag = False
            time_duration = datetime.now() - start_time
            if time_duration.total_seconds() > timeout:
                print 'Timeout: Rollback took too long...'
                exit(1)
            time.sleep(30)
            stack_events = cf.describe_stack_events(StackName=stack_name)
            current_status = stack_events['StackEvents'][0]['ResourceStatus']
            current_type = stack_events['StackEvents'][0]['ResourceType']
            if (current_status == 'ROLLBACK_COMPLETE' or current_status == 'ROLLBACK_FAILED' or current_status == 'UPDATE_ROLLBACK_COMPLETE' or current_status == 'UPDATE_ROLLBACK_FAILED') and current_type != 'AWS::CloudFormation::Stack':
                current_status = 'ROLLBACK_IN_PROGRESS'


    #
    # Complete/Fail messages
    #

    if current_status == 'CREATE_COMPLETE':
        print 'Stack successfully created...'

    if current_status == 'CREATE_FAILED':
        print 'Failed to create the stack...'

    if current_status == 'ROLLBACK_COMPLETE' or current_status == 'UPDATE_ROLLBACK_COMPLETE':
        print 'Rollback completed...'

    if current_status == 'ROLLBACK_FAILED' or current_status == 'UPDATE_ROLLBACK_FAILED':
        print 'Rollback failed...'

    if current_status == 'UPDATE_COMPLETE':
        print 'Update completed...'

    exit(0)


if __name__ == '__main__':

    #
    # Setup arguments from command line
    #

    parser = argparse.ArgumentParser(description='Determines which stack is currently updating')
    parser.add_argument('-p', '--profile', metavar='', help=' AWS Account Number', default='638782101961')
    parser.add_argument('-r', '--region', metavar='', help='AWS Region', default='us-east-1')
    parser.add_argument('-t', '--timeout', type=int, metavar='', help='Time Duration Until Timeout (Seconds)', default=3600)
    parser.add_argument('-s', '--stack_name', metavar='', required=True, help='Stack Name')
    args = parser.parse_args()

    #
    # Main()
    #

    main(args.profile, args.region, args.timeout, args.stack_name)
