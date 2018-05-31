"""Implements Gitwebhook command by asnyder"""
from __future__ import print_function
import traceback
from gitlab import Gitlab
import boto3

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

DYNAMODB = boto3.resource('dynamodb')
BUD_KEY_TABLE = DYNAMODB.Table('special')

class CmdGitwebhook(CmdInterface):

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
            'help_title': 'Create a webhook for a project',
            'permission_level': 'dev',
            'props_add': self.get_add_properties(),
            'props_remove': self.get_remove_properties(),
            'props_list': self.get_list_properties()
# {#sub_command_prop_methods#}
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
            'help_text': '*Add* add a webhook to gitLab for service',
            'help_examples': [
                '/bud gitwebhook add service_info -s homescreen'
            ],
            'switch-templates': ['service']
        }
        return props

    def invoke_add(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_add")
            region = cmd_inputs.get_by_key('region')  # remove if not used
            env = cmd_inputs.get_by_key('env')  # remove if not used
            service = cmd_inputs.get_by_key('service')  # remove if not used
            # Put Add code below.
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            git_repo = cmd_specific_data.get("git_repo")
            git_hook = cmd_specific_data.get("git_hook")
            gl = cmd_specific_data.get("gl")
            git_hook_info = cmd_specific_data.get("git_hook_info")

            title = 'Gitwebhook add'
            text = "Would add a webhook\n"
            text += "repo: "
            text += git_repo
            text += "\nhook: "
            text += git_hook
            text += "\nURL: "
            text += git_hook_info['Item']['url']
            # check if hook is already there

            project_name = 'SR/' + git_repo
            project = gl.projects.get(project_name)
            hooks = project.hooks.list()

            found_hook = False
            for hook in hooks:
                if git_hook_info['Item']['url'] in hook.url:
                    found_hook = True

            if found_hook:
                text += "\nhook already set\n"
            else:
                token = git_hook_info['Item']['data']
                full_url = 'https://cidsr.eng.roku.com/project/' + git_hook_info['Item']['url']
                new_hook = project.hooks.create(
                    {'url': full_url,
                     'push_events': 1,
                     'token': token})
                text += "\nhook set\n"

            # Optional response below. Change title and text as needed.
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
            'help_text': '*Remove* remove a webhook from gitLab for service',
            'help_examples': [
                '/bud gitwebhook remove service_info -s homescreen'
            ],
            'switch-templates': ['service']
        }
        return props

    def invoke_remove(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_remove")
            service = cmd_inputs.get_by_key('service')  # remove if not used
            # Put Remove code below.
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            git_repo = cmd_specific_data.get("git_repo")
            git_hook = cmd_specific_data.get("git_hook")
            gl = cmd_specific_data.get("gl")
            git_hook_info = cmd_specific_data.get("git_hook_info")

            title = 'Gitwebhook remove'
            text = "Would remove a webhook\n"
            text += "repo: "
            text += git_repo
            text += "\nhook: "
            text += git_hook

            project_name = 'SR/' + git_repo
            project = gl.projects.get(project_name)
            hooks = project.hooks.list()

            for hook in hooks:
                if git_hook_info['Item']['url'] in hook.url:
                    project.hooks.delete(hook.id)
                    text += '\nhook deleted\n'

            # Optional response below. Change title and text as needed.
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_list_properties(self):
        """
        The properties for the "list" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*List* List hooks installed for service',
            'help_examples': [
                '/bud gitwebhook list -s homescreen'
            ],
            'switch-templates': ['service'],
        }
        return props

    def invoke_list(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_list")
            service = cmd_inputs.get_by_key('service')
            # Put List code below.
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            git_repo = cmd_specific_data.get("git_repo")
            gl = cmd_specific_data.get("gl")

            title = 'Gitwebhook list'
            text = "Webhook URLs\n"
            project_name = 'SR/' + git_repo
            project = gl.projects.get(project_name)
            hooks = project.hooks.list()

            for hook in hooks:
                text += hook.url
                text += '\n'

            # Optional response below. Change title and text as needed.
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")
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
        return self.default_run_command()

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """
        # Get DynamoDB service table for infod
        cmd_inputs = self.get_cmd_input()
        sub_command = cmd_inputs.get_sub_command
        service_arg = cmd_inputs.get_by_key('service')

        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': service_arg})

        # If service does not exist
        if 'Item' not in service:
            text = "Service `%s` does not exist in table " \
                   "*[ServiceInfo]*." % service_arg
            # return slack_ui_util.error_response(text)
            raise ShowSlackError(text)

        git_repo = service['Item']['repo']

        print(cmd_inputs)
        # must have a web hook for add/remove commands
        args_command_2 = cmd_inputs.get_by_index(3)
        arg_after_sub_command = cmd_inputs.get_by_index(2)
        # if len(args.command) > 2:
        git_hook = None
        git_hook_info = None
        if not arg_after_sub_command.startswith('-'):
            git_hook = args_command_2
            git_hook_info = BUD_KEY_TABLE.get_item(Key={'name': git_hook})
            print("git_hook_info: ", git_hook_info)
            if 'Item' not in git_hook_info:
                text = "Unknown webhook name"
                # return slack_ui_util.error_response(text)
                raise ShowSlackError(text)
        elif sub_command == 'add' or sub_command == 'remove':
            text = "Need to specify a web hook name"
            # return slack_ui_util.error_response(text)
            raise ShowSlackError

        print("%s invokes %s" % (self.__class__.__name__, sub_command))
        print("cmd_inputs: ", cmd_inputs)
        print("git_hook_info")

        # setup gitlab connection
        gitlab_key = BUD_KEY_TABLE.get_item(Key={'name': 'gitlab'})
        print("Gitlab Auth:", gitlab_key['Item']['data'])
        gl = Gitlab('https://gitlab.eng.roku.com/', gitlab_key['Item']['data'])
        gl.auth()

        cmd_specific_data_dict = {
            'git_repo': git_repo,
            'git_hook': git_hook,
            'gl': gl,
            'git_hook_info': git_hook_info
        }

        print('cmd_specific_data = {}'.format(cmd_specific_data_dict))

        return cmd_specific_data_dict

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

    def invoke_longtask_command(self, cmd_inputs):
        """
        This is part of the interface for the longtask, but it might be possible
        to combine with invoke(). ...
        :param cmd_inputs:
        :return:
        """
        try:
            response_url = cmd_inputs.get_response_url()

            # Remove the ones not used.
            region = cmd_inputs.get_by_key('region')
            env = cmd_inputs.get_by_key('env')
            service = cmd_inputs.get_by_key('service')

            # Start command code.

            # End command code.

        except ShowSlackError as sse:
            slack_error_message = str(sse)
            return slack_ui_util.error_response(
                slack_error_message, post=True, response_url=response_url)
        except Exception as ex:
            # Report back an error to the user, but ask to check logs.
            template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
            print(template.format(type(ex).__name__, ex.args))
            traceback_str = traceback.format_exc()
            print('Error traceback \n{}'.format(traceback_str))

            slack_error_message = 'An error occurred (lt). Please check logs.'
            return slack_ui_util.error_response(
                slack_error_message, post=True, response_url=response_url)

# {#invoke_methods_section#}

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_gitwebhook_main():
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