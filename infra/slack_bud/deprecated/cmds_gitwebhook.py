"""Implements Gitwebhook command by areynolds@roku.com"""
from __future__ import print_function

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface
from gitlab import Gitlab
import boto3

DYNAMODB = boto3.resource('dynamodb')
BUD_KEY_TABLE = DYNAMODB.Table('special')

class CmdGitwebhook(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Create a webhook for a project"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud gitwebhook <action> <hookname> -s <service>_\n"
        help_text += "*Available hooks:* _service_info_\n\n"
        help_text += "*<add>* _add a webhook to gitLab for service_\n"
        help_text += "*<remove>* _remove a webhook from gitLab for service_\n"
        help_text += "*<list>* _List hooks installed for service_\n"
        help_text += "*Example:* _/bud gitwebhook add service_info -s homescreen_\n\n"
        help_text += "*Example:* _/bud gitwebhook remove service_info -s homescreen_\n\n"
        help_text += "*Example:* _/bud gitwebhook list -s homescreen_\n"

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

            # If no service flag was given
            if not args.services:
                text = 'A service was not specified. Use the flag ' \
                       '`-s` to specify one.'
                return slack_ui_util.error_response(text)

            # Get DynamoDB service table for info
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': args.services[0]})

            # If service does not exist
            if 'Item' not in service:
                text = "Service `%s` does not exist in table " \
                       "*[ServiceInfo]*." % args.services[0]
                return slack_ui_util.error_response(text)

            git_repo = service['Item']['repo']

            print(args)
            # must have a web hook for add/remove commands
            if len(args.command) > 2:
                git_hook = args.command[2]
                git_hook_info = BUD_KEY_TABLE.get_item(Key={'name': git_hook})
                print("git_hook_info: ", git_hook_info)
                if 'Item' not in git_hook_info:
                    text = "Unknown webhook name"
                    return slack_ui_util.error_response(text)
            elif sub_command == 'add' or sub_command == 'remove':
                text = "Need to specify a web hook name"
                return slack_ui_util.error_response(text)

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            print("args: ", args)
            print("git_hook_info")

            # setup gitlab connection
            gitlab_key = BUD_KEY_TABLE.get_item(Key={'name': 'gitlab'})
            print("Gitlab Auth:", gitlab_key['Item']['data'])
            gl = Gitlab('https://gitlab.eng.roku.com/', gitlab_key['Item']['data'])
            gl.auth()

            if sub_command == 'add':
                return handle_add_command(args, git_repo, git_hook, gl, git_hook_info)
            if sub_command == 'remove':
                return handle_remove_command(args, git_repo, git_hook, gl, git_hook_info)
            if sub_command == 'list':
                return handle_list_command(args, git_repo, gl)
            title = 'Gitwebhook response'
            text = 'Hello from command Gitwebhook'
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


def handle_add_command(args, repo, hook, gl, info):
    """
    Add webhook
    :param info:
    :param gl:
    :param hook:
    :param repo:
    :param args:
    :return:
    """
    title = 'Gitwebhook add'
    text = "Would add a webhook\n"
    text += "repo: "
    text += repo
    text += "\nhook: "
    text += hook
    text += "\nURL: "
    text += info['Item']['url']
    # check if hook is already there

    project_name = 'SR/' + repo
    project = gl.projects.get(project_name)
    hooks = project.hooks.list()

    found_hook = False
    for hook in hooks:
        if info['Item']['url'] in hook.url:
            found_hook = True

    if found_hook:
            text += "\nhook already set\n"
    else:
        token = info['Item']['data']
        full_url = 'https://cidsr.eng.roku.com/project/' + info['Item']['url']
        new_hook = project.hooks.create(
            {'url': full_url,
             'push_events': 1,
             'token': token})
        text += "\nhook set\n"

    return slack_ui_util.text_command_response(title, text)


def handle_remove_command(args, repo, hook, gl, info):
    """
    remove webhook
    :param info:
    :param gl:
    :param hook:
    :param repo:
    :param args:
    :return:
    """
    title = 'Gitwebhook remove'
    text = "Would remove a webhook\n"
    text += "repo: "
    text += repo
    text += "\nhook: "
    text += hook

    project_name = 'SR/' + repo
    project = gl.projects.get(project_name)
    hooks = project.hooks.list()

    for hook in hooks:
        if info['Item']['url'] in hook.url:
            project.hooks.delete(hook.id)
            text += '\nhook deleted\n'

    return slack_ui_util.text_command_response(title, text)


def handle_list_command(args, repo, gl):
    """
    list webhooks
    :param gl:
    :param repo:
    :param args:
    :return:
    """
    title = 'Gitwebhook list'
    text = "Webhook URLs\n"
    project_name = 'SR/' + repo
    project = gl.projects.get(project_name)
    hooks = project.hooks.list()

    for hook in hooks:
        text += hook.url
        text += '\n'

    return slack_ui_util.text_command_response(title, text)
