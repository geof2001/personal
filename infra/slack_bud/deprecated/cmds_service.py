"""Implements Service command by qzhong@roku.com"""
from __future__ import print_function

import argparse
import json
import boto3
import gitlab
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdService(CmdInterface):

    def get_help_title(self):
        """
        Ruturn short description used in global help summary
        and title of commands help page
        """
        return 'Command that deals with anything related to services. (List, Create, etc.)'

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud service <action> <optional_params> -s <service>_\n\n"
        help_text += "`<list>` _Lists all services that are slack_bud compliant._\n"
        help_text += "Example: _/bud service list_\n\n"
        help_text += "`<create>` _Creates a boiler-plate of a Slack Bud compliant service._\n\n"
        help_text += "Example: _/bud service create --repo myRepo --service myService_\n\n"
        help_text += "\t*<Flags>*\n"
        help_text += "\t\t`--repo` - The SR repo in which the service is to be created. (Required)\n"
        help_text += "\t\t`--service, -s` - Service to be created.\n\n"
        help_text += "_NOTE: The --repo flag is required. If a repo already exists, "
        help_text += "it will be used. If not, a new one with the given name will be created._"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, command_text, response_url=None, slack_channel=None):
        """
        Return help text for your command in slack format here.
        """

        # Argument parser configuration
        parser = argparse.ArgumentParser(description='Creates service repo with sample templates.')
        parser.add_argument('--repo', '-repo', '-r', metavar='', help=' Name of SR repo.')
        parser.add_argument('--service', '-service', '-s', metavar='', default=None,
                            help=' Service to be created.')

        args, unknown = parser.parse_known_args(command_text.split())
        print('ARGS: %s' % args)

        try:
            if sub_command == 'help':
                return self.get_help_text()

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            if sub_command == 'list':
                return handle_list()
            if sub_command == 'create':
                payload = {
                    'task': 'CmdService',
                    'service': args.service,
                    'repo': args.repo,
                    'response_url': response_url
                }
                lambda_function = boto3.client('lambda')
                response = lambda_function.invoke(
                    FunctionName="slackbud-longtasks",
                    InvocationType="Event",
                    Payload=json.dumps(payload)
                )
                print(response)

                if args.service:
                    text = 'Attempting to create service `%s` in repository `%s` . . .' \
                           % (args.service, args.repo)
                else:
                    text = 'Attempting to create repository `%s` . . .' % args.repo

                return slack_ui_util.text_command_response(text, '')

            text = 'Please enter a valid command. Type /bud service help for more info.'
            return slack_ui_util.error_response(text)

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
            elif fallback_str == self.__class__.__name__:
                return True
            return False

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return False

    def invoke_longtask_command(self, event):
        """
        This is where long running tasks are handled
        """
        repo = event.get('repo')
        service = event.get('service')
        response_url = event.get('response_url')
        return handle_create(repo, service, response_url)

    def set_fallback_value(self):
        return self.__class__.__name__


def handle_list():
    """
    List all slack-bud compliant services.
    :return: String of all services to send back through slack
    """
    # Create DDB boto3 resource
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
    return slack_ui_util.text_command_response(title=title, text=text, color=color)


def handle_create(repo, service, response_url):
    """
    Placeholder for command
    :param repo: Repo name
    :param service: Service name
    :param response_url: The response URL to slack
    :return:
    """

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
    slack_ui_util.text_command_response(
        title='',
        text=ret_str,
        color=color,
        post=True,
        response_url=response_url
    )


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
