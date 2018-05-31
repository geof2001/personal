"""Implements Spend_Tag command by asnyder@roku.com"""
from __future__ import print_function

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdSpend_Tag(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Kinesis Spend_Category tagger - SRINFRA-686"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud spend_tag <action> -e <env> -r <region>_\n"
        help_text += "*Example:* _/bud spend_tag add -e dev -r us-east-1 -s <kinesis-name> -t <tag_value>_\n\n"
        help_text += "*Example:* _/bud spend_tag list -e dev -r us-east-1 _\n\n"
        help_text += "*<a>* _Add puts the Spend_Category tags on a Kinesis stream_\n"
        help_text += "           _This is to tag Kinesis Firehose streams_\n"
        help_text += "           _See: SRINFRA-686_\n"
        help_text += "*<b>* _List all a Kinesis Stream names_\n"

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

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            if sub_command == 'add':
                # You need to modify this
                return handle_add_command(args)  # Adjust as needed
            if sub_command == 'list':
                # You need to modify this
                return handle_list_command(args)  # Adjust as needed
            title = 'Spend_Tag response'
            text = 'Hello from command Spend_Tag'
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


def handle_add_command(args):
    """
    Adds a tag to a Kinesis stream.
    :param args:
    :return:
    """
    env = args.envs[0]
    region = args.regions[0]
    stream_name = args.services[0]
    tag_value = args.table

    if stream_name:
        if tag_value:
            session = aws_util.create_session(env)
            kinesis_client = aws_util.get_boto3_client_by_name('kinesis', session, region)

            kinesis_client.add_tags_to_stream(
                StreamName=stream_name,
                Tags={
                    'Spend_Category': tag_value
                }
            )

            text = "Tagged Kinesis Name: {} with Spend_Category={}".format(stream_name, tag_value)
        else:
            text = "*Error* Need to specify Spend_Category tag value with *-t* switch"


    else:
        text = "*Error* Need to specific a Kinesis Name with *-s* switch"
    title = 'Spend_Tag Add response'
    return slack_ui_util.text_command_response(title, text)


def handle_list_command(args):
    """
    Lists tags on a Kinesis stream.
    :param args:
    :return:
    """
    env = args.envs[0]
    region = args.regions[0]

    session = aws_util.create_session(env)
    kinesis_client = aws_util.get_boto3_client_by_name('kinesis', session, region)

    text = 'List of Kinesis names\n'
    last_stream_name = None
    while True:
        if not last_stream_name:
            response = kinesis_client.list_streams()
        else:
            response = kinesis_client.list_streams(
                ExclusiveStartStreamName=last_stream_name
            )
        stream_name_list = response['StreamNames']
        for curr_name in stream_name_list:
            text += '  {}\n'.format(curr_name)
            last_stream_name = curr_name

        if not response['HasMoreStreams']:
            break
        else:
            print('Building stream list. Last stream: {}'.format(last_stream_name))

    title = 'Spend_Tag List response'
    return slack_ui_util.text_command_response(title, text)
