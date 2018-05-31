"""Implements Service command by asnyder"""
from __future__ import print_function

import json
import boto3
import gitlab

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdService(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['list', 'create'],
            'help_title': 'Command that deals with anything related to services. (List, Create, etc.)',
            'permission_level': 'dev',
            'props_list': self.get_list_properties(),
            'props_create': self.get_create_properties()
        }

        return props

    def get_list_properties(self):
        """
        The properties for the "list" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<list>` Lists all services that are slack_bud compliant.',
            'help_examples': [
                '/bud service list'
            ],
            'switch-templates': []
        }
        return props

    def invoke_list(self, cmd_inputs):
        """
        Placeholder for "list" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_list")

            # Start List code section #### output to "text" & "title".
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            result = services_table.scan()

            # Gather all services from ServiceInfo and sort
            service_list = []
            for item in result['Items']:
                service_list.append(item['serviceName'])
            service_list.sort()

            # Add services to return string
            text = ''
            for service in service_list:
                text += '`%s`\n' % service

            title = 'Here is a list of all services/stacks that are Slack Bud compliant.'
            color = "#d77aff"
            return  self.slack_ui_standard_response(title=title, text=text, color=color)
            # End List code section. ####

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_create_properties(self):
        """
        The properties for the "create" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'longtask',
            'help_text': '`<create>` Creates repo/service in Gitlab if it does not exist.',
            'help_examples': [
                '/bud service create --repo myRepo',
                '/bud service create --repo myRepo --service myService',
                'NOTE: The --repo flag is required. If a repo already exists, it will be used. If not, a new one with the given name will be created.'
            ],
            'switch-templates': ['service-optional'],
            'switch-repo': {
                'aliases': ['repo'],
                'type': 'string',
                'required': True,
                'lower_case': False,
                'help_text': 'The SR repo in which the service is to be created. (Required)'
            }
        }
        return props

    def invoke_create(self, cmd_inputs):
        """
        Placeholder for "create" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_create")
            arg_service = cmd_inputs.get_by_key('service')
            arg_repo = cmd_inputs.get_by_key('repo')
            response_url = cmd_inputs.get_response_url()

            repo = arg_repo
            service = arg_service

            # Start Create code section #### output to "text" & "title".
            # GitLab Credentials for authentication
            gl = gitlab.Gitlab('https://gitlab.eng.roku.com/', 'KvQaBkiuiZ4JPH9vqWQg')
            gl.auth()

            # Getting SR group ID
            group_id = gl.groups.list(search='SR')[0].id
            print('GROUP ID: %s' % group_id)
            project = ''
            ret_str = ''

            try:
                if gl.projects.get('SR/%s' % repo):
                    print('-------------------------------------------------------------------------------------')
                    print('ATTENTION: SR/%s already exists. Adding missing sample Phoenix files...' % repo)
                    print('-------------------------------------------------------------------------------------')
                    project = gl.projects.get('SR/%s' % repo)
                    ret_str += '[*Repository*] \n~%s~ - Already exists. Skipping...\n\n' % repo
            except gitlab.exceptions.GitlabGetError:
                print('-------------------------------------------------------------------------------------')
                print('Creating Sample Phoenix Repo For SR/%s ...' % repo)
                print('-------------------------------------------------------------------------------------')
                project = gl.projects.create({'name': repo, 'namespace_id': group_id})
                ret_str += '[*Repository*]\n`%s` - Successfully created...\n\n' % repo

            try:
                read_me = project.files.create({'file_path': 'README.md',
                                                'branch': 'master',
                                                'commit_message': 'Create sample README.md',
                                                'content':
                                                    '# %s\nInsert READ_ME information here...' % repo.title()})
                print('[%s] \'README.md\' was created...' % repo)
                ret_str += '[*File*] `%s/README.md` - Successfully created...\n' % repo
            except gitlab.exceptions.GitlabCreateError:
                print('[%s] \'README.md\' already exists and will not be created...' % repo)
                ret_str += '[*File*] ~%s/README.md~ - Already exists. Skipping...\n' % repo

            try:
                git_ignore = project.files.create({'file_path': '.gitignore',
                                                   'branch': 'master',
                                                   'commit_message': 'Create sample .gitignore',
                                                   'content':
                                                       '.idea/\n'
                                                       'gradle/\n'
                                                       'gradlew\n'
                                                       'gradlew.bat\n'
                                                       'apiDoc/\n'
                                                       'classes/\n'
                                                       'build/\n'
                                                       'gradle_graphs/\n'
                                                       'target/\n'
                                                       'out/\n'
                                                       'output/\n'
                                                       '.gradle/\n'
                                                       '.idea/\n'
                                                       'logs/\n'
                                                       '*.iml\n'
                                                       '*.iws\n'
                                                       '*.ipr\n'
                                                       '*.class\n'
                                                       '*.dll\n'
                                                       '*.so\n'
                                                       '*.exe\n'
                                                       '*.o\n'
                                                       '*.pyc\n'
                                                       '*.cache\n'
                                                       '.DS_Store\n'})
                print('[%s] \'.gitignore\' was created...' % repo)
                ret_str += '[*File*] `%s/.gitignore` - Successfully created...\n' % repo
            except gitlab.exceptions.GitlabCreateError:
                print('[%s] \'.gitignore\' already exists and will not be created...' % repo)
                ret_str += '[*File*] ~%s/.gitignore~ - Already exists. Skipping...\n' % repo

            try:
                build_gradle = project.files.create({'file_path': 'build.gradle',
                                                     'branch': 'master',
                                                     'commit_message': 'Create sample build.gradle',
                                                     'content':
                                                         '//allprojects{}\n\n'
                                                         '//subprojects{}\n\n//Include dependencies/repos/other info here...'})
                print('[%s] \'build.gradle\' was created...' % repo)
                ret_str += '[*File*] `%s/build.gradle` - Successfully created...\n' % repo
            except gitlab.exceptions.GitlabCreateError:
                print('[%s] \'build.gradle\' already exists and will not be created...' % repo)
                ret_str += '[*File*] ~%s/build.gradle~ - Already exists. Skipping...\n' % repo

            try:
                settings_gradle = project.files.create({'file_path': 'settings.gradle',
                                                        'branch': 'master',
                                                        'commit_message': 'Create sample settings.gradle',
                                                        'content':
                                                            'rootProject.name = \'%s\'\n//Includes here..\n\n'
                                                            '//Project microservice name alias here..' % repo})
                print('[%s] \'settings.gradle\' was created...' % repo)
                ret_str += '[*File*] `%s/settings.gradle` - Successfully created...\n' % repo
            except gitlab.exceptions.GitlabCreateError:
                print('[%s] \'settings.gradle\' already exists and will not be created...' % repo)
                ret_str += '[*File*] ~%s/settings.gradle~ - Already exists. Skipping...\n' % repo

            try:
                service_info_yaml = project.files.create({'file_path': 'infra/service_info.yaml',
                                                          'branch': 'master',
                                                          'commit_message': 'Create sample infra/service_info.yaml file',
                                                          'content': create_service_info(repo, service)})
                print('[%s/infra] \'service_info.yaml\' was created...' % repo)
                ret_str += '[*File*] `%s/infra/service_info.yaml` - Successfully created...\n' % repo
            except gitlab.exceptions.GitlabCreateError:
                project = gl.projects.get('SR/%s' % repo)
                f = project.files.get(file_path='infra/service_info.yaml', ref='master')
                data = f.decode()
                if str(service) in data:
                    print('[%s/infra] \'service_info.yaml\' already exists and will not be created...' % repo)
                    ret_str += '[*File*] ~%s/infra/service_info.yaml~ - Already exists. Skipping...\n' % repo
                else:
                    f.delete(commit_message='Re-creating service_info.yaml', branch='master')
                    data += update_service_info(repo, service)
                    service_info_yaml = project.files.create({'file_path': 'infra/service_info.yaml',
                                                              'branch': 'master',
                                                              'commit_message': 'Create sample infra/service_info.yaml file',
                                                              'content': data})
                    print('[%s/infra] \'service_info.yaml\' was created...' % repo)
                    ret_str += '[*File*] `%s/infra/service_info.yaml` - Successfully updated...\n' % repo

            try:
                params_json = project.files.create({'file_path': 'infra/%s.params.json' % repo,
                                                    'branch': 'master',
                                                    'commit_message': 'Create sample infra/%s/params.json file' % repo,
                                                    'content': create_params_json()})
                print('[%s/infra] \'%s.params.json\' was created...' % (repo, repo))
                ret_str += '[*File*] `%s/infra/%s.params.json` - Successfully created...\n' % (repo, repo)
            except gitlab.exceptions.GitlabCreateError:
                print('[%s/infra] \'%s.params.json\' already exists and will not be created...' % (repo, repo))
                ret_str += '[*File*] ~%s/infra/%s.params.json~ - Already exists. Skipping...\n' % (repo, repo)

            try:
                stack_yaml = project.files.create({'file_path': 'infra/%s.stack.yaml' % repo,
                                                   'branch': 'master',
                                                   'commit_message': 'Create sample infra/%s/stack.yaml file' % repo,
                                                   'content': create_stack_yaml(repo)})
                print('[%s/infra] \'%s.stack.yaml\' was created...' % (repo, repo))
                ret_str += '[*File*] `%s/infra/%s.stack.yaml` - Successfully created...\n' % (repo, repo)
            except gitlab.exceptions.GitlabCreateError:
                print('[%s/infra] \'%s.stack.yaml\' already exists and will not be created...' % (repo, repo))
                ret_str += '[*File*] ~%s/infra/%s.stack.yaml~ - Already exists. Skipping...\n' % (repo, repo)

            if service:
                try:
                    ms_gradle = project.files.create({'file_path': '%s/build.gradle' % service,
                                                      'branch': 'master',
                                                      'commit_message': 'Create build.gradle for %s/%s' %
                                                                        (repo, service),
                                                      'content':
                                                          '//Plug-Ins, Dependencies, Tasks here...'})
                    print('[%s/%s] \'build.gradle\' was created...' % (repo, service))
                    ret_str += '[*File*] `%s/%s/build.gradle` - Successfully created...\n' \
                               % (repo, service)
                except gitlab.exceptions.GitlabCreateError:
                    print('[%s/%s] \'build.gradle\' already exists and will not be created...' % (repo, service))
                    ret_str += '[*File*] ~%s/%s/build.gradle~ - Already exists. Skipping...\n' \
                               % (repo, service)

            print(response_url)
            color = "#d77aff"
            self.slack_ui_standard_response(
                title='',
                text=ret_str,
                color=color
            )
            # End Create code section. ####

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")


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

