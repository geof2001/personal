"""Utility class with helper methods for bud commands.

This class depends on aws_util, but it agnostic of the UI.
Exceptions caught need to be converted into UI format and
passed back to the user.
"""
from __future__ import print_function

import zipfile
import json
import os
import boto3
import aws_util
import random
import datetime
import traceback
import re
from elasticsearch import Elasticsearch, RequestsHttpConnection, TransportError


class BudHelperError(Exception):
    """Catch this exception from bud_helper_util methods that throw it.
    An error message needs to be propagated back out to the user.

    NOTE: Don't throw this exception, only catch and convert it.
    """
    def __init__(self, *args):
        Exception.__init__(self, *args)


def get_props_table_name_for_service(service_param, env_param, region_param):
    """Convert service parameter on command-line into dynamo properties table.

    If the property table doesn't exist for one of several reasons this will
    throw a BudHelperError, which needs to be caught and converted into
    a message back to the user.

    :param service_param: Same as args.services[0]
    :param env_param: Same as args.envs[0]
    :param region_param: Same as args.regions[0]
    :return:  Name of Dynamo table as a string
    """
    dynamo_resource = boto3.resource('dynamodb')
    service_table = dynamo_resource.Table('ServiceInfo')
    service = service_table.get_item(Key={'serviceName': service_param})
    try:
        session = aws_util.create_session(env_param)
    except:
        raise BudHelperError('No environment')
    if region_param not in aws_util.AWS_REGIONS:
        raise BudHelperError('No region for service.')

    # cf_client = aws_util.get_cloudformation_client(session, region_param)
    try:
        stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
        props_table = get_props_table_name_for_stack_name(
            session, region_param, stack_name, service_param
        )
        # stack_description = cf_client.describe_stacks(
        #     StackName=service['Item']['serviceInfo']['properties_table']['stack_name'])
        # props_table = stack_description['Stacks'][0]['Outputs'][0]['OutputValue']

        print(
            'get_props_table_name_for_service() found table: %s for service: %s in %s - %s'
            % (props_table, service_param, env_param, region_param)
        )
        return props_table
    except:
        # raise BudHelperError('Table not found.')
        # Temporarily use (None) as a signal to use the default
        # Dynamo table -- for testing.
        print('No table found by get_props_table_name_for_service, use default')
        return None


def get_props_table_name_for_stack_name(session, region, stack_name, service):
    """Find the Archaius Property table for a stack.
    """

    try:
        cf = aws_util.get_cloudformation_client(session, region)
        stack_description = cf.describe_stacks(StackName=stack_name)

        index = 0
        for i, dic in enumerate(stack_description['Stacks'][0]['Outputs']):
            if 'PropertiesTable' in dic['OutputKey']:
                index = i
                break

        props_table = stack_description['Stacks'][0]['Outputs'][index]['OutputValue']
        return props_table

    except:
        raise BudHelperError(
            'Failed to find Property table for stack: %s, service: %s, in region: %s' %
            (stack_name, service, region)
        )

def grep(filename, needle):
    """Find text within file.
    This returns a list of matching lines.
    """
    ret = []
    with open(filename) as f_in:
        for i, line in enumerate(f_in):
            if needle in line:
                ret.append(line)
    return ret


def read_key_value_file_to_dictionary(filepath, delim='='):
    """Read a file in the following format.
    key1 = value1
    key2 = value2
    key3 = value3

    and convert it into a dictionary.

    :param filepath: path to the file
    :param delim: delimiter used. '=' is default. ': ' will also be common.
    :return: dictionary values of file.
    """
    f = open(filepath, 'r')
    answer = {}
    for line in f:
        k, v = line.strip().split(delim)
        answer[k.strip()] = v.strip()

    f.close()
    return answer


def unzip_file(zip_file_path, to_dir):
    """Unzip a *.zip file in a local directory."""

    try:
        print('Unzip verifying path: %s' % zip_file_path)
        # Verify zip file
        if not os.path.isfile(zip_file_path):
            message = 'Unzip failed to verify file: %s' % zip_file_path
            print(message)
            raise BudHelperError(message)
        else:
            print('Verified "{}" is a file.'.format(zip_file_path))

        # unzip
        zip_ref = zipfile.ZipFile(zip_file_path, 'r')
        zip_ref.extractall(to_dir)
        zip_ref.close()
    except BudHelperError:
        raise
    except Exception as ex:
        message = 'Failed to unzip file: %s \nto dir: %s.\nReason: %s'\
                  % (zip_file_path, to_dir, ex.message)
        print(message)
        raise BudHelperError(message)


def get_files_in_dir_by_type(dir_path, file_ext):
    """Get files of extension in directory."""
    included_extensions = [file_ext]
    file_names = [fn for fn in os.listdir(dir_path)
                  if any(fn.endswith(ext) for ext in included_extensions)]

    return file_names


