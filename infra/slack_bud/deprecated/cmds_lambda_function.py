"""Entry point for all slack calls"""
import json
import logging
import os
import argparse
import traceback
from urlparse import parse_qs
import boto3
from deprecated.cmds_version import CmdVersion
from deprecated.cmds_props import CmdProps
from deprecated.cmds_backup import CmdBackup
from deprecated.cmds_canary import CmdCanary
from deprecated.cmds_help import CmdHelp
from deprecated.cmds_build import CmdBuild
from deprecated.cmds_user import CmdUser
from deprecated.cmds_gitwebhook import CmdGitwebhook
from deprecated.cmds_buildinfo import CmdBuildinfo
from deprecated.cmds_deploy import CmdDeploy
from deprecated.cmds_untagged import CmdUntagged
from deprecated.cmds_spend_tag import CmdSpend_Tag
from deprecated.cmds_show import CmdShow
from deprecated.cmds_flamegraph import CmdFlamegraph
from deprecated.cmds_test import CmdTest
from deprecated.cmds_service import CmdService
# {cmdimportline}
import util.aws_util as aws_util
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
from util.bud_helper_util import BudHelperError


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
    '--create',
    default=False, action='store_true',
    help='If true, create new property')
PARSER.add_argument(
    '--jira', '-jira', '-j',
    default=False, action='store_true',
    help='If true, get JIRA task instead of commit difference')
PARSER.add_argument(
    '--table', '-table', '-t',
    default=None,
    help='Use for backup command for a specific table')
PARSER.add_argument(
    '--slackbudisprod',
    default=True,
    help='True if prod, False if dev'
)
PARSER.add_argument(
    '--number', '--n', '-n', metavar='', nargs='*',
    default=10,help='numbers for commands'
)


STS = boto3.client('sts')
KMS = boto3.client('kms')
DYNAMODB = boto3.resource('dynamodb')
BUD_USERS_TABLE = DYNAMODB.Table('SlackBudUsers')
EXPECTED_TOKEN = os.environ['slackToken']

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
CURRENT = boto3.client('sts').get_caller_identity()
LOGGER.info('caller ID: %s' % CURRENT)

ENVIRONMENTS = aws_util.ENVIRONMENTS


def is_valid_token(params):
    """
    Verify the SlackToken which is included in environment of lambda function.

    :param params:
    :return: True if valid, otherwise False
    """
    token = params['token'][0]
    if token != EXPECTED_TOKEN:
        # Log what you can about this request.
        user_id = params['user_id'][0]
        user = params['user_name'][0]
        print("ERROR: Invalid token from user: {}\nuser_id: {}\ntoken: {}\nexpected: {}"
              .format(user, user_id, token, EXPECTED_TOKEN))
        return False
    return True


def is_valid_user(params, user_name, args):
    """
    Verify this a valid user_name for this command.
    If user_name is None automatically return False
    If user_name is not None look of this specific command to
    see if they have permissions to execute it.
    :param args:
    :param params:
    :param user_name: If is valid name of user. None if not valid.
    :return: True if a valid user, otherwise False
    """
    if user_name is None:
        return False
    # check if the user as the admin role for the listed commands.
    print("bud_user", user_name['userid'])
    print("bud_role", user_name['role'])
    command = args.command[0]
    if command in 'user gitwebhook' and user_name['role'] != 'admin':
        print("admin user running command:", command)
        return False

    return True


def look_up_bud_user(params):
    """
    Look-up userid in the BudUsers table.
    If found return the user name.
    :param params: params
    :return: return user name. If not found return None.
    """
    user_id = params['user_id'][0]
    response = BUD_USERS_TABLE.get_item(
        Key={
            'userid': user_id,
        }
    )

    if 'Item' not in response:
        # Log this user_id
        print("Invalid user_id: {}".format(user_id))
        return None
    return response['Item']


def get_subcommand_from_args(args):

    print('get_subcommand_from_args args: {}'.format(args))

    if args.command is not None:
        if len(args.command) > 1:
            subcmd = args.command[1]
            print('sub_command = {}'.format(subcmd))
            return subcmd

    return 'version'


