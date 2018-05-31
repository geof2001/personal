"""Implements Build command by asnyder@roku.com"""
from __future__ import print_function

from datetime import datetime
import argparse
import urllib2
import logging
import boto3
import json
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

TOKEN = 'REGRESSIONISGOOD'
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
BUILD_METHODS = {'docker_build_V2': 'https://cidsr.eng.roku.com/view/Docker/job/docker-create-javaserver-image-v2/'}
LAMBDA = boto3.client('lambda')


class CmdBuild(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Builds the specified service. (Default branch: master)"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:*\n_/bud build -s <service>_\n_/bud build -s <service> " \
            "--branch <branch_name>_\n\nExample:\n_/bud " \
            "build -s content_\n_/bud build -s content --branch myBranch_\n\n\n"
        help_text += "`<history` _To check build history of the service_\n\n"
        help_text += "*<Flags>*\n"
        help_text += "`-s` - Service to show builds for. (Required)\n"
        help_text += "`-n` - Number of builds to show. (Default: 10)\n"
        help_text += "`-b` - Branch built against. (Default: all)\n\n"
        help_text += "Example: _/bud build history -s content -n 5 -b myBranch_\n\n\n"
        help_text += "*Build Diffs:*\n_/bud build diff <build1> <build2>_\n\nExample: \n_/bud "\
            "build diff master:1111-111-1111 master:2222-222-2222_"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, command_text, response_url,  user):
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
            '--num', '-n',
            default=10, type=int,
            help='Number of info to show')
        parser.add_argument(
            '--branch', '-branch', '-b',
            metavar='',
            help='Branch to build against')
        parser.add_argument(
            '--jira', '-jira', '-j',
            metavar='',
            default=False,
            help='If true, get JIRA task instead of commit difference')

        args, unknown = parser.parse_known_args(command_text.split())
        print('ARGS: %s' % args)

        try:
            if sub_command.strip() == 'help':
                return self.get_help_text()

            if sub_command.strip() == 'diff':
                return handle_diff_sub_command(args, response_url)

            # If no service flag was given
            if not args.services:
                text = 'A service was not specified. Use the flag ' \
                       '`-s` to specify one.'
                return slack_ui_util.error_response(text)

            # Exception for tfs-legacy and tfs-legacy-canary
            if args.services[0] == 'tfs-legacy' or args.services[0] == 'tfs-legacy-canary':
                args.services[0] = 'tfs'
            
            # Get DynamoDB service table for info
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': args.services[0]})

            # If service does not exist
            if 'Item' not in service:
                text = "Unable to build. Service `%s` does not exist in table " \
                       "*[ServiceInfo]*." % args.services[0]
                return slack_ui_util.error_response(text)

            # Handle History
            if sub_command.strip() == 'history':
                return handle_build_history(args)

            # Check if the service is buildable/has build info
            if 'build' not in service['Item']['serviceInfo']:
                text = 'Service `%s` is not buildable according to service_info.yaml.' \
                       % args.services[0]
                return slack_ui_util.error_response(text)

            # Determine build method and URL from table
            build_method = service['Item']['serviceInfo']['build']['method'] \
                if 'method' in service['Item']['serviceInfo']['build'] else ''
            build_url = BUILD_METHODS[build_method] if build_method in BUILD_METHODS else ''
            if not build_url:
                text = "Service `%s` does not have a build method/URL associated with it..." \
                       % args.services[0]
                return slack_ui_util.error_response(text)

            # If branch not specified, make it master
            if not args.branch:
                args.branch = 'master'

            # Handle builds based on their methods
            if build_method == 'docker_build_V2':
                full_build_url = '{url}buildWithParameters?token={token}' \
                                 '&BRANCH={branch}&SERVICE_NAME={service}' \
                                 '&TAGS={user}&RESPONSE_URL={response_url}' \
                    .format(url=build_url,
                            token=urllib2.quote(TOKEN),
                            branch=urllib2.quote(args.branch),
                            service=urllib2.quote(args.services[0]),
                            user=urllib2.quote(user),
                            response_url=response_url)
                LOGGER.info(full_build_url)
                urllib2.urlopen(full_build_url)
                text = "The build for `%s` has kicked off. Check ```%s``` to " \
                       "monitor it..." % (args.services[0], build_url)
                return slack_ui_util.text_command_response(None, text)

            # Error text
            text = "The build for `%s` failed to kicked off. Check ```%s``` to see " \
                   "why..." % (args.services[0], build_url)
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
            # This command doesn't have a confirm.
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
            elif fallback_str == CmdBuild.__class__.__name__:
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


def handle_diff_sub_command(args, response_url):
    jira = args.jira
    print("JIRA VALUE INSIDE FUNCTION {}".format(jira))
    try:
        if not jira:
            payload = {}
            build1 = args.command[2]
            build2 = args.command[3]
            print("Build1: {}".format(build1))
            print("Build2: {}".format(build2))
            payload = {
            "build1": build1,
            "build2": build2,
            "url": response_url,
            "jira": False,
            "task": 'builddiff'
            }
        else:
            payload = {}
            build1 = args.command[2]
            build2 = args.command[3]
            payload = {
            "build1": build1,
            "build2": build2,
            "url": response_url,
            "jira": True,
            "task": 'builddiff'
            }
        response = LAMBDA.invoke(
            FunctionName="slackbud-longtasks",
            InvocationType="Event",
            Payload=json.dumps(payload)
            )
        print(response)
        return slack_ui_util.respond(None,
            {
            "response_type": "ephemeral",
            "text":
                "*Work is in progress, Please wait for a moment.....*"
            }
            )
    except ValueError:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "in_channel",
                "text": "*Please check the build argumets ,provide "
                        "in `/bud build diff <build1> <build2> "
                        "--jira` format*"
            }
        )


def handle_build_history(args):
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
        try:
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
        except ShowSlackError:
            text = '%s builds do not exist with the specified filters. Lower the number.' % args.num
            return slack_ui_util.error_response(text)

    if search_list:
        title = 'Here are `%s` of the most recent build(s) for service `%s`' % (args.num, args.services[0])
    else:
        title = 'No builds can be found for service `%s` with specified input.' % args.services[0]
    text = output
    color = "#d77aff"
    return slack_ui_util.text_command_response(title=title, text=text, color=color)
