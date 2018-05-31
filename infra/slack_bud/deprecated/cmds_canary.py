"""Implements Canary command by jscott@roku.com"""
####################################################
from __future__ import print_function

import os
import requests
import argparse
import logging
import json
import time
import boto3
import urllib2
from objdict import ObjDict
import pendulum
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

ENVIRONMENTS = aws_util.ENVIRONMENTS
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
TOKEN = 'REGRESSIONISGOOD'
ES_HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
DEPLOY_METHODS = {
    'CF_deploy_V1': 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-canary-service/'
}
DATADOG_HEALTH_URL = 'https://app.datadoghq.com/dash/669562/' \
                     'sr-service-health?live=true&page=0&is_auto=false&tile_size=m'
# Accounts Map
ACCOUNTS = {"dev": "638782101961",
            "qa": "181133766305",
            "prod": "886239521314",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-prod": "prod"}

class CmdCanary(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Create a canary for a project"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text  = "*Formats:* _/bud canary <action> -e <env> -r <region>_\n"
        help_text += "*Example:* _/bud canary deploy -s content -e dev -r us-east-1_\n\n"
        help_text += "*Example:* _/bud canary release -s content -e dev -r us-east-1_\n\n"
        help_text += "*<deploy>* _deploy a canary for the specified service\n"
        help_text += "           deploy -s <servicename> \n"
        help_text += "*<history>* _show the history of canaries deployed for service \n"
        help_text += "           history -s <servicename> \n"
        help_text += "*<release>* _release the canary from service_\n"
        help_text += "           release -s <servicename> \n\n\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
            )

    def invoke_sub_command(self, sub_command, command_text, response_url, raw_inputs):
        """
        Return help text for your command in slack format here.
        """

        # Argument Parser Configuration
        parser = argparse.ArgumentParser(description='Parses show command input')
        parser.add_argument(
            'command', metavar='', default=None, nargs='*',
            help='The command before the flags')
        parser.add_argument(
            '--service', '-s',
            metavar='', default=None, help='qa, dev, prod')
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
            '--version', '-version', '-v',
            default=None,
            help='Version of service image to deploy')
        
        args, unknown = parser.parse_known_args(command_text.split())
        print('ARGS: %s' % args)
        try:
            if sub_command.strip() == 'help':
                return self.get_help_text()

            # environments = self.ENVIRONMENTS

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            
            if sub_command == 'deploy':
                return handle_deploy_command(args)
                
            if sub_command == 'release':
                return handle_release_command(args)
            
            title = 'Canary response'
            text = 'Hello from command Canary'
            return slack_ui_util.text_command_response(title, text)

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
            elif fallback_str == 'SomeString':
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

def handle_deploy_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    es_client = aws_util.setup_es()

    deploy_event = ObjDict()
    
    deploytime = pendulum.now('US/Pacific').strftime("%Y%m%d-%H:%M:%S")
    deploy_event.eventCategory = args.command[0]
    deploy_event.time = deploytime
    deploy_event.eventType = args.command[1]
    
    deploy_event.serviceName = args.service
    deploy_event.version = args.version
    deploy_event.region = args.regions
    deploy_event.environment = args.envs
    # deploy_event.duration = completedTime - deploytime
    
    record_event = es_client.index(index="canary", doc_type="event", id = 1, body=deploy_event)

    print(record_event)
    
    title = 'Deploy response for `%s` canary of build `%s`' % (args.service, args.version)
    text = "this is sub-command A"
    return slack_ui_util.text_command_response(title, text)


def handle_release_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    title = 'Canary for service `%s` running build `%s` is being released' % (args.services[0], args.build)
    # text = "this is sub-command B"
    text = handle_param_fetch('gitlab.eng.roku.com')
    return slack_ui_util.text_command_response(title, text)

def handle_show_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    title = 'History of canary deploys for service `%s`' % (args.services[0])
    # text = "this is sub-command B"
    text = handle_param_fetch('gitlab.eng.roku.com')
    return slack_ui_util.text_command_response(title, text)

def handle_param_fetch(pName):
    #test gitlab up with ping
    response = requests.get('https://' + pName)
    if response.status_code == 200:
        pingstatus = "Network is Good"
    else:
        pingstatus = "Network has Error"
    return pingstatus