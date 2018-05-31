"""Implements Show command by asnyder"""
from __future__ import print_function

import boto3
from datetime import datetime

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

ENVIRONMENTS = aws_util.ENVIRONMENTS

class CmdShow(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['_default_', 'builds', 'deploys'],
            'help_title': 'Shows information based on specified input',
            'permission_level': 'dev',
            'props__default_': self.get__default__properties(),
            'props_builds': self.get_builds_properties(),
            'props_deploys': self.get_deploys_properties()
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
            'help_text': 'Shows information based on specified input',
            'help_examples': [
                '/bud show <data> <params> -e dev -r us-east-1 -s content'
            ],
            'switch-templates': ['env-optional', 'service', 'region-optional']
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
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()
        
            # Start _Default_ code section #### output to "text" & "title".
            text = 'Please enter something valid to show. Use _/bud show help_ to see a list of commands.'

            # End {} code section. ####
        
            # Standard response below. Change title and text for output.
            title = "Show command"
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_builds_properties(self):
        """
        The properties for the "builds" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<builds>` description here.',
            'help_examples': [
                '/bud show builds -s content -n 5 -b myBranch'
            ],
            'switch-templates': ['service'],
            'switch-b': {
                'aliases': ['b', 'branch'],
                'type': 'string',
                'required': False,
                'lower_case': False,
                'help_text': 'Branch to build against. (Default: master)'
            },
            'switch-n': {
                'aliases': ['n', 'num'],
                'type': 'int',
                'required': False,
                'lower_case': False,
                'help_text': 'Number of builds to show. (Default: 10)'
            }
        }
        return props

    def invoke_builds(self, cmd_inputs):
        """
        Placeholder for "builds" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_builds")
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_service = cmd_inputs.get_by_key('service')
            arg_branch = cmd_inputs.get_by_key('branch')
            arg_num = cmd_inputs.get_by_key('num')
            if not arg_num:
                arg_num = 10
            response_url = cmd_inputs.get_response_url()
        
            # Start Builds code section #### output to "text" & "title".
            # text = ''
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if arg_branch:
            #     text += 'arg_branch = {}\n'.format(arg_branch)
            # if arg_num:
            #     text += 'arg_num = {}\n'.format(arg_num)

            es_client = aws_util.setup_es()

            branch = " AND gitbranch.keyword:\"%s\"" % arg_branch if arg_branch else ''

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": "service.keyword:\"%s\"" % arg_service + branch
                    }
                }
            }
            search = es_client.search(
                index='build*',
                body=query,
                sort=['buildtime:desc'],
                size=arg_num
            )

            search_list = search['hits']['hits']
            output = ''

            for build in search_list:
                date = datetime.strptime(build['_source']['buildtime'], '%Y-%m-%dT%H:%M:%S')
                date = date.strftime('%b %d, %Y - %I:%M:%S %p')
                image_name = build['_source']['dockertag']
                job_number = image_name.split('-')[-1]
                output += '```Build #%s   (%s)```\n' % (job_number, date)
                output += '`Image`  -  _%s_\n' % image_name
                output += '`Git Repo`  -  _%s_\n' % build['_source']['gitrepo']
                output += '`Git Author`  -  _%s_\n' % build['_source']['gitauthor']
                output += '`Git Commit Hash`  -  _%s_\n' % build['_source']['gitcommit']
                output += '`Repository`  -  _%s_\n' % str(build['_source']['repositories'][0])
                output += '`Unit Tests Passed`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['passed']
                output += '`Unit Tests Failed`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['failed']
                output += '`Unit Tests Skipped`  -  _%s_\n' % build['_source']['coverage']['unittestcases']['skipped']

            if search_list:
                title = 'Here are the past `%s` build(s) for service `%s`' % (arg_num, arg_service)
            else:
                title = 'No builds can be found for service `%s` with specified input.' % arg_service
            text = output
            color = "#d77aff"
            return self.slack_ui_standard_response(title=title, text=text, color=color)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_deploys_properties(self):
        """
        The properties for the "deploys" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<deploys>` description here.',
            'help_examples': [
                '/bud show deploys -s content -n 5 -e dev -r us-east-1 -c'
            ],
            'switch-templates': ['env-optional', 'service', 'region-optional'],
            'switch-n': {
                'aliases': ['n', 'num'],
                'type': 'int',
                'required': False,
                'lower_case': False,
                'help_text': 'Number of builds to show. (Default: 10)'
            },
            'switch-c': {
                'aliases': ['c', 'changeset'],
                'type': 'string',
                'required': False,
                'lower_case': True,
                'help_text': 'Branch to build against. (Default: master)'
            }
        }
        return props

    def invoke_deploys(self, cmd_inputs):
        """
        Placeholder for "deploys" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_deploys")
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_service = cmd_inputs.get_by_key('service')
            arg_num = cmd_inputs.get_by_key('num')
            if not arg_num:
                arg_num = 10  # default value
            arg_changeset = cmd_inputs.get_by_key('changeset')
            # Check that this value is only 'true' | 'false' | None
            if arg_changeset:
                if arg_changeset not in ['true', 'false']:
                    raise ShowSlackError('Changeset flag `-c` needs to be either *true* or *false*')

            response_url = cmd_inputs.get_response_url()
        
            # Start Deploys code section #### output to "text" & "title".
            # text = ''
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if arg_changeset:
            #     text += 'arg_changeset = {}\n'.format(arg_changeset)
            # if arg_num:
            #     text += 'arg_num = {}\n'.format(arg_num)
            # Temp section to verify input rules are correct.
            # Setup ES client
            es_client = aws_util.setup_es()

            changeset_val = ''
            if arg_changeset == 'true':
                changeset_val = 'true'
            elif arg_changeset == 'false':
                changeset_val = 'false'

            env = " AND environment:\"%s\"" % ENVIRONMENTS[arg_env] if arg_env else ''
            region = " AND region:\"%s\"" % arg_region if arg_region else ''
            changeset = " AND changeset:\"%s\"" % changeset_val if changeset_val else ''

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": "service.keyword:\"%s\"" % arg_service + env + region + changeset
                    }
                }
            }
            search = es_client.search(
                index='deploy*',
                body=query,
                sort=['deploy_time:desc'],
                size=arg_num
            )

            search_list = search['hits']['hits']
            output = ''

            for deploy in search_list:
                date = datetime.strptime(deploy['_source']['deploy_time'], '%Y-%m-%dT%H:%M:%S')
                date = date.strftime('%b %d, %Y - %I:%M:%S %p')
                image_name = deploy['_source']['image_name'].split(':')[1]
                job_number = deploy['_source']['deploy_job_number']
                environment = deploy['_source']['environment']
                output += '```Deploy #%s   (%s)```\n' % (job_number, date)
                output += '`Image`  -  _%s_\n' % image_name
                output += '`Environment`  -  _%s_\n' % ENVIRONMENTS.keys()[ENVIRONMENTS.values().index(environment)]
                output += '`Region`  -  _%s_\n' % deploy['_source']['region']
                output += '`Change Set`  -  _%s_\n' % deploy['_source']['changeset']
                output += '`CF Status`  -  _%s_\n' % str(deploy['_source']['cf_status']) \
                    if 'cf_status' in deploy['_source'] else '`CF Status`  -  _?_\n'
                output += '`Deploy User`  -  _%s_\n' % deploy['_source']['userID']

            if search_list:
                title = 'Here are the past `%s` deploy(s) for service `%s`' % (arg_num, arg_service)
            else:
                title = 'No deploys can be found for service `%s` with specified input.' % arg_service
            text = output
            color = "#d77aff"
            return  self.slack_ui_standard_response(title=title, text=text, color=color)



            # End {} code section. ####
        
            # Standard response below. Change title and text for output.
            title = "Deploys title"
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
        return self.default_run_command()

# {#invoke_command#}

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """

        cmd_inputs = self.get_cmd_input()
        arg_service = cmd_inputs.get_by_key('service')

        # Create DDB boto3 resource
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': arg_service})

        # If specified service not in table
        if 'Item' not in service:
            error_text = 'The specified service does not exist in table `ServiceInfo`.'
            raise ShowSlackError(error_text)

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


def test_cases_cmd_show_main():
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