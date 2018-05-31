"""Implements Test command by jpatel"""
from __future__ import print_function
import datetime
import traceback
import logging
import argparse
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
"content" : "https://cidsr.eng.roku.com/job/test_content_service_trigger/"
}


class CmdTest(CmdInterface):

    def get_help_title(self):
        """
        Ruturn short description used in global help summary
        and title of commands help page
        """
        return 'trigger test on sr services'

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud test -s <service> -e <env> -r <region>_\n"
        help_text += "*Example:* _/bud test -s content -e prod -r us-west-2\n\n"
        help_text += "*Example:* _/bud test history -n 10 -s content -e dev -r us-east-1_\n\n"
        help_text += "*Example:* _/bud test lastfail -s content -e dev -r us-east-1_\n\n"
        help_text += "*history* _history checking history_\n"
        help_text += "*lastfail* _command for get lastfailed testcases_\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args, response_url=None, slack_channel=None):
        """
        Return help text for your command in slack format here.
        """
        try:
            event = {}
            if sub_command == 'help':
                return self.get_help_text()

            if response_url:
                self.set_response_url(response_url)
            # If no service flag was given, Return Error.
            if not args.services:
                text = 'A service was not specified. Use the flag ' \
                       '`-s` to specify one.'
                return slack_ui_util.error_response(text)

            if sub_command == "history":
                return handle_history_command(args)



            if args.services[0] == "content":
                region = args.regions[0]
                environment = args.envs[0]
                service = args.services[0]
                url = TEST_JOB_MAPPING.get('content')
                full_test_url = "{}buildWithParameters?token={}" \
                                 "&TESTENV={}&SERVICE={}" \
                                 "&REGION={}".format(url,TOKEN,environment,
                                    service,region)
                LOGGER.info(full_test_url)
                response = requests.post(full_test_url)
                if response.status_code == 201:
                    text = "The Test for `{}` service has kicked off in `{}` environment and `{}` region. Check ```{}``` to " \
                           "monitor it...".format(args.services[0],environment,region,url)

                    # Get triggered jenkins job id.
                    lastbuild = requests.get(
                        "{}/lastBuild/api/json".format(url))
                    current_job_id = int((json.loads(lastbuild.content).get('displayName'))[1:])+1
                    event['args'] = args
                    event['response_url'] = response_url
                    event['custom_data'] = current_job_id
                    invoke_longtask_command(event)
                    print('Invoke longtasks lambda function response:\n{}'.format(response))
                    return slack_ui_util.text_command_response(None, text)
                else:
                    text = "Can't start Test for `{}` service  in `{}` environment and `{}` region".format(service,
                                                                                                           environment,
                                                                                                           region)
                    return slack_ui_util.error_response(text)

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            if sub_command == 'history':
                # You need to modify this
                return handle_history_command(args)  # Adjust as needed
            if sub_command == 'lastfail':
                # You need to modify this
                return handle_lastfail_command(args)  # Adjust as needed
            title = 'Test response'
            text = '*Sorry, currently this command is implemented for `content` service only*'
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
        Long running task handler for test case result post.
        """
        # Setup ES client for getting test data.
        es_client = aws_util.setup_es()

        # Get query data for test result.
        job_id = event.get('custom_data')
        env = event.get('env')
        region = event.get('region')
        service = event.get('service')
        slack_callback_url = event.get('response_url')

        poll = 100
        polling_interval = 2
        passed_tc,failed_tc,skipped_tc,test_time,test_link,environment,testendpoint,testimage = "", "", "", "",\
                                                                                                "", "", "", ""
        while poll:
            # Query for test case result
            test_result_query = "\"{}\" AND service:\"{}\" AND testenv:\"{}\"".format(job_id,service, env)

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
                #polling_interval += 2**polling_interval
                poll -= 1
        title = "Testcase result on service:`{}` environment:`{}` region:`{}` \n".format(service, environment, region)
        text = ""
        text += "Service: `{}` \n".format(service)
        text += "Environment: `{}` \n".format(environment)
        text += "Endpoint `{}` \n".format(testendpoint)
        text += "Build `{}` \n".format(testimage)
        text += "Testcases passed: `{}` \n".format(passed_tc)
        text += "Testcases failed: `{}` \n".format(failed_tc)
        text += "Testcases skipped: `{}` \n".format(skipped_tc)
        text += "Testcases time: `{}` \n".format(test_time)
        text += "Link: `{}`".format(test_link)

        return slack_ui_util.text_command_response(title, text, post=True, response_url=slack_callback_url)

    def set_fallback_value(self):
        return self.__class__.__name__


def handle_history_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    # Setup ES client for getting test data.
    es_client = aws_util.setup_es()
    number = args.number[0]
    region = args.regions[0]
    environment = args.envs[0]
    service = args.services[0]

    # Query for test case result
    test_result_query = "service:\"{}\" AND testenv:\"{}\"".format(service, environment)

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
    dash = "-"*75
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
            text += dash+'\n'
    title = 'Test history for `{}` service for env:`{}` for last:`{}`'.format(service, environment, number)
    return slack_ui_util.text_command_response(title, text)



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


def handle_lastfail_command(args):
    """
    Placeholder for command
    :param args:
    :return:
    """
    try:
        es_client = aws_util.setup_es()
        number = args.number[0]
        region = args.regions[0]
        environment = args.envs[0]
        service = args.services[0]
        dash = "-" * 75
        text = ""
        # Query for test case result
        test_result_query = "service:\"{}\" AND testenv:\"{}\" AND testfailed:[1 TO *]".format(service, environment)

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
        data = search_result.get('hits').get('hits')[0]

        passed_tc = data.get('testpassed')
        failed_tc = data.get('testfailed')
        skipped_tc = data.get('testskipped')
        test_time = data.get('testtime')
        test_link = data.get('testlink')
        service = data.get('service')
        environment = data.get('testenv')
        testendpoint = data.get('endpoint')
        testimage = data.get('dockertag')
        buildcommit = get_last_failed_build_commit(testimage)
        text += "Service: `{}` \n".format(service)
        text += "Environment: `{}` \n".format(environment)
        text += "Endpoint `{}` \n".format(testendpoint)
        text += "Build `{}` \n".format(testimage)
        text += "Testcases passed: `{}` \n".format(passed_tc)
        text += "Testcases failed: `{}` \n".format(failed_tc)
        text += "Testcases skipped: `{}` \n".format(skipped_tc)
        text += "Testtime: `{}` \n".format(test_time)
        text += "Lastbuildcommit: `{}`".format(buildcommit)
        text += dash + '\n'
        # Optional response below. Change title and text as needed.
        title = "Last test failure information"
        return slack_ui_util.text_command_response(title, text)

    except ShowSlackError:
        raise
    except Exception as ex:
        bud_helper_util.log_traceback_exception(ex)
        raise ShowSlackError("Invalid request. See log for details.")



def invoke_longtask_command(event):
    """
    Entry point for long running task.

    This way of doing long tasks is temporary and will
    change with the next refactorying. SRINFRA-694
    :param event:
    :return:
    """
    try:
        start = datetime.datetime.now()

        payload = {}
        args_dict = event.get('args')
        response_url = event.get('response_url')
        custom_data = event.get('custom_data')

        # debug section verify the data makes it accross as expected.
        print('args={}'.format(args_dict))
        print('response_url={}'.format(response_url))
        print('custom_data={}'.format(custom_data))

        region = args_dict.regions[0]
        env = args_dict.envs[0]
        service = args_dict.services[0]

        payload['env'] = env
        payload['service'] = service
        payload['response_url'] = response_url
        payload['task'] = "CmdTest"
        payload['region'] = region
        payload['custom_data'] = custom_data
        response = LAMBDA.invoke(
            FunctionName="slackbud-longtasks",
            InvocationType="Event",
            Payload=json.dumps(payload)
            )
        print(response)
        #Start code here.


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