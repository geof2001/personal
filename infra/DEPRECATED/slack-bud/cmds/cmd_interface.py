"""Base class for commands."""
from __future__ import print_function

import json
import abc
import bud_helper_util

ENVIRONMENTS = bud_helper_util.ENVIRONMENTS


class CmdInterface(abc.ABC):
    """Interface for commands to implement"""
    def __init__(self, cmd_name, sub_command_list):
        self.cmd_name = cmd_name
        self.sub_command_list = sub_command_list

    def __str__(self):
        return "%s has sub_commands: %s" % (self.cmd_name, self.sub_command_list)

    @abc.abstractmethod
    def get_help_text(self): pass

    @abc.abstractmethod
    def invoke_sub_command(self, sub_command, args, response_url=None): pass

    @abc.abstractmethod
    def invoke_confirm_command(self, type, params): pass

    @abc.abstractmethod
    def is_confirm_command(self, params): pass

    # This method is used by implemented is_confirm_command
    def get_fallback_string_from_payload(self, params):
        """Returns a string put in by command to verify it is confirmation response."""
        if 'payload' in params:
            return json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']