# service_info.yaml setup if it does not exist
def create_service_info(repo, service):
    """
    Updates current service info file
    :param repo: Repo name
    :param service: Service name
    :return st: String to be returned
    """
    st = '# Defines basic service settings for the %s\n\n' % repo
    st += '# Some basic info for the service\n'
    st += 'repository_name: %s\n' % repo
    st += 'persistent_branches:\n    - master\n\n'
    st += '# Add service components/settings below\n\n'
    st += '# Defines repository libraries to be uploaded to Artifactory\n'
    st += 'library:\n'
    st += '    path: none # or name of directory if there was one to publish\n\n'
    st += '# Defines actions of the pipeline controller for all services in repo\n'
    st += 'pipeline:\n'
    st += '    build_on_check_in: True\n'
    st += '    auto_deploy:\n'
    st += '        dev: \n'
    st += '            - us-east-1\n'
    st += '        qa: \n'
    st += '            - us-east-1\n\n'
    st += 'components:\n'
    st += update_service_info(repo, service)

    return st


# service_info.yaml update if it already exists
def update_service_info(repo, service):
    """
    Updates current service info file
    :param repo: Repo name
    :param service: Service name
    :return st: String to be returned
    """
    st = ''
    st += '    %s:\n' % service if service else '    None:  # REPLACE WITH ACTUAL SERVICE NAME\n'
    st += '        build:\n'
    st += '            method: docker_build_V2\n'
    st += '            params:\n'
    st += '                repo_path: # Path to code in repo here\n'
    st += '                docker_base_container: jenkins/docker/sparkserver\n\n'
    st += '        deploy:\n'
    st += '            method: CF_deploy_V1\n'
    st += '            params:\n'
    st += '                stack_file: # Stack path/file here - (repo/stack_name)\n'
    st += '            image_name: # Name of the parameter key for the docker image\n\n'
    st += '        properties_table:\n'
    st += '            stack_output: # Name of the properties table from the CF stack output\n'
    st += '            stack_name: # Name of the stack\n\n'
    st += '        test_smoke:\n'
    st += '            method: ptest\n'
    st += '            params:\n'
    st += '                test_script: # %s/%s_smoke\n' % (repo, service)
    st += '        test_regression:\n'
    st += '            method: ptest\n'
    st += '            params:\n'
    st += '                test_script: # %s/%s_regression\n' % (repo, service)
    st += '        test_load:\n'
    st += '            method: artillery\n'
    st += '            params:\n'
    st += '                test_script: # %s/%s_load\n\n' % (repo, service)
    st += '        # Configure respective regions/envs here\n\n'
    st += '        regions:\n'
    st += '            dev: \n'
    st += '                - us-east-1\n'
    st += '            qa: \n'
    st += '                - us-east-1\n'
    st += '            prod: \n'
    st += '                - us-east-1\n\n'

    return st


# Service params.json file setup
def create_params_json():
    """
    Create service params file
    :return st: String to be returned
    """
    st = '[\n'
    st += '  {\n    "ParameterKey":\n    ' \
          '"ParameterValue": "{{}}"\n  },\n'
    st = st[:-2] + '\n]'
    return st


# Service stack.yaml setup
def create_stack_yaml(repo):
    """
    Create service stack file
    :param repo: Repo name
    :return st: String to be returned
    """
    st = 'Description: CF Stack for service %s\n\n' % repo
    st += 'Conditions:\n\nParameters:\n\nResources:\n\nOutputs:\n\n'
    return st


# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_service_main():
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