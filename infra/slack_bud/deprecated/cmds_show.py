"""Implements Show command by qzhong@roku.com"""
from __future__ import print_function

import argparse
import boto3
from datetime import datetime
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

ENVIRONMENTS = aws_util.ENVIRONMENTS


class CmdShow(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Shows information based on specified input."

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud show <data> <params> -s <service> -e <env> -r <region>_\n\n"
        help_text += "`<builds` _Shows the specified # of most recent builds for the service_\n\n"
        help_text += "*<Flags>*\n"
        help_text += "`-s` - Service to show builds for. (Required)\n"
        help_text += "`-n` - Number of builds to show. (Default: 10)\n"
        help_text += "`-b` - Branch to build against. (Default: master)\n\n"
        help_text += "Example: _/bud show builds -s content -n 5 -b myBranch_\n\n"
        help_text += "`<deploys>` _Shows the specified # of most recent deploys for the service_\n\n"
        help_text += "*<Flags>*\n"
        help_text += "`-s` - Service to show deploys for. (Required)\n"
        help_text += "`-n` - Number of deploys to show. (Default: 10)\n"
        help_text += "`-e` - Environment filter of deploys.\n"
        help_text += "`-r` - Region filter of deploys.\n"
        help_text += "`-c` - If flag is used, show only deploys creating change sets. (Default: False)\n\n"
        help_text += "Example: _/bud show deploys -s content -n 5 -e dev -r us-east-1 -c_\n\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, command_text, response_url=None, slack_channel=None):
        """
        Return help text for your command in slack format here.
        """
        # Argument Parser Configuration
        parser = argparse.ArgumentParser(description='Parses show command input')
        parser.add_argument(
            'command', metavar='', default=None, nargs='*',
            help='The command before the flags')
        parser.add_argument(
            '--services', '--service', '-s',
            metavar='', default=None, nargs='*',
            help='qa, dev, prod')
        parser.add_argument(
            '--envs', '--env', '-e',
            metavar='', default=None, nargs='*',
            help='qa, dev, prod')
        parser.add_argument(
            '--regions', '--region', '-r',
            metavar='', nargs='*',
            help='AWS Region(s)')
        parser.add_argument(
            '--num', '-n',
            default=10, type=int,
            help='Number of info to show')
        parser.add_argument(
            '--branch', '-branch', '-b',
            metavar='',
            help='Branch to build against')
        parser.add_argument(
            '--changeset', '-c',
            default=False, action='store_true',
            help='If true, display changeset')
        args = parser.parse_args(command_text.split())
        print('ARGS: %s' % args)

        try:
            if sub_command == 'help':
                return self.get_help_text()
            print("%s invokes %s" % (self.__class__.__name__, sub_command))

            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': args.services[0]})

            # If specified service not in table
            if 'Item' not in service:
                error_text = 'The specified service does not exist in table `ServiceInfo`.'
                return slack_ui_util.error_response(error_text)
            if sub_command == 'builds':
                # You need to modify this
                return handle_show_builds(args)  # Adjust as needed
            if sub_command == 'deploys':
                # You need to modify this
                return handle_show_deploys(args)  # Adjust as needed
            text = 'Please enter something valid to show. Use _/bud show help_ to see a list of commands.'
            return slack_ui_util.error_response(text)

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def invoke_confirm_command(self, params):
        """
        Return help text for your command in slack format here.
        """
        try:
            # This section is for working with confirm
            # ToDo: Provide a simple working example.
            return None

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def is_confirm_command(self, params):
        """
        Return help text for your command in slack format here.
        """
        try:
            fallback_str = self.get_fallback_string_from_payload(params)
            if fallback_str is None:
                return False
            elif fallback_str == self.__class__.__name__:
                return True
            return False

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return False

    def invoke_longtask_command(self, event):
        """
        Put longtask command stuff here.
        :param event:
        :return:
        """
        # Temp just to not break build.
        return None

    def set_fallback_value(self):
        return self.__class__.__name__


def handle_show_builds(args):
    """
    Shows the most recent builds of specified service.
    :param args: Flags inputted by user.
    :return:
    """

    # Setup ES client
    es_client = aws_util.setup_es()

    branch = " AND gitbranch.keyword:\"%s\"" % args.branch if args.branch else ''

    # ES query
    query = {
        "query": {
            "query_string": {
                "query": "service.keyword:\"%s\"" % args.services[0] + branch
            }
        }
    }
    search = es_client.search(
        index='build*',
        body=query,
        sort=['buildtime:desc'],
        size=args.num
    )

    search_list = search['hits']['hits']
    output = ''

    for build in search_list:
        date = datetime.strptime(build['_source']['buildtime'], '%Y-%m-%dT%H:%M:%S')
        date = date.strftime('%b %d, %Y - %I:%M:%S %p')
        image_name = build['_source']['dockertag']
        job_number = image_name.split('-')[-1]
        output += '```Build #%s   (%s)```\n' % (job_number, date)
        output += '`Image`  -  _%s_\n' % image_name
        output += '`Git Repo`  -  _%s_\n' % build['_source']['gitrepo']
        output += '`Git Author`  -  _%s_\n' % build['_source']['gitauthor']
        output += '`Git Commit Hash`  -  _%s_\n' % build['_source']['gitcommit']
        output += '`Repository`  -  _%s_\n' % str(build['_source']['repositories'][0])
        output += '`Unit Tests Passed`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['passed']
        output += '`Unit Tests Failed`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['failed']
        output += '`Unit Tests Skipped`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['skipped']

    if search_list:
        title = 'Here are the past `%s` build(s) for service `%s`' % (args.num, args.services[0])
    else:
        title = 'No builds can be found for service `%s` with specified input.' % args.services[0]
    text = output
    color = "#d77aff"
    return slack_ui_util.text_command_response(title=title, text=text, color=color)


def handle_show_deploys(args):
    """
    Shows the most recent deploys of specified service.
    :param args: Flags inputted by user.
    :return:
    """

    # Setup ES client
    es_client = aws_util.setup_es()

    changeset_val = 'true' if args.changeset else 'false'

    env = " AND environment:\"%s\"" % ENVIRONMENTS[args.envs[0]] if args.envs else ''
    region = " AND region:\"%s\"" % args.regions[0] if args.regions else ''
    changeset = " AND changeset:\"%s\"" % changeset_val

    # ES query
    query = {
        "query": {
            "query_string": {
                "query": "service.keyword:\"%s\"" % args.services[0] + env + region + changeset
            }
        }
    }
    search = es_client.search(
        index='deploy*',
        body=query,
        sort=['deploy_time:desc'],
        size=args.num
    )

    search_list = search['hits']['hits']
    output = ''

    for deploy in search_list:
        date = datetime.strptime(deploy['_source']['deploy_time'], '%Y-%m-%dT%H:%M:%S')
        date = date.strftime('%b %d, %Y - %I:%M:%S %p')
        image_name = deploy['_source']['image_name'].split(':')[1]
        job_number = deploy['_source']['deploy_job_number']
        environment = deploy['_source']['environment']
        output += '```Deploy #%s   (%s)```\n' % (job_number, date)
        output += '`Image`  -  _%s_\n' % image_name
        output += '`Environment`  -  _%s_\n' % ENVIRONMENTS.keys()[ENVIRONMENTS.values().index(environment)]
        output += '`Region`  -  _%s_\n' % deploy['_source']['region']
        output += '`Change Set`  -  _%s_\n' % deploy['_source']['changeset']
        output += '`CF Status`  -  _%s_\n' % str(deploy['_source']['cf_status']) \
            if 'cf_status' in deploy['_source'] else '`CF Status`  -  _?_\n'
        output += '`Deploy User`  -  _%s_\n' % deploy['_source']['userID']

    if search_list:
        title = 'Here are the past `%s` deploy(s) for service `%s`' % (args.num, args.services[0])
    else:
        title = 'No deploys can be found for service `%s` with specified input.' % args.services[0]
    text = output
    color = "#d77aff"
    return slack_ui_util.text_command_response(title=title, text=text, color=color)
