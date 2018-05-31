"""Gets the slack-bud version."""
from __future__ import print_function

import os
import util.slack_ui_util as slack_ui_util
from cmd_interface import CmdInterface


class CmdVersion(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Get the version of SlackBud"

    def get_help_text(self):
        help_text = "*Format:* _/bud version_"
        help_text += "*Example:* _/bud version_"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args):
        return handle_version()

    def invoke_confirm_command(self, params):
        """Confirm is never invoked from version."""
        return None

    def is_confirm_command(self, params):
        return False

    def invoke_longtask_command(self, event):
        """
        Put longtask command stuff here.
        :param event:
        :return:
        """
        # Temp just to not break build.
        return None


def handle_version():
    """Read and return the contents of build_info.txt"""
    try:
        if os.path.isfile('./build_info.txt'):
            f = open('build_info.txt', 'r')
            file_text = f.read()
            return slack_ui_util.text_command_response(
                title='Version',
                text=file_text
            )
        else:
            return slack_ui_util.text_command_response(
                title='Version',
                text='No version information found.'
            )
    except IOError as ex:
        return slack_ui_util.error_response('%s' % ex.message)
