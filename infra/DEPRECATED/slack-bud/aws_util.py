"""Utility class for getting AWS resources."""
from __future__ import print_function

from datetime import datetime
import boto3
import pytz
from requests_aws_sign import AWSV4Sign
from elasticsearch import Elasticsearch, RequestsHttpConnection, TransportError

HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"


class CodePipelineStageError(Exception):
    """Raise this exception when you want to fail a stage in code-pipeline"""
    def __init__(self, *args):
        Exception.__init__(self, *args)


def get_dynamo_resource(session, region, client=False):
    """Get a dynamodb client from a session."""

    if not client:
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=session['Credentials']['AccessKeyId'],
            aws_secret_access_key=session['Credentials']['SecretAccessKey'],
            aws_session_token=session['Credentials']['SessionToken'],
            region_name=region
        )
    else:
        dynamodb = boto3.client(
            'dynamodb',
            aws_access_key_id=session['Credentials']['AccessKeyId'],
            aws_secret_access_key=session['Credentials']['SecretAccessKey'],
            aws_session_token=session['Credentials']['SessionToken'],
            region_name=region
        )
    return dynamodb


def get_cloudformation_client(session, region):
    """Get a cloundformation client from a session"""
    return boto3.client(
        'cloudformation',
        aws_access_key_id=session['Credentials']['AccessKeyId'],
        aws_secret_access_key=session['Credentials']['SecretAccessKey'],
        aws_session_token=session['Credentials']['SessionToken'],
        region_name=region
    )


def get_ecr_client(session, region):
    """Get a ecr client from a session"""
    return boto3.client(
        'ecr',
        aws_access_key_id=session['Credentials']['AccessKeyId'],
        aws_secret_access_key=session['Credentials']['SecretAccessKey'],
        aws_session_token=session['Credentials']['SessionToken'],
        region_name=region
    )


def get_session(environments, env):
    """Get a session from the environment assume roles."""
    sts = boto3.client('sts')
    session = sts.assume_role(
        RoleArn='arn:aws:iam::%s:role/SlackBudRole' % environments[env],
        RoleSessionName='SlackBudRole')
    return session


def setup_es():

    """Setup ES object with host"""
    # If no version flag value was provided, look up previous builds from ES
    session = boto3.session.Session()
    credentials = session.get_credentials()
    region = 'us-west-2'
    service = 'es'
    auth = AWSV4Sign(credentials, region, service)

    try:
        es_client = Elasticsearch(host=HOST, port=443, connection_class=RequestsHttpConnection,
                                  http_auth=auth, use_ssl=True, verify_ssl=True)
    except TransportError as exc:
        exit('Unable to establish ES connection with host - %s' % exc.message)

    return es_client


def get_prop_table_time_format():
    """Get timestamp in format used in prop dynamo tables.

    Example: January 19, 2018 - 09:55:48
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%B %d, %Y - %H:%M:%S")
    return time


def get_dynamo_backup_name_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%Y-%b-%d-%H%M")
    return time


def get_build_info_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%Y%m%d")
    return time
