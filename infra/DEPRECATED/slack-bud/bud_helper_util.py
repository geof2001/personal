"""Utility class with helper methods for bud commands.

This class depends on aws_util, but it agnostic of the UI.
Exceptions caught need to be converted into UI format and
passed back to the user.
"""
from __future__ import print_function

import zipfile
import os.path
import boto3
import aws_util



AWS_REGIONS = [
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2',
    'ca-central-1',
    'eu-west-1',
    'eu-west-2',
    'eu-central-1',
    'sa-east-1',
    'ap-south-1',
    'ap-northeast-1',
    'ap-northeast-2',
    'ap-southeast-1',
    'ap-southeast-2']

ENVIRONMENTS = {
    "dev": '638782101961',
    "qa": '181133766305',
    "stg": '610352865374',
    "prod": '886239521314'}


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
        session = aws_util.get_session(ENVIRONMENTS, env_param)
    except:
        raise BudHelperError('No environment')
    if region_param not in AWS_REGIONS:
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
            if dic['OutputKey'] == '%sPropertiesTable' % service.capitalize():
                index = i
                break

        props_table = stack_description['Stacks'][0]['Outputs'][index]['OutputValue']
        return props_table

    except:
        raise BudHelperError(
            'Failed to find Property table for stack: %s in region: %s' %
            (stack_name, region)
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

    print('Unzip verifying path: %s' % zip_file_path)
    # Verify zip file
    if not os.path.isfile(zip_file_path):
        message = 'Unzip failed to verify file: %s' % zip_file_path
        print(message)
        raise BudHelperError(message)

    try:
        # unzip
        zip_ref = zipfile.ZipFile(zip_file_path, 'r')
        zip_ref.extractall(to_dir)
        zip_ref.close()
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


def region_is_valid(region):
    """Check if the region is valid."""
    if region not in AWS_REGIONS:
        return False
    return True


def env_is_valid(env):
    """Check if the env is valid."""
    if env not in ENVIRONMENTS:
        return False
    return True
