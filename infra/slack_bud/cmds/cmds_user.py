"""Implements User command by asnyder"""
from __future__ import print_function
import re
import boto3

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

DYNAMODB = boto3.resource('dynamodb')
BUD_USERS_TABLE = DYNAMODB.Table('SlackBudUsers')

class CmdUser(CmdInterface):
    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['add', 'remove', 'list'],
            'help_title': 'Command (admin-only) for updating SlackBud users',
            'permission_level': 'admin',
            'props_add': self.get_add_properties(),
            'props_remove': self.get_remove_properties(),
            'props_list': self.get_list_properties()
        }
        return props

    def get_add_properties(self):
        """
        The properties for the "add" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<add>` add a new user and assign a role',
            'help_examples': [
                '/bud user add @areynolds dev',
                '*Note:* _requires admin role access_',
                '*Roles:* _dev and admin_'
            ],
            'switch-templates': []
        }
        return props

    def invoke_add(self, cmd_inputs):
        """
        Placeholder for "add" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_add")
            arg_item_2 = cmd_inputs.get_by_index(2)
            arg_item_3 = cmd_inputs.get_by_index(3)
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            userid = cmd_specific_data.get('userid')
            user_name = cmd_specific_data.get('user_name')

            # Start Add code section #### output to "text" & "title".

            text = ''
            if arg_item_2:
                text += 'user = {}\n'.format(arg_item_2)
            if arg_item_3:
                text += 'role = {}\n'.format(arg_item_3)
            if userid:
                text += 'userid = {}\n'.format(userid)
            if user_name:
                text += 'user_name = {}\n'.format(user_name)

            # Check the inputs.
            if not arg_item_2:
                raise ShowSlackError('need to specify a user and a role')
            if not arg_item_3:
                raise ShowSlackError('need to specify a role')
            user_role = arg_item_3
            if user_role not in 'dev admin':
                raise ShowSlackError('Unknown role. use dev or admin')

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

            # End Add code section. ####
        
            # Standard response below. Change title and text for output.
            title = "Add User"
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_remove_properties(self):
        """
        The properties for the "remove" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<remove>` remove an existing user',
            'help_examples': [
                '/bud user remove @areynolds'
            ],
            'switch-templates': []
        }
        return props

    def invoke_remove(self, cmd_inputs):
        """
        Placeholder for "remove" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_remove")
            arg_item_2 = cmd_inputs.get_by_index(2)
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            userid = cmd_specific_data.get('userid')
            user_name = cmd_specific_data.get('user_name')

            # Start Remove code section #### output to "text" & "title".
            text = ''
            if arg_item_2:
                text += 'user = {}\n'.format(arg_item_2)
            if userid:
                text += 'userid = {}\n'.format(userid)
            if user_name:
                text += 'user_name = {}\n'.format(user_name)

            # End Remove code section. ####
            title = 'User remove'
            text = "removing user\n"
            text += user_name
            BUD_USERS_TABLE.delete_item(
                Key={
                    'userid': userid
                }
            )
            # Standard response below. Change title and text for output.
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_list_properties(self):
        """
        The properties for the "remove" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<list>` list users',
            'help_examples': [
                '/bud user list'
            ],
            'switch-templates': []
        }
        return props

    def invoke_list(self, cmd_inputs):
        """
        Placeholder for "remove" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_list")

            # Start Remove code section #### output to "text" & "title".
            text = 'this is the list command.'
            # End Remove code section. ####
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
            # Standard response below. Change title and text for output.
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    # End Command's Properties section
    # ###################################
    # Start Command's implemented interface method section

    def run_command(self):
        """
        DON'T change this method. It should only be changed but the
        create_command, add_sub_command, and remove_sub_command scripts.

        In this method we look up the sub-command being used, and then the
        properties for that sub-command. It parses and validates the arguments
        and deals with invalid arguments.

        If the arguments are good. It next determines if this sub command
        needs to be invoked via the longtask lambda, or can run in (this)
        shorttask lambda. It then packages the arguments up properly and
        runs that command.

        :return: SlackUI response.
        """
        return self.default_run_command()

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """
        cmd_inputs = self.get_cmd_input()

        print('@build_cmd_specific_data cmd_inputs={}'.format(cmd_inputs))

        sub_command = cmd_inputs.get_sub_command()
        raw_inputs = cmd_inputs.get_raw_inputs()

        print("%s invokes %s" % (self.__class__.__name__, sub_command))
        print("raw_inputs", raw_inputs)

        if sub_command != 'list':
            m = re.search('<@(.*)\|(.*)> *(.*)$', raw_inputs)
            userid = m.group(1)
            user_name = m.group(2)

            cmd_specific_data = {
                'userid': userid,
                'user_name': user_name
            }

        else:
            cmd_specific_data = {}

        return cmd_specific_data

    def invoke_confirm_command(self):
        """
        Only fill out this section in the rare case your command might
        prompt the Slack UI with buttons ect. for responses.
        Most commands will leave this section blank.
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print('invoke_confirm_command')
            cmd_inputs = self.get_cmd_input()
            params = cmd_inputs.get_confirmation_params()
            callback_id = cmd_inputs.get_callback_id()
            print('callback_id = {}'.format(callback_id))

            # Start confirmation code section.
            # Callback Id convention is callback_<sub-command-name>_<anything>

            # Replace_example below.
            # if callback_id == 'callback_mysubcommand_prompt_env':
            #     return some_method_to_handle_this_case(params)
            # if callback_id == 'callback_mysubcommand_prompt_region':
            #     return some_other_method_to_handle_region(params)


            # End confirmation code section.
            # Default return until this section customized.
            title = 'Default invoke_confirm_command'
            text = 'Need to customize, invoke_confirm_command'
            return self.slack_ui_standard_response(title, text)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    # End class functions
# ###################################
# Start static helper methods sections

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."


def test_cases_cmd_user_main():
    """
    Entry point for command unit tests.
    :return: True if tests pass False if they fail.
    """
    try:
        # Test the regex parsing.
        raw_input_1 = 'user add <@U1RGUPMHA|someuser> dev'
        m = re.search('<@(.*)\|(.*)> *(.*)$', raw_input_1)
        userid = m.group(1)
        user_name = m.group(2)
        print('userid = {}'.format(userid))
        print('user_name = {}'.format(user_name))

        return True
    except Exception as ex:
        bud_helper_util.log_traceback_exception(ex)
        return False


if __name__ == '__main__':
    #  test methods below.
    test_cases_cmd_user_main()
