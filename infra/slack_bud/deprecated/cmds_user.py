"""
Implements the User command by areynolds
This manages the Slack_bud authorized users.

"""
from __future__ import print_function

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface
import re
import boto3

DYNAMODB = boto3.resource('dynamodb')
BUD_USERS_TABLE = DYNAMODB.Table('SlackBudUsers')

class CmdUser(CmdInterface):
    """
        class CmdUser
    """

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Command (admin-only) for updating SlackBud users"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud user <action> <slack_user_ID> <role>_\n"
        help_text += "*Note:* _requires admin role access_\n"
        help_text += "*Roles:* _dev and admin_\n\n"
        help_text += "*add* _add a new user and assign a role_\n"
        help_text += "*remove* _remove an existing user_\n\n"
        help_text += "*Example:* _/bud user add @areynolds dev_\n\n"
        help_text += "*Example:* _/bud user remove @areynolds_\n\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args, response_url, raw_inputs):
        """
        Return help text for your command in slack format here.
        """
        try:
            if sub_command == 'help':
                return self.get_help_text()

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            print("raw_inputs", raw_inputs)

            if sub_command != 'list':
                m = re.search('<@(.*)\|(.*)> *(.*)$', raw_inputs)
                userid = m.group(1)
                user_name = m.group(2)

            if sub_command == 'add':
                r = raw_inputs.split(' ')
                if len(r) == 4:
                    user_role = r[3]
                    if user_role not in 'dev admin':
                        title = 'User'
                        text = 'Unknow role. use dev or admin'
                        return slack_ui_util.text_command_response(title, text)
                else:
                    title = 'User'
                    text = 'need to specify a role'
                    return slack_ui_util.text_command_response(title, text)
                return handle_add_command(userid, user_name, user_role)

            if sub_command == 'remove':
                return handle_remove_command(userid, user_name)

            if sub_command == 'list':
                return handle_list_command()

            title = 'User'
            text = 'add or remove Slack_bud users and set their role'
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


def handle_add_command(userid, user_name, user_role):
    """
    Add user to bud users
    :param user_role:
    :param userid:
    :param user_name:
    :return:
    """
    title = 'User add'
    text = "adding user:\n"
    text += user_name
    text += '\n'
    text += user_role
    BUD_USERS_TABLE.put_item(
        Item={
            'userid': userid,
            'role': user_role,
            'username': user_name
        }
    )
    return slack_ui_util.text_command_response(title, text)


def handle_remove_command(userid, user_name):
    """
    Remove user from bud users

    :param userid: Slack userID
    :param user_name: Slack user name
    :type userid: string
    :type user_name: string
    :return: Slack Text Response

    """
    title = 'User remove'
    text = "removing user\n"
    text += user_name
    BUD_USERS_TABLE.delete_item(
        Key={
            'userid': userid
        }
    )
    return slack_ui_util.text_command_response(title, text)

def handle_list_command():
    """
    List bud users
    :return: Slack response text
    """
    title = 'User List'
    text = "User Role\n"
    table_data = BUD_USERS_TABLE.scan()
    print(table_data)
    text += "Number of Users: "
    text += str(table_data['Count'])
    text += '\n'
    for item in table_data['Items']:
        text += item['username']
        text += ' '
        text += item['role']
        text += '\n'
    return slack_ui_util.text_command_response(title, text)
