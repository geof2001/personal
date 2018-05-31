"""Gets the slack-bud version."""
from __future__ import print_function

import os
import slack_ui_util


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