def lambda_handler(event, context):
    """
    This is the entry point for the new version of lambda function.

    :param event: event from lambda function
    :param context: context from lambda function
    :return: Slack response
    """

    try:
        # Check for scheduled event which just keeps this lambda function active.
        if is_scheduled_event(event):
            return 'done'

        print("cmds_lambda_function Event: {}".format(event))

        params = parse_qs(event['body'])
        print("params: {}".format(params))

        # Check the payload signs of confirm command
        if 'payload' in params:
            fallback_value = get_fallback_value(params)
            print('Checking for confirmation command. fallback_value={}'
                  .format(fallback_value))
            if fallback_value:
                # If found invoke confirm command
                if fallback_value == 'CmdVersion':
                    return CmdVersion().invoke_confirm_command(params)
                if fallback_value == 'CmdProps':
                    return CmdProps().invoke_confirm_command(params)
                if fallback_value == 'CmdCanary':
                    return CmdCanary().invoke_confirm_command(params)
                if fallback_value == 'CmdHelp':
                    return CmdHelp().invoke_confirm_command(params)
                if fallback_value == 'CmdBuild':
                    return CmdBuild().invoke_confirm_command(params)
                if fallback_value == 'CmdUser':
                    return CmdUser().invoke_confirm_command(params)
                if fallback_value == 'CmdGitwebhook':
                    return CmdGitwebhook().invoke_confirm_command(params)
                if fallback_value == 'CmdBuildinfo':
                    return CmdBuildinfo().invoke_confirm_command(params)
                if fallback_value == 'CmdDeploy':
                    return CmdDeploy().invoke_confirm_command(params)
                if fallback_value == 'CmdUntagged':
                    return CmdUntagged().invoke_confirm_command(params)
                if fallback_value == 'CmdSpend_Tag':
                    return CmdSpend_Tag().invoke_confirm_command(params)
                if fallback_value == 'CmdShow':
                    return CmdShow().invoke_confirm_command(params)
                if fallback_value == 'CmdFlamegraph':
                    return CmdFlamegraph().invoke_confirm_command(params)
                if fallback_value == 'CmdTest':
                    return CmdTest().invoke_confirm_command(params)
                if fallback_value == 'CmdService':
                    return CmdService().invoke_confirm_command(params)
# {cmdconfirmsline}
            else:
                print("WARNING: Unrecognized payload fallback value: {}".format(fallback_value))
                return slack_ui_util.respond(
                    None,
                    {
                        "response_type": "ephemeral",
                        "text": "Unrecognized payload fallback value. Please check log."
                    }
                )

        # Verify the token.
        if not is_valid_token(params):
            text = "Invalid token. This request has been logged."
            return slack_ui_util.ephemeral_text_response(text)

        # Verify user (and in future verify they have permission for this command)
        bud_user = look_up_bud_user(params)
        if bud_user is None:
            text = "Invalid user. Ask an admin to add user to this this service."
            return slack_ui_util.ephemeral_text_response(text)

        # Parse the commands and parameters
        command_text = params['text'][0]
        user = params['user_name'][0]
        response_url = params['response_url'][0]
        args, unknown = PARSER.parse_known_args(command_text.split())
        convert_args_to_lower_case(args)

        log_inputs(args, command_text, bud_user, user, response_url)

        validate_args(args)
        determine_slack_environment(args, context)
        sub_command = get_subcommand_from_args(args)
        raw_inputs = ' '.join(command_text.split())

        if not is_valid_user(params, bud_user, args):
            text = "Sorry, I can't take orders from you. Ask an admin " \
                    "in SR team to be given permission to use this service."
            return slack_ui_util.ephemeral_text_response(text)

        # Invoke the sub command
        if args.command[0] == 'version':
            return CmdVersion().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'backup':
            return CmdBackup().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'props':
            return CmdProps().invoke_sub_command(sub_command, args, response_url)
        elif args.command[0] == 'canary':
            return CmdCanary().invoke_sub_command(sub_command, command_text, response_url,
                                                  raw_inputs=raw_inputs)
        elif args.command[0] == 'help':
            return CmdHelp().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'build':
            return CmdBuild().invoke_sub_command(sub_command, command_text, response_url,
                                                 user=user)
        elif args.command[0] == 'user':
            return CmdUser().invoke_sub_command(sub_command, args, response_url,
                                                raw_inputs=raw_inputs)
        elif args.command[0] == 'gitwebhook':
            return CmdGitwebhook().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'buildinfo':
            return CmdBuildinfo().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'deploy':
            return CmdDeploy().invoke_sub_command(sub_command, command_text, response_url,
                                                  raw_inputs=raw_inputs)
        elif args.command[0] == 'untagged':
            return CmdUntagged().invoke_sub_command(sub_command, args, response_url)
        elif args.command[0] == 'spend_tag':
            return CmdSpend_Tag().invoke_sub_command(sub_command, args)
        elif args.command[0] == 'show':
            return CmdShow().invoke_sub_command(sub_command, command_text)
        elif args.command[0] == 'flamegraph':
            return CmdFlamegraph().invoke_sub_command(sub_command, args, response_url)
        elif args.command[0] == 'test':
            return CmdTest().invoke_sub_command(sub_command, args, response_url)
        elif args.command[0] == 'service':
            return CmdService().invoke_sub_command(sub_command, command_text, response_url)
