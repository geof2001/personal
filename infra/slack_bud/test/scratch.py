import logging
import json
import traceback
import argparse
import test.unit_tests as unit_tests


# ToDo move some of this into a unit test.

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Build Update Deploy Service Tool')
PARSER.add_argument(
    'command', metavar='', default=None, nargs='*',
    help='The command')
PARSER.add_argument(
    '--services', '--service', '-s',
    metavar='', default=None, nargs='*',
    help='qa, dev, prod')
PARSER.add_argument(
    '--envs', '--env', '-e',
    metavar='', default=None, nargs='*',
    help='qa, dev, prod')
PARSER.add_argument(
    '--regions', '--region', '-r',
    default=['us-east-1'], metavar='', nargs='*',
    help='AWS Region(s)')
PARSER.add_argument(
    '--table', '-table', '-t',
    default=None,
    help='Use for backup command for a specific table')

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def main_test_make_lower_case():
    """Do some testing for converting commands to lower case"""
    test_command_text('backup list -e dev -r us-East-1')
    test_command_text('backup list -e Dev -r us-West-2')
    test_command_text('test -r us-West-2 -t TableName -e Dev')


def test_command_text(command_text):
    print('TESTING == %s ==' % command_text)
    args = PARSER.parse_args(command_text.split())
    print('REGIONS: %s' % args.regions)
    print('ENVS: %s' % args.envs)
    print('TABLE: %s' % args.table)
    convert_args_to_lower_case(args)
    print('REGIONS: %s' % args.regions)
    print('ENVS: %s' % args.envs)
    print('TABLE: %s' % args.table)
    print(' ')


def convert_args_to_lower_case(args):
    """Convert some of the args into lower case
    to work with auto-correcting mobile devices
    """
    if args.regions is not None:
        args.regions = to_lower(args.regions)
    if args.envs is not None:
        args.envs = to_lower(args.envs)


def to_lower(arg_list):
    """Make all elements in list lower case"""
    lower_case_list = []
    for curr in arg_list:
        lower_case_list.append(curr.lower())
    return lower_case_list

def main_test_grep_read_from_file():
    """Test that GREP give expected results reading from file."""
    try:
        score_lines = grep(
            'pylint_output.txt',
            'code has been rated at'
        )

        print('%s' % score_lines)
        print('score_lines is type: %s' % type(score_lines))
        num_lines = len(score_lines)
        print('num_line=%s' % num_lines)
        if num_lines > 0:
            last_score = score_lines[num_lines-1]
            if type(last_score) is str:
                print("get_score_from_pylint() last_score: %s" % last_score)
                parts = last_score.strip().split()
                parts_len = len(parts)
                if parts_len > 0:
                    print('%s' % parts[parts_len-1])
                    return parts[parts_len-1]
            else:
                print('last_score is type: %s' % type(last_score))
                print('last_score=%s' % (last_score,))
    except Exception as ex:
        print('Failed to get pylint score for reason: %s' % ex.message)


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


def test_common_longtask_payload():
    try:
        args = {
            'env': 'dev',
            'region': 'us-west-2',
            'slackbudisprod': False
        }

        response_url = 'http://long-asdfasf.slack.com/something/someid'

        use_case_1_data = {
            'stack_name': 'some-cf-stack',
            'cf_images': ['one', 'two', 'three'],
            'boolean': False
        }

        payload1 = create_longtask_payload(args, response_url)
        json_payload1 = json.dumps(payload1)

        unpack_longtask_payload(json_payload1)

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))



def create_longtask_payload(args, response_url, custom_data=None):
    """
    Testing a common longtask payload
    :param args:
    :param response_url:
    :param custom_data: dictionary with custom data.
    :return: payload
    """
    if custom_data:
        payload = {
            'args': args,
            'response_url': response_url,
            'custom_data': custom_data
        }
    else:
        payload = {
            'args': args,
            'response_url': response_url
        }
    return payload


def unpack_longtask_payload(json_payload):
    """
    Try to unpack it the same way as lambda invoke function.
    :param json_payload:
    :return:
    """
    print('unpack: {}'.format(json_payload))


def parse_docker_ps_output(output, image_match):
    """
    Parse the output of docker ps
    :param output:
    :return:
    """
    output = output.replace('CONTAINER ID', 'CONTAINER_ID')
    lines = output.split('\n')

    container_id_list = []
    image_list = []
    names_list = []
    for curr_line in lines:
        columns = curr_line.split()
        col_len = len(columns)
        if col_len > 3:
            container_id_list.append(columns[0])
            image_list.append(columns[1])
            last_col = col_len-1
            names_list.append(columns[last_col])

    i = 0
    for curr_id in container_id_list:
        print('{}: {}  | {}'.format(curr_id, image_list[i], names_list[i]))
        i += 1

    # look for a particular image.


