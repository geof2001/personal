"""Implements Buildinfo command by asnyder@roku.com"""
from __future__ import print_function

import datetime
import logging
import boto3
from elasticsearch import Elasticsearch, \
    RequestsHttpConnection, TransportError
from requests_aws_sign import AWSV4Sign
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

# Please put your elastic host here
# ES_HOST = \
#     "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
ES_HOST = \
    "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"


class ES:
    """ElasticSearch methods"""
    def __init__(self, host):
        session = boto3.session.Session()
        credentials = session.get_credentials()
        region = session.region_name
        service = 'es'
        auth = AWSV4Sign(credentials, region, service)
        self.logger = logging.getLogger()
        try:
            self.es_client = Elasticsearch(
                host=host, port=443,
                connection_class=RequestsHttpConnection,
                http_auth=auth, use_ssl=True, verify_ssl=True
            )
        except TransportError as e:
            raise ValueError(
                "Problem in {} connection, Error is {}".format(host, e.message)
            )

    def get_data_commit(self, id):
        date_now = (datetime.datetime.now()).strftime('%Y-%m')
        current_index = "build_" + date_now
        data = self.es_client.get(index=current_index, doc_type='_all', id=id)
        git_commit = data.get("_source").get("gitcommit", None)
        return git_commit

    def get_data_repo(self, id):
        date_now = (datetime.datetime.now()).strftime('%Y-%m')
        current_index = "build_" + date_now
        data = self.es_client.get(index=current_index, doc_type='_all', id=id)
        repo = data.get("_source").get("gitrepo", None)
        return repo

    def get_data(self, id):
        try:
            date_now = (datetime.datetime.now()).strftime('%Y-%m')
            current_index = "build_" + date_now
            data = self.es_client.get(index=current_index, id=id, doc_type='_all')
            print(data.get("coverage"))
            repo = data.get("_source").get("repositories", None)
            author = data.get("_source").get("gitauthor", None)
            service = data.get("_source").get("service", None)
            git_commit = data.get("_source").get("gitcommit", None)
            build_time = data.get("_source").get("buildtime", None)
            git_repo = data.get("_source").get("gitrepo", None)
            passed = data.get("_source").get("coverage")\
                .get("unittestcases").get("passed")
            failed = data.get("_source").get("coverage")\
                .get("unittestcases").get("failed")
            skipped = data.get("_source").get("coverage")\
                .get("unittestcases").get("skipped")
            line = int(data.get("_source").get("coverage")
                       .get("coverage").get("line"))
            class_cov = int(data.get("_source").get("coverage")
                            .get("coverage").get("class"))
            branch = int(data.get("_source").get("coverage")
                         .get("coverage").get("branch"))
            instruction = int(data.get("_source").get("coverage")
                              .get("coverage").get("instruction"))
            slack_data = {
                "response_type": "ephemeral",
                "text": "*Build information of build* : `{}`".format(id),
                "attachments": [
                    {
                        "text": "*Repository*: `{}`".format(repo),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Author*: `{}`".format(author),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Service*: `{}`".format(service),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*GIT Commit*: `{}`".format(git_commit),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Build time*: `{}`".format(build_time),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*GIT Repo*: `{}`".format(git_repo),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Passed*: `{}`".format(passed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Failed*: `{}`".format(failed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Unittest Case Skipped*: `{}`".format(skipped),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Line Code Coverage*: *`{}%`*".format(line),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Class Code Coverage*: *`{}%`*".format(class_cov),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Branch Code Coverage*: *`{}%`*".format(branch),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Instruction Code Coverage*:"
                            " *`{}%`*".format(instruction),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    }
                ]
            }
            return slack_ui_util.respond(None, slack_data)

        except TransportError as e:
            return slack_ui_util.respond(e)
            # raise ValueError(
            #     "Can not get data with id: {} on index: {}, error is {}"
            #         .format(id, current_index, e)
            # )


class CmdBuildinfo(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Get the build info for a project"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud buildinfo <action> <service>:<docker-build>_\n"
        help_text += "*Example:* _/bud buildinfo content:master-58b0f67-20180215-20054_\n\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args, response_url=None, slack_channel=None):
        """
        Return help text for your command in slack format here.
        """
        try:
            if sub_command == 'help':
                return self.get_help_text()

            print("%s invokes %s" % (self.__class__.__name__, sub_command))

            es = ES(ES_HOST)
            id = str(sub_command)
            return es.get_data(id)

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


def handle_a_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    title = 'Buildinfo response'
    text = "this is sub-command A"
    return slack_ui_util.text_command_response(title, text)


def handle_b_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    title = 'Buildinfo response'
    text = "this is sub-command B"
    return slack_ui_util.text_command_response(title, text)
