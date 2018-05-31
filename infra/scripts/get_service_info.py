#!/usr/bin/python
import argparse
import boto3

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Service Tool')
PARSER.add_argument('service', metavar='', default=None, help='Service Name')
PARSER.add_argument('--repo-only', default=False,  action='store_true', help='Get git repo')
args = PARSER.parse_args()

boto3.setup_default_session(profile_name='661796028321', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb')
services_table = dynamodb.Table('ServiceInfo')
service = services_table.get_item(Key={'serviceName': args.service})
try:
    if args.repo_only:
        git_repo = service['Item']['repo']
        print git_repo
    elif 'content-redis' in args.service:
        service_name = service['Item']['serviceName']
        copy_script = service['Item']['serviceInfo']['build']['params']['copy_script']
        git_repo = service['Item']['repo']
        service_info = 'SERVICE_NAME={service_name} ' \
                       'COPY_SCRIPT={copy_script} ' \
                       'GIT_REPO={git_repo}'.format(service_name=service_name,
                                                    copy_script=copy_script,
                                                    git_repo=git_repo)
        print service_info
    else:
        service_name = service['Item']['serviceName']
        repo_path = service['Item']['serviceInfo']['build']['params']['repo_path']
        docker_path = service['Item']['serviceInfo']['build']['params']['docker_base_container']
        if 'gradle_version' in service['Item']['serviceInfo']['build']['params']:
            gradle_version = service['Item']['serviceInfo']['build']['params']['gradle_version']
        else:
            gradle_version = '3.2.1'
        docker_repo = '638782101961.dkr.ecr.us-east-1.amazonaws.com'
        git_repo = service['Item']['repo']
        service_info = 'SERVICE_NAME={service_name} ' \
                       'SERVICE_PATH={repo_path} ' \
                       'DOCKER_PATH={docker_path} ' \
                       'DOCKER_REPO={docker_repo} ' \
                       'GIT_REPO={git_repo} ' \
                       'GRADLE_VERSION={gradle_version}'.format(service_name=service_name,
                                                    repo_path=repo_path,
                                                    docker_path=docker_path,
                                                    docker_repo=docker_repo,
                                                    git_repo=git_repo,
                                                    gradle_version=gradle_version)
        print service_info
except Exception as e:
    print 'The service may not exist in the ServiceInfo table, or the buildParams in the table are invalid.'
    print e