# {cmdswitchline}
        else:
            return slack_ui_util.respond(
                None,
                {
                    "response_type": "ephemeral",
                    "text": "The command is invalid. Please enter a valid command..."
                }
            )

    except BudHelperError as bhe:
        # Convert to a Slack Error Response.
        return slack_ui_util.error_response(bhe.message)
    except ShowSlackError as sse:
        return slack_ui_util.error_response(sse.message)
    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

        slack_error_message = 'An error occurred. Please check logs.'
        return slack_ui_util.error_response(slack_error_message)


def get_fallback_value(params):
    """
    The fallback value is the same as the class name as defined
    by the abstract base class.

    :param params:
    :return: string fallback value.
    """
    try:
        return json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']
    except Exception as ex:
        raise ShowSlackError('Failed to find fallback value. Reason: {}'.format(ex.message))


def log_inputs(args, command_text, bud_user, user, response_url):
    """
    Log the inputs and nothing else.
    :param args:
    :param command_text:
    :param bud_user:
    :param user:
    :param response_url:
    :return:
    """
    print('Command text: %s' % command_text)
    print('bud_user: %s' % bud_user)
    print('user: %s' % user)
    print('COMMAND: %s' % args.command)
    print('SERVICES: %s' % args.services)
    print('ENVS: %s' % args.envs)
    print('REGIONS: %s' % args.regions)
    print('RESPONSE_URL: %s' % response_url)
    print('JIRA: %s' % args.jira)
    print('Numbers: %s'%args.number)
    if args.table is not None:
        print('TABLE: %s' % args.table)


def determine_slack_environment(args, context):
    """
    Determine if this is prod or dev and set args accordingly.

    NOTE: We might eventually want a Singleton pattern to hold this
    state since environment needs to be determined before the
    confirmation commands.

    :param args: args is passed around to where needed to added here.
    :param context:
    :return: args with proper setting for args.
    """
    function_name = context.function_name

    print('(debug) context.function_name={}, type(args)={}'
          .format(function_name, type(args)))

    if 'dev' or 'qa' in function_name:
        args.slackbudisprod = False
    elif 'prod' in function_name:
        args.slackbudisprod = True
    else:
        print('ERROR failed to identify '
              'slack-bud environment based on fuction_name: {}'.format(function_name))
        raise ShowSlackError('SlackBud environment error. See logs')


def validate_args(args):
    """
    Validate args like env, and region.
    But throw an exception if they are wrong.

    :param args:
    :return: None or throw exception
    """
    if args.regions:
        if not aws_util.region_is_valid(args.regions[0]):
            raise ShowSlackError(
                'The region *[%s]* is not a valid AWS region.' % args.regions[0]
            )
    if args.envs:
        if not aws_util.env_is_valid(args.envs[0]):
            raise ShowSlackError(
                'The environment *[%s]* is not a valid environment.' % args.envs[0]
            )


def convert_args_to_lower_case(args):
    """Make some slack-bud arguments lower-case for better
    experience on mobile phones.

    The command, environment, region and service all convert
    to lower case. All other params keep original case.
    """
    # if args.command is not None:
    #     args.command = to_lower(args.command)
    if args.regions is not None:
        args.regions = to_lower(args.regions)
    if args.envs is not None:
        args.envs = to_lower(args.envs)
    if args.services is not None:
        args.services = to_lower(args.services)


def to_lower(arg_list):
    """Make all elements in list lower case"""
    lower_case_list = []
    for curr in arg_list:
        lower_case_list.append(curr.lower())
    return lower_case_list


def is_scheduled_event(event):
    """
    Events are sent by CloudWatch to keep the lambda function active
    and avoid start-up deploys after long idle periods.

    This method detects those events so they can be filtered from the logs.
    :param event: event from the lambda entry point
    :return: True if an Scheduled Event to keep lambda function active otherwise False
    """
    try:
        if type(event) is dict:
            key_list = list(event.keys())
            if 'detail-type' in key_list:
                detail_type = event['detail-type']
                if detail_type == 'Scheduled Event':
                    return True
        return False
    except Exception as ex:
        template = 'Failed at step "is_scheduled_event" type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
