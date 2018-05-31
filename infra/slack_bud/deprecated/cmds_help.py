"""Implements Top Level Help command by areynolds@roku.com"""
from __future__ import print_function
import sys
import imp
import os
import inspect
import traceback

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdHelp(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Get summary of all available commands"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text  = "*Format:* _/bud help_\n"
        help_text += "*Example:* _/bud help_\n\n"

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

            title = 'SlackBud Help'
            text = 'Available commands\n'
            # Walk though all of the Cmd* classes calloing get_help_title().
            text += get_title_from_all_commands()
            text += 'for help with a specific command use: \n'
            text += '_/bud <command> help_\n'
            text += 'More info on confluence page: https://confluence.portal.roku.com:8443/display/SR/SR+Slack+BudE\n'

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

        for curr_module in all_cmd_modules_list:
            if curr_module.startswith('cmds_'):
                cmd_name = curr_module.replace('cmds_','')
                cmd_class_name = get_cmd_class_name(cmd_name)
                import_class = 'cmds.'+curr_module+'.'+cmd_class_name
                klass = import_class_from_name(import_class)
                curr_title = klass().get_help_title()
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
    return 'Cmd'+temp


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
