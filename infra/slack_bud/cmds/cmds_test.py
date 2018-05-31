"""Implements Test command by jpatel"""
from __future__ import print_function
import datetime
import traceback
import logging
import requests
import boto3
import json
import time

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


# Constant parameters
TOKEN = 'REGRESSIONISGOOD'
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
LAMBDA = boto3.client('lambda')

TEST_JOB_MAPPING = {
    "content": "https://cidsr.eng.roku.com/job/test_content_service_trigger/"
}


class CmdTest(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['run', 'history', 'lastfail'],
            'help_title': 'trigger test on sr services',
            'permission_level': 'dev',
            'props_run': self.get_run_properties(),
            'props_history': self.get_history_properties(),
            'props_lastfail': self.get_lastfail_properties()
# {#sub_command_prop_methods#}
        }

        return props


    def get_run_properties(self):
        """
        The properties for the "run" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'longtask',
            'help_text': '*Run* runs a test',
            'help_examples': [
                '/bud test run -s content -e prod -r us-west-2'
            ],
            'switch-templates': ['env', 'service', 'region'],
        }
        return props

    def invoke_run(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_run")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            current_job_id = ""
            slack_callback_url = cmd_inputs.get_response_url()
            if arg_service == "content":
                region = arg_region
                environment = arg_env
                service = arg_service
                url = TEST_JOB_MAPPING.get('content')
                full_test_url = "{}buildWithParameters?token={}" \
                                "&TESTENV={}&SERVICE={}" \
                                "&REGION={}".format(url, TOKEN, environment,
                                                    service, region)
                LOGGER.info(full_test_url)
                response = requests.post(full_test_url)
                if response.status_code == 201:
                    text = "The Test for `{}` service has kicked off in `{}` environment and `{}` region. Check ```{}``` to " \
                           "monitor it...".format(arg_service, environment, region, url)

                    # Get triggered jenkins job id.
                    lastbuild = requests.get(
                        "{}/lastBuild/api/json".format(url))
                    current_job_id = int((json.loads(lastbuild.content).get('displayName'))[1:]) + 1
                    # event['args'] = args
                    # event['response_url'] = response_url
                    # event['custom_data'] = current_job_id
                    # # invoke_longtask_command(event)
                    print('Invoke longtasks lambda function response:\n{}'.format(response))
                    title = "Test Response"
                    slack_ui_util.text_command_response(title, text, post=True, response_url=slack_callback_url)
                else:
                    text = "Can't start Test for `{}` service  in `{}` environment and `{}` region".format(arg_service,
                                                                                                           arg_env,
                                                                                                           arg_region)
                    return slack_ui_util.error_response(text)

            es_client = aws_util.setup_es()

            # Get query data for test result.
            job_id = current_job_id  # event.get('custom_data')  # ToDo... figure out how to package up job_id.



            poll = 100
            polling_interval = 2
            passed_tc, failed_tc, skipped_tc, test_time, test_link, environment, testendpoint, testimage = "", "", "", "", \
                                                                                                           "", "", "", ""
            while poll:
                # Query for test case result
                test_result_query = "\"{}\" AND service:\"{}\" AND testenv:\"{}\"".format(job_id, arg_service, arg_env)

                # ES query
                query = {
                    "query": {
                        "query_string": {
                            "query": str(test_result_query)
                        }
                    }
                }
                print("QUERY: {}".format(query))

                search_result = es_client.search(
                    index="test*",
                    doc_type="json",
                    body=query,
                    sort=['testtime:desc'],
                    size=10
                )
                print("Total :{}".format(search_result.get('hits').get('total')))
                content_list = search_result.get('hits').get('hits')
                if len(content_list) != 0:
                    result_container = []
                    for result in content_list:
                        result_container.append((result.get('_source')))
                    latest_result = result_container[0]
                    passed_tc = latest_result.get('testpassed')
                    failed_tc = latest_result.get('testfailed')
                    skipped_tc = latest_result.get('testskipped')
                    test_time = latest_result.get('testtime')
                    test_link = latest_result.get('testlink')
                    service = latest_result.get('service')
                    environment = latest_result.get('testenv')
                    testendpoint = latest_result.get('endpoint')
                    testimage = latest_result.get('dockertag')
                    break
                else:
                    print("Polling for data....")
                    time.sleep(polling_interval)
                    # polling_interval += 2**polling_interval
                    poll -= 1
            title = "Testcase result on service:`{}` environment:`{}` region:`{}` \n".format(arg_service,
                                                                                             arg_env,
                                                                                             arg_region)
            text = ""
            text += "Service: `{}` \n".format(arg_service)
            text += "Environment: `{}` \n".format(arg_env)
            text += "Endpoint `{}` \n".format(testendpoint)
            text += "Build `{}` \n".format(testimage)
            text += "Testcases passed: `{}` \n".format(passed_tc)
            text += "Testcases failed: `{}` \n".format(failed_tc)
            text += "Testcases skipped: `{}` \n".format(skipped_tc)
            text += "Testcases time: `{}` \n".format(test_time)
            text += "Link: `{}`".format(test_link)

            return slack_ui_util.text_command_response(title, text, post=True, response_url=slack_callback_url)
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
            'help_text': '*History* Get history of commands run',
            'help_examples': [
                '/bud test history -n 10 -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['env', 'service', 'region'],
            'switch-n': {
                'aliases': ['n', 'num'],
                'type': 'int',
                'required': False,
                'lower_case': True,
                'help_text': 'Number of tests to include in history'
            }
        }
        return props

    def invoke_history(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_history")
            region = cmd_inputs.get_by_key('region')  # remove if not used
            env = cmd_inputs.get_by_key('env')  # remove if not used
            service = cmd_inputs.get_by_key('service')  # remove if not used
            number = cmd_inputs.get_by_key('num')
            if not number:
                number = 10

            # Put History code below.

            # Setup ES client for getting test data.
            es_client = aws_util.setup_es()

            # Query for test case result
            test_result_query = "service:\"{}\" AND testenv:\"{}\"".format(service, env)

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": str(test_result_query)
                    }
                }

            }
            print("QUERY: {}".format(query))

            search_result = es_client.search(
                index="test*",
                doc_type="json",
                body=query,
                sort=['testtime:desc'],
                size=int(number)
            )

            passed_tc, failed_tc, skipped_tc, test_time, test_link, environment, testendpoint, testimage = "", "", "", "", \
                                                                                                           "", "", "", ""
            text = ""
            dash = "-" * 75
            print("Total :{}".format(search_result.get('hits').get('total')))
            content_list = search_result.get('hits').get('hits')
            if len(content_list) != 0:
                result_container = []
                for result in content_list:
                    result_container.append((result.get('_source')))
                for data in result_container:
                    passed_tc = data.get('testpassed')
                    failed_tc = data.get('testfailed')
                    skipped_tc = data.get('testskipped')
                    test_time = data.get('testtime')
                    test_link = data.get('testlink')
                    service = data.get('service')
                    environment = data.get('testenv')
                    testendpoint = data.get('endpoint')
                    testimage = data.get('dockertag')

                    text += "Service: `{}` \n".format(service)
                    text += "Environment: `{}` \n".format(environment)
                    text += "Endpoint `{}` \n".format(testendpoint)
                    text += "Build `{}` \n".format(testimage)
                    text += "Testcases passed: `{}` \n".format(passed_tc)
                    text += "Testcases failed: `{}` \n".format(failed_tc)
                    text += "Testcases skipped: `{}` \n".format(skipped_tc)
                    text += dash + '\n'
            title = 'Test history for `{}` service for env:`{}` for last:`{}`'.format(service, environment, number)
            return slack_ui_util.text_command_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_lastfail_properties(self):
        """
        The properties for the "lastfail" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Lastfail* command for get lastfailed testcases',
            'help_examples': [
                '/bud test lastfail -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['env', 'service', 'region'],
        }
        return props


    def get_last_failed_build_commit(self,buildnumber):
        es_client = aws_util.setup_es()

        # ES query
        query = {
            "query": {
                "query_string": {
                    "query": "dockertag.keyword:\"{}\"".format(buildnumber)
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
            data = None
        if not data:
            return None
        build_commit = data.get("_source").get("gitcommit", None)
        return build_commit

    def invoke_lastfail(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_lastfail")
            text = ""
            dash = "-" * 75
            region = cmd_inputs.get_by_key('region')  # remove if not used
            env = cmd_inputs.get_by_key('env')  # remove if not used
            service = cmd_inputs.get_by_key('service')  # remove if not used

            # Setup ES client for getting test data.
            es_client = aws_util.setup_es()

            # Query for test case result
            test_result_query = "service:\"{}\" AND testenv:\"{}\" AND testfailed:[1 TO *]".format(service, env)

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": str(test_result_query)
                    }
                }

            }
            print("QUERY: {}".format(query))

            search_result = es_client.search(
                index="test*",
                doc_type="json",
                body=query,
                sort=['testtime:desc'],
                size=1
            )
            data = search_result.get('hits').get('hits')[0].get('_source')
            print("Search Result: {}".format(search_result))
            print("Data: {}".format(data))
            passed_tc = data.get('testpassed')
            failed_tc = data.get('testfailed')
            skipped_tc = data.get('testskipped')
            test_time = data.get('testtime')
            test_link = data.get('testlink')
            service = data.get('service')
            environment = data.get('testenv')
            testendpoint = data.get('endpoint')
            testimage = data.get('dockertag')
            buildcommit = self.get_last_failed_build_commit(testimage)
            text += "Service: `{}` \n".format(service)
            text += "Environment: `{}` \n".format(environment)
            text += "Endpoint `{}` \n".format(testendpoint)
            text += "Build `{}` \n".format(testimage)
            text += "Testcases passed: `{}` \n".format(passed_tc)
            text += "Testcases failed: `{}` \n".format(failed_tc)
            text += "Testcases skipped: `{}` \n".format(skipped_tc)
            text += "Testtime: `{}` \n".format(test_time)
            text += "Lastbuildcommit: `{}` \n".format(buildcommit)
            text += "Testcaselink: `{}` \n".format(test_link)
            text += dash + '\n'
            # Optional response below. Change title and text as needed.
            title = "Last test failure information"
            print("Text for lastfail: {}".format(text))
            return slack_ui_util.text_command_response(title, text)
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
        # Default version of run command, can over-ride if needed.
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


def test_cases_cmd_test_main():
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