# Below is what a typical output looks like for the docker ps command.
# Will need to parse this output.
# -
# CONTAINER ID        IMAGE                                                                                 COMMAND                  CREATED             STATUS              PORTS                                              NAMES
# 7bb53c1a6d54        638782101961.dkr.ecr.us-east-1.amazonaws.com/search:master-b80d756-20180307-6584      "/usr/local/bin/ru..."   14 minutes ago      Up 14 minutes       0.0.0.0:32775->7199/tcp, 0.0.0.0:32774->8080/tcp   ecs-search-SearchTaskDefinition-FGAMVW774DHY-1-search-de87a4a2cad5a7a25200
# ffae32edc4a8        amazon/amazon-ecs-agent:latest                                                        "/agent"                 2 days ago          Up 2 days                                                              ecs-agent
# 611f6aaa2372        638782101961.dkr.ecr.us-east-1.amazonaws.com/gateway:master-c469f1b-20170926-4570     "/usr/local/bin/ru..."   2 days ago          Up 2 days           80/tcp, 443/tcp, 7199/tcp, 9000/tcp                gateway
# c8d9f89ff354        638782101961.dkr.ecr.us-east-1.amazonaws.com/registrar:master-5879535-20170814-4023   "/usr/local/bin/ru..."   2 days ago          Up 2 days           7199/tcp, 8080/tcp                                 registrar
# 6b9bf514ef1f        638782101961.dkr.ecr.us-east-1.amazonaws.com/x-ray:xray-2x-20171018-7                 "/usr/bin/xray-dae..."   2 days ago          Up 2 days           0.0.0.0:2000->2000/udp                             xray

def test_parser_methods():
    """
    Test the parser
    :return:
    """
    output = "CONTAINER ID        IMAGE                                                                                 COMMAND                  CREATED             STATUS              PORTS                                              NAMES\n"
    output += '7bb53c1a6d54        638782101961.dkr.ecr.us-east-1.amazonaws.com/search:master-b80d756-20180307-6584      "/usr/local/bin/ru..."   14 minutes ago      Up 14 minutes       0.0.0.0:32775->7199/tcp, 0.0.0.0:32774->8080/tcp   ecs-search-SearchTaskDefinition-FGAMVW774DHY-1-search-de87a4a2cad5a7a25200\n'
    output += 'ffae32edc4a8        amazon/amazon-ecs-agent:latest                                                        "/agent"                 2 days ago          Up 2 days                                                              ecs-agent\n'
    output += '611f6aaa2372        638782101961.dkr.ecr.us-east-1.amazonaws.com/gateway:master-c469f1b-20170926-4570     "/usr/local/bin/ru..."   2 days ago          Up 2 days           80/tcp, 443/tcp, 7199/tcp, 9000/tcp                gateway\n'
    output += 'c8d9f89ff354        638782101961.dkr.ecr.us-east-1.amazonaws.com/registrar:master-5879535-20170814-4023   "/usr/local/bin/ru..."   2 days ago          Up 2 days           7199/tcp, 8080/tcp                                 registrar\n'
    output += '6b9bf514ef1f        638782101961.dkr.ecr.us-east-1.amazonaws.com/x-ray:xray-2x-20171018-7                 "/usr/bin/xray-dae..."   2 days ago          Up 2 days           0.0.0.0:2000->2000/udp                             xray\n'

    parse_docker_ps_output(output)


def validate_run_time_value(run_time_in_sec):
    """
    If the value is None, or not valid number set it to the
    default value of 20 seconds.

    For valid numbers enforce a
    min of 10 seconds
    and a max of 60 seconds

    :param run_time_in_sec:
    :return: integer between 10 and 60 seconds.
    """
    DEFAULT_RUN_TIME = 20
    MIN_TIME_IN_SEC = 10
    MAX_TIME_IN_SEC = 60

    try:
        if isinstance(run_time_in_sec, (int, long, float)):
            if run_time_in_sec < MIN_TIME_IN_SEC:
                return MIN_TIME_IN_SEC
            elif run_time_in_sec > MAX_TIME_IN_SEC:
                return MAX_TIME_IN_SEC
            else:
                return int(run_time_in_sec)
        else:
            # Is this a string that can be a number?
            int_value = int(run_time_in_sec)
            return validate_run_time_value(int_value)
    except Exception:
        print('Setting {} to default {} sec.'.format(run_time_in_sec, DEFAULT_RUN_TIME))
        return DEFAULT_RUN_TIME


