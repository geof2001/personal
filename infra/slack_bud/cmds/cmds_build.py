"""Implements Build command by asnyder"""
from __future__ import print_function
import traceback

from datetime import datetime
import urllib2
import logging
import boto3
import json
import gitlab
import re
import requests
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface
from collections import OrderedDict

TOKEN = 'REGRESSIONISGOOD'
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
BUILD_METHODS = {
    'docker_build_V2': 'https://cidsr.eng.roku.com/view/Docker/job/docker-create-javaserver-image-v2/',
    'docker_copy_s3': 'https://cidsr.eng.roku.com/view/Docker/job/docker-copy-scripts-to-s3/',
    'docker_bif_build': 'https://cidsr.eng.roku.com/view/Docker/job/docker-create-bifserver-image/',
    'recsys_emr_s3': 'https://cidsr.eng.roku.com/job/deploy-recsys-emr-jar-to-S3/',
    'recsys_wikipedia_extractor': 'https://cidsr.eng.roku.com/view/Docker/job/docker-recsys-wikipedia-extractor/'
}

DIFFERENT_NAME_IMAGE_SERVICES = {
    'recsys-wikipedia-extractor-batch': 'recsys-wikipedia-extractor',
    'recsys-wikipedia-extractor': 'recsys-wikipedia-extractor-batch',
    'recsys-api': 'recsys',
    'recsys': 'recsys-api'
}

LAMBDA = boto3.client('lambda')
GITLAB_URL = 'https://gitlab.eng.roku.com/'
JIRA_URL = 'https://jira.portal.roku.com:8443/'
GIT_TOKEN = 'B8cREFMrfFKF7MKWi8jP'
MAX_COMMITS = 200
REGEX_FOR_JIRA = re.compile(r'(\[\w+\-\d{2,5}\]|\w+\-\d{2,5})')