def es_write_index(es_client, json_doc, current_index, id):
    """Writes json doc to the es domain with the provided index and id"""
    try:
        date_now = (datetime.datetime.now()).strftime('%Y-%m')
        current_index = current_index + "_" + date_now
        if es_client.indices.exists(index=current_index):
            es_client.index(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)), body=json_doc)
        else:
            es_client.create(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)), body=json_doc)
    except TransportError as e:
        raise ValueError("Problem in {} connection, Error is {}".format(es_client, e.message))


def delta_time(start_time):
    """
    Use datetime and total_second for delta from a start time stamp.

    returns a string like:  x.xxxx sec.

    :param start_time:
    :return: string with time in seconds for a delta.
    """
    end_time = datetime.datetime.now()
    delta_time = end_time - start_time
    return delta_time.total_seconds()


def print_delta_time(start_time, stage):
    """
    Prints the delta time from start_time into the aws lambda funtions log.
    Format is:  'TIMER <stage-comment>: <delta time> sec.'
    :param start_time:
    :param stage: The comment to append to front of timer log.
    :return: None
    """
    delta_time_str = delta_time(start_time)
    log_line = 'TIMER {}: {} sec.'.format(stage, delta_time_str)
    print(log_line)


def get_slack_bud_environment(params):
    """
    Return string 'dev' or 'prod' based on what is in the
    lambda functions: event[body][command]
    The lambda functions are named.
        '\buddev2' -> dev
        '\buddev' -> dev
        '\bud' -> prod
    :param params: params parameter
    :return: string 'dev' | 'prod'
    """
    # Infer the environment from the Slack Command name used.
    cmd_list = params.get('command')
    if cmd_list:
        slack_cmd_word = params['command'][0]
        # Found it within inputs.
        if slack_cmd_word.endswith('buddev2'):
            return 'dev2'
        elif slack_cmd_word.endswith('buddev'):
            return 'dev'
        elif slack_cmd_word.endswith('bud'):
            return 'prod'
        else:
            message = "Unexpected slack_cmd_word. Expect: " \
                      "('bud'|'buddev'|'buddev2'). Was: {}".format(slack_cmd_word)
            raise BudHelperError(message)
    else:
        # Or get name from lambda environment variable.
        lambda_function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME')
        if '-prod-' in lambda_function_name:
            return 'prod'
        elif '-dev-' in lambda_function_name:
            return 'dev'
        elif '-qa-' in lambda_function_name:
            return 'dev2'
        else:
            message = "Unexpected lambda function name. " \
                      "Expect: serverless-slackbud-dev-slackBud. " \
                      "Was: {}".format(lambda_function_name)
            raise BudHelperError(message)


def invoke_longtask_lambda(slack_bud_env, payload):
    """
    This is called from SlackBud's lambda funtion to start
    a task on the 'longtask' lambda function for that environment.
    It needs a to know the environment which is ( 'dev' | 'prod' )
    to find the right lambda function and the payload is a dictionary
    in a standard format for passing all the needed data to the
    remove system.

    If the env string has the wrong value this method throws a
    BudHelperError, (but is essentially a ValueError in Python).

    The payload isn't checked but if an error is caught the system
    will raise a BudHelperError
    :param slack_bud_env: string with values 'dev' | 'prod'
    :param payload: python dictionary in a standard SlackBud format for passing data.
    :return: True is successful. Throws an error if failed to launch.
    """
    try:
        # Check that env is either 'dev' or 'prod'
        if slack_bud_env == 'dev':
            lambda_function_name = 'slackbud-longtasks-dev'
        elif slack_bud_env == 'prod':
            lambda_function_name = 'slackbud-longtasks'
        else:
            message = "Invalid value for 'env'. Expect: ('dev'|'prod'). Was: {}".format(slack_bud_env)
            raise ValueError(message)

        print('(bud_helper_util debug) type(payload): {}'.format(type(payload)))

        if type(payload) == 'dict':
            payload_str = json.dumps(payload)
        else:
            # Assume other option is string
            payload_str = payload

        aws_util.invoke_remote_lambda(lambda_function_name, payload_str)

    except Exception as ex:
        raise BudHelperError(ex.message)


def log_traceback_exception(ex):
    """
    Helper class for logging exception.
    :param ex: python exception class
    :return: None
    """
    template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
    print(template.format(type(ex).__name__, ex.args))
    traceback_str = traceback.format_exc()
    print('Error traceback \n{}'.format(traceback_str))

def squash_token_print(message, event):
    """
    Print the params dict, but replace the slack token with XXXX
    :param message: The log message to print before the params
    :param event: The params or event dict
    :return: none
    """
    if 'body' in event.keys():
        save_token = event['body']
        event['body'] = re.sub("token=[^&]+&", "token=XXXX&", event['body'])
        print(message, ": {}".format(event))
        event['body'] = save_token
    elif 'token' in event.keys():
        save_token = event['token']
        event['token'] = 'XXXXX'
        print(message, ": {}".format(event))
        event['token'] = save_token