def test_run_time_validation():

        valid_list = [-1, 0, 9, 10, 11, 30, 59, 60, 61, 10000000000]
        for item in valid_list:
            record_test_result(item)

        invalid_list = [None, 'asdfa', 2.3, 10.0, 9.9, 59.999, 60.0001,
                        '10', '9', '-1', '61', '2+2', '1.3e2'
                        'NaN', '', '-iNF', 'infinity', (1), [1],
                        [1,2], {'a':1}]
        for invalid in invalid_list:
            record_test_result(invalid)


def record_test_result(value):
    try:
        print('in: {}'.format(value))
        out = validate_run_time_value(value)
        print('out: {}\n'.format(out))
    except Exception as ex:
        print('ERROR: {}'.format(ex))


# ##########  This section is about testing Arg Parsing related stuff    ##########

def example_cmd_properity():

    cmd_prop = {
        'sub_commands': ["create", "list", ""],
        'help_title': 'This command is for testing the refactoring'
    }

    return cmd_prop


def example_cmd_create_property():

    cmd_create_property = {
        'run-type': 'longtask',
        'help_text': '*Create* simulates argument',
        'switch-templates': ['region', 'env', 'service'],
        'switch-t': {
            'aliases': ['time'],
            'required': False,
            'valid_types': 'int',
            'help_text': 'time to profile'
        },
        'switch-p':{
            'aliases': ['partition', 'part'],
            'required': True,
            'valid_type': 'string',
            'valid_values': ['dev', 'qa', 'prod'],
            'help_text': 'partition in something'
        }
    }

    return cmd_create_property


def create_payload_res():
    payload_res = {
        'body': {
            'text': 'SlackBud Help',
            'response_type': 'in_channel',
            'attachments': [{
                'color': '#a0ffaa',
                'text': 'Avail cmds\nA\B',
                'mrkdwn_in': ['text']
            }]
        },
        'headers': {
            'Content-Type': 'application/json'
        },
        'statusC0de': 200
    }


def test_get_items():

    cmd_prop_dict = example_cmd_create_property()

    print('type(cmd_prop_dict) = {}'.format( type(cmd_prop_dict) ))
    valid_types =  cmd_prop_dict['switch-t']['help_text']

    print('valid_types = {}'.format(valid_types))

    cmd_prop_dump = json.dumps(cmd_prop_dict)
    print('type(cmd_prop_dump) = {}'.format(type(cmd_prop_dump)))

    # See if we can turn this into a dictionary.
    cmd_prop_back_to_dict = json.loads(cmd_prop_dump)
    print('type(cmd_prop_back_to_dict) = {}'.format(type(cmd_prop_back_to_dict)))

    valid_types2 = cmd_prop_back_to_dict['switch-t']['help_text']
    print('type(valid_types2) = {}'.format(type(valid_types2)))
    print('valid_types2 = {}'.format(valid_types2))


def scratch_test():
    try:
        t1 = {
            'A': 'no key'
        }
        t2 = {
            'PaginationToken': '',
            'A': 'empty string'
        }
        t3 = {
            'PaginationToken': 'asdfasdfasd',
            'A': 'has key'
        }

        if 'PaginationToken' in t1:
            pt1 = t1['PaginationToken']
            if not pt1:
                print('a1')
            if pt1 is None:
                print('a2')
        else:
            print("t1 doesn't have key")

        if 'PaginationToken' in t2:
            pt2 = t2['PaginationToken']
            if not pt2:
                print('b1')
            if pt2 is None:
                print('b2')

        if 'PaginationToken' in t3:
            pt3 = t3['PaginationToken']
            if not pt3:
                print('c1')
            if pt3 is None:
                print('c2')
            if pt3:
                print('pt3 has token: {}'.format(pt3))

        pt4 = None
        if pt4:
            print("d1")
        if not pt4:
            print("d2")

    except Exception as ex:
        template = 'Failed during get_tagged_resource_list. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))


def test_unit_test_call():
    try:
        unit_tests.main()
    except Exception as ex:
        template = 'Failed during get_tagged_resource_list. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

# #################################################################################


if __name__ == '__main__':
    # test_common_longtask_payload()
    # test_parser_methods()
    # test_run_time_validation()
    # test_get_items()
    test_unit_test_call()
