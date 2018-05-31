"""Entry point for all slack calls"""
import json
import logging
import os
import re
import urllib2
import argparse
from urlparse import parse_qs
import boto3
import cmd.props as props
import cmd.build as build
import cmd.build_info as build_info
import cmd.canary as canary
import cmd.dns as dns
import cmd.gitdiff as gitdiff
import cmd.version as version
import cmd.deploy as deploy
import cmd.update as update
import cmd.test_trigger as test_trigger
import cmd.backup as backup
import slack_ui_util
import bud_helper_util


# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Build Update Deploy Service Tool')
PARSER.add_argument(
    'command', metavar='', default=None, nargs='*',
    help='The command')
PARSER.add_argument(
    '--services', '--service', '-s',
    metavar='', default=None, nargs='*',
    help='qa, dev, stg, prod')
PARSER.add_argument(
    '--envs', '--env', '-e',
    metavar='', default=None, nargs='*',
    help='qa, dev, stg, prod')
PARSER.add_argument(
    '--regions', '--region', '-r',
    default=['us-east-1'], metavar='', nargs='*',
    help='AWS Region(s)')
PARSER.add_argument(
    '--create',
    default=False, action='store_true',
    help='If true, create new property')
PARSER.add_argument(
    '--branch', '-branch',
    metavar='', default='master',
    help='Branch to build against')
PARSER.add_argument(
    '--jira', '-jira', '-j',
    default=False, action='store_true',
    help='If true, get JIRA task instead of commit difference')
PARSER.add_argument(
    '--table', '-table', '-t',
    default=None,
    help='Use for backup command for a specific table')
PARSER.add_argument(
    '--version', '-version', '-v',
    default=None,
    help='Version of service image to deploy')


STS = boto3.client('sts')
KMS = boto3.client('kms')
DYNAMODB = boto3.resource('dynamodb')
BUD_USERS_TABLE = DYNAMODB.Table('SlackBudUsers')
EXPECTED_TOKEN = os.environ['slackToken']

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
CURRENT = boto3.client('sts').get_caller_identity()
LOGGER.info('caller ID: %s' % CURRENT)

ENVIRONMENTS = bud_helper_util.ENVIRONMENTS


def handle_deploy(bud_user, user_name, command):
    """Deploy command."""
    if command not in ENVIRONMENTS:
        text = "Sorry, account %s is not supported." % command
        return slack_ui_util.error_response(text)
    deploy_url =\
        '{url}buildWithParameters?token={token}' \
        '&GIT_BRANCH={branch}' \
        '&AWS_ACCOUNTS={accounts}&TAGS={user}'\
        .format(
            url=os.environ['jenkinsUrl'],
            token=os.environ['jenkinsToken'],
            branch="master",
            accounts=ENVIRONMENTS[command],
            user=user_name)
    LOGGER.info(deploy_url)
    response = urllib2.urlopen(deploy_url)
    html = response.read()
    LOGGER.info(html)
    return slack_ui_util.respond(
        None,
        {
            "response_type": "ephemeral",
            "text": "Deploying to %s" % command,
            "attachments": [
                {
                    "text": html
                }]
        }
    )


def handle_add_user(bud_user, command):
    """Add_user command."""
    m = re.search('^<@(.*)\|(.*)> *(.*)$', command)
    userid = m.group(1)
    user_name = m.group(2)
    role = m.group(3)
    LOGGER.info(bud_user)
    LOGGER.info("Adding user %s with role %s" % (userid, role))
    if bud_user['role'] != "admin":
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "Sorry, you need to be an admin to use this command."
            }
        )

    if not role:
        role = "dev"
    BUD_USERS_TABLE.put_item(
        Item={
            'userid': userid,
            'role': role,
            'username': user_name
        }
    )
    return slack_ui_util.respond(
        None,
        {
            "response_type": "ephemeral",
            "text": "User <@%s|%s> was added with role %s"
                    % (userid, user_name, role)
        }
    )


def handle_remove_user(bud_user, command):
    """Remove user command."""
    m = re.search('^<@(.*)\|(.*)>.*$', command)
    userid = m.group(1)
    user_name = m.group(2)
    LOGGER.info(bud_user)
    LOGGER.info("Removing user %s (%s)" % (userid, user_name))
    if bud_user['role'] != "admin":
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "Sorry, you need to be an admin to use this command."
            }
        )

    BUD_USERS_TABLE.delete_item(
        Key={
            'userid': userid
        }
    )
    return slack_ui_util.respond(
        None,
        {
            "response_type": "ephemeral",
            "text": "User <@%s|%s> was removed" % (userid, user_name)
        }
    )