class CmdBuild(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['_default_', 'history', 'diff'],
            'help_title': 'Builds the specified service. (Default branch: master)',
            'permission_level': 'dev',
            'props__default_': self.get__default__properties(),
            'props_history': self.get_history_properties(),
            'props_diff': self.get_diff_properties()
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
            'help_text': '`<>` Build service',
            'help_examples': [
                '/bud build -s content',
                '/bud build -s content --branch myBranch'
            ],
            'switch-templates': ['service'],
            'switch-b': {
                'aliases': ['b', 'branch'],
                'type': 'string',
                'required': False,
                'lower_case': False,
                'help_text': 'Branch name. (default: master)'
            }
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
            arg_service = cmd_inputs.get_by_key('service')
            arg_branch = cmd_inputs.get_by_key('branch')
            if not arg_branch:
                arg_branch = 'master'

            param_slack_user_name = cmd_inputs.get_slack_user_name()
            user = param_slack_user_name
            response_url = cmd_inputs.get_response_url()
        
            # Start _Default_ code section #### output to "text" & "title".

            # Get DynamoDB service table for info
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': arg_service})

            # If service does not exist
            if 'Item' not in service:
                text = "Unable to build. Service `%s` does not exist in table " \
                       "*[ServiceInfo]*." % arg_service
                return slack_ui_util.error_response(text)

            # Check if the service is buildable/has build info
            if 'build' not in service['Item']['serviceInfo']:
                text = 'Service `%s` is not buildable according to service_info.yaml.' \
                       % arg_service
                return slack_ui_util.error_response(text)

            # Determine build method and URL from table
            build_method = service['Item']['serviceInfo']['build']['method'] \
                if 'method' in service['Item']['serviceInfo']['build'] else ''
            build_url = BUILD_METHODS[build_method] if build_method in BUILD_METHODS else ''
            if not build_url:
                text = "Service `%s` does not have a build method/URL associated with it..." \
                       % arg_service
                return slack_ui_util.error_response(text)

            # Handle builds based on their methods
            if build_method == 'docker_build_V2' or build_method == 'docker_copy_s3' or build_method == 'docker_bif_build':
                full_build_url = '{url}buildWithParameters?token={token}' \
                                 '&BRANCH={branch}&SERVICE_NAME={service}' \
                                 '&TAGS={user}&RESPONSE_URL={response_url}' \
                    .format(url=build_url,
                            token=urllib2.quote(TOKEN),
                            branch=urllib2.quote(arg_branch),
                            service=urllib2.quote(arg_service),
                            user=urllib2.quote(user),
                            response_url=response_url)
                LOGGER.info(full_build_url)
                urllib2.urlopen(full_build_url)
                text = "The build for `%s` has kicked off. Check ```%s``` to " \
                       "monitor it..." % (arg_service, build_url)
                return slack_ui_util.text_command_response(None, text)

            elif build_method == 'recsys_wikipedia_extractor':
                full_build_url = '{url}buildWithParameters?token={token}' \
                                 '&BRANCH={branch}&TAGS={user}' \
                                 '&RESPONSE_URL={response_url}' \
                                 '&SERVICE_NAME={service}' \
                    .format(url=build_url,
                            token=urllib2.quote(TOKEN),
                            branch=urllib2.quote(arg_branch),
                            user=urllib2.quote(user),
                            response_url=response_url,
                            service=arg_service)
                LOGGER.info(full_build_url)
                urllib2.urlopen(full_build_url)
                text = "The build for `%s` has kicked off. Check ```%s``` to " \
                       "monitor it..." % (arg_service, build_url)
                return slack_ui_util.text_command_response(None, text)

            elif build_method == 'recsys_emr_s3':
                full_build_url = '{url}buildWithParameters?token={token}&SERVICE_NAME={service_name}' \
                                 '&RESPONSE_URL={response_url}'\
                    .format(url=build_url,
                            token=urllib2.quote(TOKEN),
                            service_name=urllib2.quote(arg_service),
                            response_url=response_url)
                LOGGER.info(full_build_url)
                urllib2.urlopen(full_build_url)
                text = "The build for `%s` has kicked off. Check ```%s``` to " \
                       "monitor it..." % (arg_service, build_url)
                return slack_ui_util.text_command_response(None, text)

            # Error text
            text = "The build for `%s` failed to kicked off. Check ```%s``` to see " \
                   "why..." % (arg_service, build_url)
            return slack_ui_util.error_response(text)

            # End _Default_ code section. ####
        
            # Standard response below. Change title and text for output.
            title = "Build"
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_history_properties(self):
        """
        The properties for the "history" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<history>` Lists build history of the specified service.',
            'help_examples': [
                '/bud build history -s content -n 5 -b myBranch'
            ],
            'switch-templates': ['service'],
            'switch-n': {
                'aliases': ['n', 'num'],
                'type': 'int',
                'required': False,
                'lower_case': True,
                'help_text': 'Number of builds to show. (Default: 10)'
            },
            'switch-b': {
                'aliases': ['b', 'branch'],
                'type': 'string',
                'required': False,
                'lower_case': False,
                'help_text': 'Branch built against. (Default: all)'
            }
        }
        return props

    def invoke_history(self, cmd_inputs):
        """
        Placeholder for "history" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_history")
            arg_service = cmd_inputs.get_by_key('service')
            arg_branch = cmd_inputs.get_by_key('branch')
            arg_num = cmd_inputs.get_by_key('num')
            if not arg_num:
                arg_num = 10

            response_url = cmd_inputs.get_response_url()
        
            # Start History code section #### output to "text" & "title".

            # Get DynamoDB service table for info
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': arg_service})

            # If service does not exist
            if 'Item' not in service:
                text = "Unable to build. Service `%s` does not exist in table " \
                       "*[ServiceInfo]*." % arg_service
                return slack_ui_util.error_response(text)
            # Setup ES client
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
                try:
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
                    output += '`Unit Tests Skipped`  -  _%s_\n' % build['_source']['coverage']['unittestcases'][
                        'skipped']
                except ShowSlackError:
                    text = '%s builds do not exist with the specified filters. Lower the number.' % arg_num
                    return slack_ui_util.error_response(text)

            if search_list:
                title = 'Here are `%s` of the most recent build(s) for service `%s`' % (arg_num, arg_service)
            else:
                title = 'No builds can be found for service `%s` with specified input.' % arg_service
            text = output
            color = "#d77aff"
            return slack_ui_util.text_command_response(title=title, text=text, color=color)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_diff_properties(self):
        """
        The properties for the "diff" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'longtask',
            'help_text': '`<diff>` Gets the build differences between two builds.',
            'help_examples': [
                '/bud build diff master:1111-111-1111 master:2222-222-2222'
            ],
            'switch-templates': [],
            'switch-jira': {
                'aliases': ['jira'],
                'type': 'property',
                'required': False,
                'lower_case': False,
                'help_text': 'Jira property flag'
            }
        }
        return props

    def invoke_diff(self, cmd_inputs):
        """
        Placeholder for "diff" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_diff")
            build1 = cmd_inputs.get_by_index(2)
            build2 = cmd_inputs.get_by_index(3)
            jira = cmd_inputs.get_by_key('-jira')
            response_url = cmd_inputs.get_response_url()
            logging.info("Build1: {}".format(build1))
            logging.info("Build2: {}".format(build2))
            logging.info("Callback url is {}".format(response_url))
            es_client = aws_util.setup_es()

            build1_info = es_client.search(index='build*', body=get_query(build1))
            build2_info = es_client.search(index='build*', body=get_query(build2))

            repo_for_build1 = build1_info.get('hits').get('hits')[0].get('_source').get('gitrepo')
            repo_for_build2 = build2_info.get('hits').get('hits')[0].get('_source').get('gitrepo')

            commit_for_build1 = build1_info.get('hits').get('hits')[0].get('_source').get('gitcommit')
            commit_for_build2 = build2_info.get('hits').get('hits')[0].get('_source').get('gitcommit')


            # return slack_ui_util.respond(None,
            #                              {
            #                                  "response_type": "ephemeral",
            #                                  "text":
            #                                      "*Work is in progress, Please wait for a moment.....*"
            #                              }
            #                              )

            if repo_for_build1 != repo_for_build2:
                header = {"Content-type": "application/json"}
                body = {
                    "response_type": "ephemeral",
                    "text": "*Can not get git difference or jira task between builds,"
                            "build: `{}` is from repository: `{}` and build: `{}` is "
                            "from repository `{}`,"
                            " repositories *".format(build1, repo_for_build1, build2, repo_for_build2)
                }
                r = requests.post(response_url, data=json.dumps(body), headers=header)
            if jira:
                slack_data = get_commit_difference_data(build1, build2, commit_for_build1, commit_for_build2,
                                                        repo_for_build1, jira=True)
                header = {"Content-type": "application/json"}
                body = slack_data
                r = requests.post(response_url, data=json.dumps(slack_data), headers=header)
                logging.info("Posted on this URL: {}".format(response_url ))
                logging.info("Posted this DATA {}".format(slack_data))
                logging.info("Response Code for POST : {}".format(r.status_code))
                logging.info("Reason: {}".format(r.reason))
            else:
                slack_data = get_commit_difference_data(build1, build2, commit_for_build1, commit_for_build2,
                                                        repo_for_build1)
                header = {"Content-type": "application/json"}
                body = slack_data
                r = requests.post(response_url , data=json.dumps(slack_data), headers=header)
                logging.info("Posted on this URL: %s" % response_url)
                logging.info("Posted this DATA {}".format(slack_data))
                logging.info("Response Code for POST : {}".format(r.status_code))
                logging.info("Reason: {}".format(r.reason))
        except ValueError:
            return slack_ui_util.respond(
                None,
                {
                    "response_type": "in_channel",
                    "text": "*Please check the build argumets ,provide "
                            "in `/bud build diff <build1> <build2> "
                            "--jira` format*"
                }
            )
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

# PUT STATIC METHODS HERE. AND REMOVE THIS COMMENT.

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_build_main():
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


def get_commit_difference_data(build1,build2,commit1, commit2,repo_name, jira=False):
    gl = gitlab.Gitlab(GITLAB_URL, GIT_TOKEN, api_version=3)
    logging.info(gl)
    project = gl.projects.list(search=repo_name)[0]
    logging.info(project)
    commits = [str(x.id) for x in project.commits.list(page=0, per_page=MAX_COMMITS,ref_name='master')]
    logging.info('Commits :{}'.format(commits))
    current_commit = commit1
    last_commit = commit2
    logging.info('Current Commit {}'.format(current_commit))
    logging.info('Last commit: {}'.format(last_commit))
    logging.info(current_commit)
    logging.info(last_commit)
    logging.info(' ' in current_commit)
    logging.info(' ' in last_commit)
    try:
        start_point, end_point = 0, 0
        start_point = commits.index(commit1)
        end_point = commits.index(commit2)
        if start_point > end_point:
            start_point,end_point = end_point,start_point
        commits_in_between = commits[start_point:end_point]
    except ValueError:
        data = {
            "response_type": "in_channel",
            "text": "One of the commit is not find in gitlab, Please check commit is present in gitlab"
        }
        return data
    if commits_in_between == []:
        data = {
            "response_type": "in_channel",
            "text": "There is no commits in between builds.",
        }
        return data
    commit_info = []
    #commit_info =  OrderedDict()
    jira_info =  OrderedDict()
    for commit in commits_in_between:
        commit_title = project.commits.get(commit).title
        short_id = project.commits.get(commit).short_id
        author = str(project.commits.get(commit).author_email).split('@')[0]
        jira_task = re.search(REGEX_FOR_JIRA, commit_title)
        logging.info('JIRA task: {}'.format(jira_task))
        # if jira_task:
        #     if "SR" in jira_task.group(1):
        #         #url_for_jira_task = jira_url + 'browse/' + jira_task.group(1)
        #         task_id = jira_task.group(1)
        #         commit_title = (commit_title.replace(task_id,"")).strip()
        #         if '[' or ']' in task_id:
        #             task_id = ''.join(char for char in task_id if char not in '()[]')
        #         url_for_jira_task = JIRA_URL + 'browse/' + task_id
        #         commit_id = "`{}`,`{}`".format(short_id, author)
        #         if len(commit_title) <= 45:
        #             jira_info[commit_id] = commit_title
        #         else:
        #             jira_info[commit_id] = commit_title[:45]+".."
        #
        #     else:
        #         pass
        # url_for_difference = GITLAB_URL + "SR/" + repo_name + "/commit/" + commit
        # commit_id = "`{}`,`{}`".format(short_id, author)
        commit_message = "`{}`,`{}`,`{}`".format(short_id, author, commit_title)
        if len(commit_message) <= 75:
            pass
        else:
            commit_message = commit_message[:75]+".."+'`'
        commit_info.append(commit_message)
        # if len(commit_title) <= 45:
        #     commit_info[commit_id] = commit_title
        # else:
        #     commit_info[commit_id] = commit_title[:45]+".."
    logging.info("Commit Information: {}".format(commit_info))
    logging.info("Jira Information: {}".format(jira_info))
    attachments = []
    dash = '-'*50
    if not jira:
        for commit_msg in commit_info:
            info = ''
            information = {}
            info += "{}".format(commit_msg.encode('ascii', 'ignore'))
            #info += dash
            information["text"] = info
            information["mrkdwn_in"] = ["text"]
            information["color"] = "#bd9ae8"
            attachments.append(information)
        slack_data = {
            "response_type": "in_channel",
            "text": "*Git difference between builds*: `{}` and `{}`\n*Total commits in between*: {}\n".format(build1, build2, len(attachments)),
            "attachments": attachments
        }
        return slack_data
    else:
        if jira_info != {}:
            for k, v in jira_info.items():
                info = ''
                information = {}
                info += "*JIRA Title*: {}, \n*Jira Task*: `{}`\n".format(k.encode('ascii', 'ignore'), v)
                #info += dash
                information["text"] = info
                information["mrkdwn_in"] = ["text"]
                information["color"] = "#bd9ae8"
                attachments.append(information)
            slack_data = {
                "response_type": "in_channel",
                "text": "*JIRA tasks between builds*: `{}` and `{}`\n*Total JIRA tasks in between*: {}\n     {}".format(build1, build2, len(attachments), dash),
                "attachments": attachments
            }
            return slack_data
        else:
            slack_data = {
                "response_type": "in_channel",
                "text": "*Jira task not found between builds*: `{}` and `{}`".format(build1, build2),
            }
            return slack_data


def get_query(build):
    query = {
        "query": {
            "query_string": {
                "query": "dockertag.keyword:{}".format(build)
                        }
                    }
                }
    return query