"""Implements Help command by asnyder"""
from __future__ import print_function

import imp
import os
import traceback

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface
from cmd_inputs import CmdInputs


class CmdHelp(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': [],
            'help_title': 'Get summary of all available commands',
            'permission_level': 'dev',
# {#sub_command_prop_methods#}
        }

        return props

# {#sub_command_prop_method_def#}


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
        # Get the inputs.
        cmd_inputs = self.get_cmd_input()
        if not cmd_inputs:
            raise ValueError('ERROR: no "cmd_inputs" found')

        print('run_command: cmd_inputs = {}'.format(cmd_inputs))

        # Get the sub-command.
        sub_command = cmd_inputs.get_sub_command()

        # Do the normal help command stuff.
        try:
            if sub_command == 'help':
                return self.show_command_help()

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))

            title = 'SlackBud Help'
            text = 'Available commands\n'
            # Walk though all of the Cmd* classes calling get_help_title().
            text += get_title_from_all_commands()
            text += 'for help with a specific command use: \n'
            text += '_/bud <command> help_\n'
            text += 'More info on confluence page: https://confluence.portal.roku.com:8443/display/SR/SR+Slack+BudE\n'

            return slack_ui_util.text_command_response(title, text, color='#ffaa60')

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

# {#invoke_command#}

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """
        return {}

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

def get_modules_from_cmds_package():
    module_extensions = ('.py', '.pyc', '.pyo')
    package_name = 'cmds'
    file, pathname, description = imp.find_module(package_name)
    if file:
        raise ImportError('Not a package: %r', package_name)
    # Use a set because some may be both source and compiled.
    return set([os.path.splitext(module)[0]
                for module in os.listdir(pathname)
                if module.endswith(module_extensions)])


def get_title_from_all_commands():
    ret_val = ''
    try:
        all_cmd_modules_set = get_modules_from_cmds_package()
        all_cmd_modules_list = list(all_cmd_modules_set)
        all_cmd_modules_list.sort()

        cmd_name_prefix = 'cmds_'
        for curr_module in all_cmd_modules_list:
            if curr_module.startswith(cmd_name_prefix):
                cmd_name = curr_module.replace(cmd_name_prefix, '')
                cmd_class_name = get_cmd_class_name(cmd_name)
                import_class = 'cmds.' + curr_module + '.' + cmd_class_name
                klass = import_class_from_name(import_class)

                cmd_inputs = CmdInputs()
                curr_title = klass(cmd_inputs).get_help_title()
                ret_val += '*{}:* {}\n'.format(cmd_name, curr_title)

    except Exception as ex:
        template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

        ret_val += 'Check logs for exception details\n'

    return ret_val


def get_cmd_class_name(cmd_name):
    """
    Convert from: spend_tag
    to: CmdSpend_Tag
    :param cmd_name: spend_tag
    :return: CmdSpend_Tag
    """
    temp = cmd_name.replace('_', ' ')
    temp = temp.title()
    temp = temp.replace(' ', '_')
    return 'Cmd' + temp


def import_class_from_name(import_class_package):
    """

    :param import_class_package: String in format: 'package.module.class'
    :return: class
    """
    print('import_class_package={}'.format(import_class_package))
    components = import_class_package.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_help_main():
    """
    Entry point for command unit tests.
    :return: True if tests pass False if they fail.
    """
    try:
        # Fill in any needed tests here.

        return True
    except Exception as ex:
        bud_helper_util.log_traceback_exception(ex)
        return False