def lambda_handler(event, context):
    """Module entry point for lambda functions."""
    LOGGER.info(event)
    params = parse_qs(event['body'])

    if 'payload' in params and \
            json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback'] == 'Properties':
        return props.props_confirm(params, ENVIRONMENTS)

    if 'payload' in params and \
            json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback'] == 'Deploy':
        return deploy.deploy_confirm(params)

    if 'payload' in params and \
            json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback'] == 'Update':
        return update.update_confirm(params)

    if 'payload' in params and \
            json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback'] == 'DNS':
        LOGGER.info("Doing DNS update")
        return dns.dns_confirm(params, ENVIRONMENTS)

    elif 'payload' in params:
        fallback = json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']
        LOGGER.warn("Unrecognized payload fallback value: %s" % fallback)
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "Unrecognized payload fallback value. Please check log."
            }
        )

    token = params['token'][0]
    if token != EXPECTED_TOKEN:
        LOGGER.error("Request token (%s) does not match expected", token)
        return slack_ui_util.respond(Exception('Invalid request token'))

    response = BUD_USERS_TABLE.get_item(
        Key={
            'userid': params['user_id'][0],
        }
    )

    if 'Item' not in response:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "Sorry, I can't take orders from you. Ask an "
                        "admin in SR team to be given permission to use this service."
            }
        )

    bud_user = response['Item']
    command_text = params['text'][0]
    user = params['user_name'][0]
    response_url = params['response_url'][0]
    args = PARSER.parse_args(command_text.split())
    convert_args_to_lower_case(args)

    LOGGER.info('COMMAND: %s' % args.command)
    LOGGER.info('SERVICES: %s' % args.services)
    LOGGER.info('ENVS: %s' % args.envs)
    LOGGER.info('REGIONS: %s' % args.regions)
    LOGGER.info('RESPONSE_URL: %s' % response_url)
    LOGGER.info('JIRA: %s' % args.jira)
    if args.table is not None:
        LOGGER.info('TABLE: %s' % args.table)

    # to remove extra space entered by user
    command_text = ' '.join(command_text.split())
    commands = command_text.split(' ')
    if len(commands) == 1 and args.command[0] != 'version':
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "Please check command format."
            }
        )
    else:
        cmd = " ".join(commands[1:])

    if args.regions:
        if not bud_helper_util.region_is_valid(args.regions[0]):
            return slack_ui_util.error_response(
                'The region *[%s]* is not a valid AWS region.' % args.regions[0]
            )
    if args.envs:
        if not bud_helper_util.env_is_valid(args.envs[0]):
            return slack_ui_util.error_response(
                'The environment *[%s]* is not a valid environment.' % args.envs[0]
            )

    if args.command[0] == 'add_user':
        return handle_add_user(bud_user, cmd)
    elif args.command[0] == 'remove_user':
        return handle_remove_user(bud_user, cmd)
    elif args.command[0] == 'canary':
        return canary.handle_canary_deploy()
    elif args.command[0] == 'deploy':
        return deploy.handle_deploy(cmd, args, response_url, command_text)
    elif args.command[0] == 'update':
        return update.handle_update(cmd)
    elif args.command[0] == 'props':
        return props.handle_props(cmd, ENVIRONMENTS, args, response_url)
    elif args.command[0] == 'buildinfo':
        return build_info.handle_build_info(cmd)
    elif args.command[0] == 'build':
        return build.handle_build(cmd, args, user, response_url)
    elif args.command[0] == 'dns':
        return dns.handle_dns(cmd, ENVIRONMENTS, args, params)
    elif args.command[0] == 'backup':
        return backup.handle_dynamo_backup(cmd, ENVIRONMENTS, args, params)
    elif args.command[0] == 'builddiff':
        return gitdiff.handle_git_diff(cmd, response_url, args)
    elif args.command[0] == 'smoketest':
        return test_trigger.handle_test_trigger(cmd, response_url, args)
    elif args.command[0] == 'version':
        return version.handle_version()
    else:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text": "The command is invalid. Please enter a valid command..."
            }
        )

    command = params['command'][0]
    channel = params['channel_name'][0]

    return respond(
        None,
        {
            "response_type": "ephemeral",
            "text": "%s invoked %s in %s with the following text: %s"
                    % (user, command, channel, command_text),
            "attachments": [
                {
                    "text": "Will now take action on the command..."
                }
            ]
        }
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
