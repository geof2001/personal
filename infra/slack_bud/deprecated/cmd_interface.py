"""Base class for commands."""
from __future__ import print_function

import json
from abc import ABCMeta, abstractmethod
import util.aws_util as aws_util


class CmdInterface:
    __metaclass__ = ABCMeta

    def __init__(self):
        self._response_url = ''

    def set_response_url(self, response_url):
        print('(debug) setting response_url={}'.format(response_url))
        self._response_url = response_url

    def get_response_url(self):
        print('(debug) return _response_url={}'.format(self._response_url))
        return self._response_url

    @abstractmethod
    def get_help_text(self): pass

    @abstractmethod
    def get_help_title(self): pass

    @abstractmethod
    def invoke_sub_command(self, sub_command, args,
                           response_url=None,
                           slack_channel=None,
                           raw_inputs=None,
                           user=None): pass

    @abstractmethod
    def invoke_confirm_command(self, params): pass

    @abstractmethod
    def invoke_longtask_command(self, event): pass

    # @abstractmethod
    # def is_confirm_command(self, params): pass

    # This method is used by implemented is_confirm_command
    def get_fallback_string_from_payload(self, params):
        """Returns a string put in by command to verify it is confirmation response."""
        if 'payload' in params:
            return json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']

    def set_fallback_value(self):
        """
        Is this method to define the fallback string used by the slack confirm process.

        :param self:
        :return: String which it fallback value for this class
        """
        return self.__class__.__name__

    def create_longtask_payload(self, args, custom_data=None):
        """
        Use this method to package data before passing to the long
        :param self:
        :param args:
        :param response_url:
        :param custom_data:
        :return:
        """
        if custom_data:
            payload = {
                'task': self.set_fallback_value(),
                'args': vars(args),
                'response_url': self.get_response_url(),
                'custom_data': custom_data
            }
        else:
            payload = {
                'task': self.set_fallback_value(),
                'args': vars(args),
                'response_url': self.get_response_url()
            }
        return payload

    def get_slack_bud_environment(self, args):
        """
        Return string 'dev' or 'prod'
        :param self:
        :param args:
        :return: string 'dev' | 'prod'
        """
        if args.slackbudisprod:
            return 'prod'
        else:
            return 'dev'
