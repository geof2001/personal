"""Implements Buildinfo command by asnyder"""
from __future__ import print_function

import datetime
import logging
import boto3
from elasticsearch import Elasticsearch, \
    RequestsHttpConnection, TransportError
from requests_aws_sign import AWSV4Sign

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface



class CmdBuildinfo(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['_default_'],
            'help_title': 'Get the build info for a project',
            'permission_level': 'dev',
            'props__default_': self.get__default__properties()
# {#sub_command_prop_methods#}
        }

        return props


    def get__default__properties(self):
        """
        The properties for the "_default_" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`Type <service>:<docker-build>',
            'help_examples': [
                '/bud buildinfo master-58b0f67-20180215-20054'
            ],
            'switch-templates': []
        }
        return props

    def invoke__default_(self, cmd_inputs):
        """
        Placeholder for "_default_" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke__default_")
            arg_item_data = cmd_inputs.get_by_index(2)

            if 'help' in arg_item_data:
                title = "buildinfo help"
                text = ""
                text += "`/bud buildinfo <docker-build>`"
                text += "\n\n"
                text += "`/bud buildinfo master-58b0f67-20180215-20054`"
                return self.slack_ui_standard_response(title, text)

            response_url = cmd_inputs.get_response_url()
        
            # Start _Default_ code section #### output to "text" & "title".
            print("%s invokes %s" % (self.__class__.__name__, arg_item_data))

            # Setup ES client
            es_client = aws_util.setup_es()

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": "dockertag.keyword:\"{}\"".format(arg_item_data)
                    }
                }
            }

            search = es_client.search(
                index='build*',
                body=query,
                sort=['buildtime:desc'],
            )
            data = ""
            try:
                data = search.get('hits').get('hits')[0]
            except IndexError:
                slack_ui_util.error_response("Build information for build `{}` is not found in recorder.".format(arg_item_data))


            if not data:
                text = "build data is not found for `{}`".format(arg_item_data)
                return slack_ui_util.respond(None, text)
            repo = data.get("_source").get("repositories", None)
            author = data.get("_source").get("gitauthor", None)
            service = data.get("_source").get("service", None)
            git_commit = data.get("_source").get("gitcommit", None)
            build_time = data.get("_source").get("buildtime", None)
            git_repo = data.get("_source").get("gitrepo", None)
            passed = data.get("_source").get("coverage") \
                .get("unittestcases").get("passed")
            failed = data.get("_source").get("coverage") \
                .get("unittestcases").get("failed")
            skipped = data.get("_source").get("coverage") \
                .get("unittestcases").get("skipped")
            line = int(data.get("_source").get("coverage")
                       .get("coverage").get("line"))
            class_cov = int(data.get("_source").get("coverage")
                            .get("coverage").get("class"))
            branch = int(data.get("_source").get("coverage")
                         .get("coverage").get("branch"))
            instruction = int(data.get("_source").get("coverage")
                              .get("coverage").get("instruction"))
            git_commit = data.get("_source").get("gitcommit", None)
            repo = data.get("_source").get("gitrepo", None)

            slack_data = {
                "response_type": "ephemeral",
                "text": "*Build information of build* : `{}`".format(arg_item_data),
                "attachments": [
                    {
                        "text": "*Repository*: `{}`".format(repo),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Author*: `{}`".format(author),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Service*: `{}`".format(service),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*GIT Commit*: `{}`".format(git_commit),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Build time*: `{}`".format(build_time),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*GIT Repo*: `{}`".format(git_repo),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Passed*: `{}`".format(passed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Failed*: `{}`".format(failed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Unittest Case Skipped*: `{}`".format(skipped),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Line Code Coverage*: *`{}%`*".format(line),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Class Code Coverage*: *`{}%`*".format(class_cov),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Branch Code Coverage*: *`{}%`*".format(branch),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Instruction Code Coverage*:"
                            " *`{}%`*".format(instruction),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    }
                ]
            }
            return slack_ui_util.respond(None, slack_data)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")
        except TransportError as e:
            return slack_ui_util.respond(e)
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
        return self.default_run_command()

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

# {#invoke_methods_section#}

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_buildinfo_main():
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

# End unit-test section.
# #########################
# Helper classes
