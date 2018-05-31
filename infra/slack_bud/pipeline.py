"""Module handles the pipeline lambda."""
from __future__ import print_function
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

import json
import urllib
import os
import base64
import datetime
import requests
import traceback
import boto3
import util.aws_util as aws_util
from util.aws_util import CodePipelineStageError
import util.bud_helper_util as bud_helper_util
import test.unit_tests as unit_tests


def lambda_send_email_handler(event, context):
    """Send email with results."""

    print("Received event: " + json.dumps(event))
    ses_client = boto3.client('ses', region_name='us-west-2')
    s3_client = boto3.client('s3')

    # Get the latest pylint file from S3
    s3_client.download_file(
        'sr-infra-pipeline-source',
        'pylint_output.txt',
        '/tmp/pylint_output.txt'
    )

    # Get the unit-test results.
    s3_client.download_file(
        'sr-infra-pipeline-source',
        'unit-test.txt',
        '/tmp/unit-test.txt'
    )

    # Read the score from the file.
    subject_line = "SlackBud Pylint"
    pylint_score = get_score_from_pylint('/tmp/pylint_output.txt')
    if pylint_score is not None:
        subject_line += ': %s' % pylint_score

    job_id = event['CodePipeline.job']['id']
    print('CodePipeline JobID=%s' % job_id)

    recipients = ['asnyder@roku.com', 'qzhong@roku.com', 'areynolds@roku.com', 'jscott@roku.com']
    # ToDo: get recipient from githook info. Send to last code committer.

    msg = MIMEMultipart()
    msg['Subject'] = subject_line
    msg['From'] = 'SR-SLACKBUD-Service@roku.com'
    msg['To'] = ', '.join(recipients)

    # what a recipient sees if they don't use an email reader
    msg.preamble = 'Multipart message about SlackBud test results.\n'

    # the message body
    body_text = 'Attached are the results of latest SlackBud Pylint and unit tests.'
    if pylint_score is not None:
        body_text += '\nThe latest pylint score is: %s' % pylint_score
        body_text += '\nKeep this score above 7/10'
    part = MIMEText(
        body_text
    )
    msg.attach(part)

    # the attachments
    part = MIMEApplication(open('/tmp/pylint_output.txt', 'rb').read())
    part.add_header(
        'Content-Disposition',
        'attachment',
        filename='pylint_output.txt'
    )
    msg.attach(part)

    # unit test attachment.
    part = MIMEApplication(open('/tmp/unit-test.txt', 'rb').read())
    part.add_header(
        'Content-Disposition',
        'attachment',
        filename='unit-test.txt'
    )
    msg.attach(part)

    # Send the message
    result = ses_client.send_raw_email(
        RawMessage={'Data': msg.as_string()},
        Source=msg['From'],
        Destinations=recipients)
    print(result)

    cp_client = boto3.client('codepipeline')
    cp_client.put_job_success_result(
        jobId=job_id,
    )

    return 'done'


def get_score_from_pylint(pylint_path):
    """Get the pylint score. If no result file found fail gracefully."""
    try:
        score_lines = bud_helper_util.grep(
            pylint_path,
            'code has been rated at'
        )

        print('score_lines is type: %s' % type(score_lines))
        num_lines = len(score_lines)
        print('num_line=%s' % num_lines)
        if num_lines > 0:
            last_score = score_lines[num_lines-1]
            if type(last_score) is str:
                print("get_score_from_pylint() last_score: %s" % last_score)
                parts = last_score.strip().split()
                parts_len = len(parts)
                if parts_len > 0:
                    return parts[parts_len-1]
            else:
                print('last_score is type: %s' % type(last_score))
                print('last_score=%s' % (last_score,))
    except Exception as ex:
        print('Failed to get pylint score for reason: %s' % ex.message)


def lambda_deploy_handler(event, context):
    """Deploy lambda function"""
    print("Received event: " + json.dumps(event))
    start_time = datetime.datetime.now()

    job_id = event['CodePipeline.job']['id']
    print('CodePipeline JobID=%s' % job_id)
    deploy_stage = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']

    print("UserParameter - deploy_stage=%s" % deploy_stage)

    s3bucket = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
    s3key = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']

    print("s3bucket = %s" % s3bucket)
    print("s3key = %s" % s3key)

    cp_client = boto3.client('codepipeline')
    slack_command = 'UNDEFINED'
    try:
        print("deploy_stage = %s" % deploy_stage)

        if deploy_stage == 'dev':
            slack_command = '/buddev'
            update_lambda_function_code(
                'serverless-slackbud-dev-slackBud',
                s3bucket, s3key, True
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: serverless-slackbud-dev-slackBud')
            update_lambda_function_code(
                'pipeline-send-test-results',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: pipeline-send-test-results')
            update_lambda_function_code(
                'pipeline-deploy-prod',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: pipeline-deploy-prod')
            update_lambda_function_code(
                'serverless-slackbud-qa-slackBud',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: serverless-slackbud-qa-slackBud')
            update_lambda_function_code(
                'slackbud-longtasks-dev',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: slackbud-longtasks-dev')
            update_lambda_function_code(
                'pipeline-run-tests',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: pipeline-run-tests')
            update_lambda_function_code(
                'pipeline-deploy-dev',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: pipeline-deploy-dev')
        elif deploy_stage == 'prod':
            slack_command = '/bud'
            update_lambda_function_code(
                'serverless-slackbud-prod-slackBud',
                s3bucket, s3key, True
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: serverless-slackbud-prod-slackBud')
            update_lambda_function_code(
                'slackbud-longtasks',
                s3bucket, s3key
            )
            bud_helper_util.print_delta_time(
                start_time, 'Finished: slackbud-longtasks')

        else:
            error_msg = "Unknown deploy stage. Expected 'dev'|'prod'. Was %s."\
                        % deploy_stage
            raise CodePipelineStageError(error_msg)

        cp_client.put_job_success_result(
            jobId=job_id,
        )

        bud_helper_util.print_delta_time(
            start_time, 'Sent stage success result.')

        # Look inside the zip file to get the build_info.txt
        unzip_dir = '/tmp/deployed'
        upload_and_unzip_source_code(s3bucket, s3key, unzip_dir)

        bud_helper_util.print_delta_time(
            start_time, 'upload_and_unzip_source_code')

        extra_build_info = get_build_info_from_zip(unzip_dir)

        bud_helper_util.print_delta_time(
            start_time, 'get_build_info_from_zip')

        slack_msg_text = "Deployed to %s" % slack_command
        if extra_build_info is not None:
            slack_msg_text += '\nversion: %s' % extra_build_info

        # Put a success message on a Slack Channel
        post_message_to_slack_channel(
            title="Deployment",
            text=slack_msg_text
        )

        bud_helper_util.print_delta_time(
            start_time, 'Sent success message to Slack deploy channel')

    except CodePipelineStageError as ex:
        error_msg = 'FAILED Stage! reason %s' % ex.message
        print(error_msg)
        cp_client.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': error_msg
            }
        )
        # Put a message about deployment failure
        post_message_to_slack_channel(
            title='Failed deployment',
            text=error_msg,
            color='#ff3d3d'
        )
    except Exception as e:
        error_msg = 'FAILED Stage! reason: %s' % e.message
        print(error_msg)
        cp_client.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': error_msg
            }
        )
        # Put a message about deployment failure
        post_message_to_slack_channel(
            title='General error',
            text=error_msg,
            color='#ff3d3d'
        )

        bud_helper_util.print_delta_time(
            start_time, 'Done')

    return 'done'


# Deprecated by 'lambda_smoke_and_unit_test_handler'
# def lambda_run_tests(event, context):
#     """
#     Run both unit tests and smoke tests, and put results
#     in a text file and push to an S3 bucket.
#
#     :param event:
#     :param context:
#     :return: done
#     """
#     try:
#         cp_client = boto3.client('codepipeline')
#         job_id = event['CodePipeline.job']['id']
#         print('CodePipeline JobID=%s' % job_id)
#
#         print("Starting smoke test phase.")
#         # At this step look for smoke_*.txt files.
#         # And run each of them once, but catch non-200
#         # responses.
#
#         # Upload the zip file to /tmp
#         s3bucket = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
#         s3key = event['CodePipeline.job']['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']
#
#         print("s3bucket = %s" % s3bucket)
#         print("s3key = %s" % s3key)
#
#         # Upload and Unzip file.
#         unzip_dir = '/tmp/deployed'
#         upload_and_unzip_source_code(s3bucket, s3key, unzip_dir)
#         # Read build_info.txt to get build #.
#         version = get_build_info_from_zip(unzip_dir)
#         print("TESTING version: {}".format(version))
#
#         # scan test directory for smoke_test_*.txt files.
#         test_dir = unzip_dir+'/test'
#
#         txt_files = bud_helper_util.get_files_in_dir_by_type(
#             test_dir, 'txt'
#         )
#
#         # #TODO: Stopped here... Need to look for smoke_test_*.txt files.
#
#         # Run each file, catch and report details of errors.
#
#         # Write the output.
#
#     except Exception as ex:
#         print('Had an error.')
#
#     cp_client.put_job_success_result(
#         jobId=job_id,
#     )
#     return 'done'


def upload_and_unzip_source_code(
        s3bucket, s3key,
        unzip_dir='/tmp/deployed'):
    """
    Get the source code zip file and unzip is locally with
    the specified name and directory.
    :param s3bucket: Source S3 bucket.
    :param s3key: Source S3 object key.
    :param unzip_dir: Local lambda directory to unzip
    :return: None. Let any exceptions be thrown
    """
    dest_zip_file_path = unzip_dir+'.zip'
    s3_client = boto3.client('s3')
    s3_client.download_file(
        s3bucket,
        s3key,
        dest_zip_file_path
    )
    bud_helper_util.unzip_file(dest_zip_file_path, unzip_dir)


def get_build_info_from_zip(unzip_dir):
    """
    After calling 'unload_and_unzip_source_code' function
    Call this method to read the 'build_info.txt' file in
    the unzip directory.
    :param unzip_dir: unzip directory like '/tmp/deployed'
    :return: version string like 'slackbud-master-ca16386f-20180216-373'
    """
    # """Get the build info from the zip file.
    # Handle errors by logging and returning None"""
    try:
        txt_files = bud_helper_util.get_files_in_dir_by_type(
            unzip_dir, 'txt'
        )

        if len(txt_files) > 0:
            build_info_file_path = unzip_dir+'/build_info.txt'
            build_info_map =\
                bud_helper_util.read_key_value_file_to_dictionary(
                    build_info_file_path,
                    ': '
                )
            version = build_info_map['version']
            if version is not None:
                return version
            else:
                print("Failed to find version in build_info.txt file.")
        else:
            print("Didn't find build_info.txt")

    except Exception as ex:
        print('Failed to get build info from zip. Reason %s' % ex.message)


def found_lambda_function(list_function_response, function_name):
    """
    Return True if you found the lambda function in the list or responses.
    :param list_function_response: Response from boto3 lambda list_functions
    :param function_name: The function we are looking for.
    :return: True if found, otherwise False
    """
    functions = list_function_response['Functions']
    for curr_function in functions:
        curr_func_name = curr_function['FunctionName']
        if curr_func_name is function_name:
            return True
    return False


def update_lambda_function_code(function_name, s3_bucket, s3_key,
                                fail_stage_on_error=False):
    """Update code but handle and report errors gracefully"""
    try:
        print('Updating code for lambda function: %s' % function_name)
        lambda_client = boto3.client('lambda')

        # BELOW check is OPTIONAL. Skipping.
        # Check for lambda function name, to verify it exists.
        # print("Verify lambda function {} exists.".format(function_name))
        # list_function_response = lambda_client.list_functions(
        #     MasterRegion='us-west-2',
        #     FunctionVersion='$LATEST'
        # )
        # while True:
        #     if found_lambda_function(list_function_response, function_name):
        #         print("Found: {}".format(function_name))
        #         break
        #     else:
        #         print("Didn't find: {}. Looking for paginated response".format(function_name))
        #         if list_function_response['NextMarker']:
        #             print("NextMarker={}".format(list_function_response['NextMarker']))
        #             list_function_response = lambda_client.list_functions(
        #                 MasterRegion='us-west-2',
        #                 Marker=list_function_response['NextMarker']
        #             )

        response = lambda_client.update_function_code(
            FunctionName=function_name,
            S3Bucket=s3_bucket,
            S3Key=s3_key
        )

        # If status code is 200 return success.
        status_code = response['ResponseMetadata']['HTTPStatusCode']
        if status_code == 200:
            print('Deployed function: {}'.format(function_name))
        else:
            print('FAILED to deploy function: %s' % function_name)
            print('Status Code: %s' % status_code)
            print('Response: %s' % json.dumps(response))
            if fail_stage_on_error:
                error_log = 'Failed to update function %s. Check logs'\
                            % function_name
                raise CodePipelineStageError(error_log)
        return response

    except Exception as ex:
        error_log = 'Failed to update function %s. Reason: %s'\
                    % (function_name, ex)
        if fail_stage_on_error:
            raise CodePipelineStageError(error_log)
        else:
            print(error_log)


def create_build_info_file():
    """Create a build_info file"""

    print('Start create_build_info_file()')
    for curr_file in os.listdir("."):
        print(os.path.join(".", curr_file))

    try:
        # Write the build_info.txt file.
        build_info_file = open("build_info.txt", "w")

        build_time = aws_util.get_prop_table_time_format()
        build_info_file.write("build_time: %s" % build_time)

        # Include the githook information.
        if os.path.isfile('githook_info.txt'):
            githook_file = open('githook_info.txt', 'r')
            lines = githook_file.readlines()
            build_map = {}
            build_map['date'] = aws_util.get_build_info_time_format()
            for line in lines:
                part = line.split('=')
                key = part[0].strip()
                value = part[1].strip()
                if key == 'gitlabAfter':
                    build_map['commit'] = value.strip()
                if key == 'gitlabUserEmail':
                    build_map['mail'] = value.strip()
                if key == 'gitlabBranch':
                    build_map['branch'] = value.strip()
                if key == 'BUILD_NUMBER':
                    build_map['build'] = value.strip()
            commit = build_map['commit']
            short_commit = commit[:8]
            version = ('slackbud-%s-%s-%s-%s' %
                       (build_map['branch'], short_commit,
                        build_map['date'], build_map['build'])
            )
            build_info_file.write('\nversion: %s' % version)
            build_info_file.write('\nmail: %s' % build_map['mail'])
            build_info_file.write('\ncommit: %s' % build_map['commit'])
        else:
            print("Didn't find githook file. Skipping githook step.")

        build_info_file.close()

    except Exception as ex:
        print("Could not write build_info.txt file.")
        print("Reason: %s" % ex)


def post_message_to_slack_channel(title, text, color='#36a64f'):
    """
    Post a message to the #'sr-slack-deploy' channel.
    :param title:
    :param text:
    :param color:
    :return:
    """
    print("'#sr-slack-deploy' channel should get message.\n{}\n{}"
          .format(title, text))

    slack_message = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": text
            }
        ]
    }
    url = "https://hooks.slack.com/services/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"
    res = requests.post(
        url=url,
        data=json.dumps(slack_message),
        headers={"Content-type": "application/json"}
    )
    print('Slack status code: {}'.format(res.status_code))


def lambda_smoke_and_unit_test_handler(event, context):
    """
    This lambda function runs during the unit test stage.

    It first does a smoke test to verify the build dependencies
    are valid. If it fails the smoke test, it immediately send
    an e-mail, and fails the pipeline stage, so this build
    cannot proceed further.

    If the smoke test succeeds, this runs the unit tests and
    those results are stores in an S3 bucket it can be combined
    with the pylint results and sent as a different test.

    The pass/fail of the unit test is handled but the "send results"
    CodePipeline stage.

    :param event: Event that we get from CodePipeline
    :param context: Context that we get from CodePipeline
    :return: Does a pass fails of the test stage.
    """
    try:
        start_time = datetime.datetime.now()

        cp_client = boto3.client('codepipeline')
        job_id = event['CodePipeline.job']['id']
        print('CodePipeline JobID=%s' % job_id)

        # Run the smoke test with a `buddev help`
        buddev_help_event = create_slack_help_event_for_lambda()
        # do an invoke here.
        lambda_client = boto3.client('lambda')

        bud_helper_util.print_delta_time(
            start_time, 'Start: invoke buddev help')

        response = lambda_client.invoke(
            FunctionName='serverless-slackbud-dev-slackBud',  # This is buddev
            InvocationType='RequestResponse',
            LogType='Tail',  # Need to see if this give CloudWatch result.
            Payload=json.dumps(buddev_help_event)
        )

        bud_helper_util.print_delta_time(
            start_time, 'Finished: invoke buddev help')

        # look at the response status code.
        status_code = response['StatusCode']
        print('Status Code: {}'.format(status_code))

        # look at the Payload or is it LogResult?
        log_result = response['LogResult']
        base_64_decoded_log = base64.b64decode(log_result)
        string_in_log = "import_class_package=cmds.cmds_props.CmdProps"
        string_found = verify_log_contain_string(string_in_log, base_64_decoded_log)
        if not string_found:
            error_msg = 'Failed to find: {} in log result'.format(string_in_log)
            print(error_msg)
            print('Log Result: {}'.format(base_64_decoded_log))
            raise ValueError(error_msg)

        bud_helper_util.print_delta_time(
            start_time, 'Finished: Reading Log')

        payload_response_streaming_body = response['Payload']
        payload_response_bytes = payload_response_streaming_body.read()
        payload_response_decoded = payload_response_bytes.decode()
        print('"payload_response_decoded" = {}'.format(payload_response_decoded))

        res_json = json.loads(payload_response_decoded)
        print('res_json = {}'.format(res_json))

        bud_helper_util.print_delta_time(
            start_time, 'Finished: Reading Payload')

        # Look for "SlackBud Help" in the text of the response.
        # res = json.loads(res_json)
        body_text = res_json['body']
        print('body_text = {}'.format(body_text))
        body_obj = json.loads(body_text)
        slack_ui_cmd_title = body_obj['text']
        print('slack_ui_cmd_title = {}'.format(slack_ui_cmd_title))
        # Look for 'SlackBud Help'
        if slack_ui_cmd_title != 'SlackBud Help':
            error_msg = 'Failed to find "SlackBud Help" in response title. Found: {}'.format(slack_ui_cmd_title)
            print(error_msg)
            raise ValueError(error_msg)

    except Exception as ex:
        # Caught smoke test error.
        print('Smoke test had an exception.')

        # Put stack trace into logs
        template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

        # Send warning e-mail
        # fail this stage.
        cp_client.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': 'Failed Smoke Test'
            }
        )
        return 'done'

    try:
        bud_helper_util.print_delta_time(
            start_time, 'Start: Unit-Test section')

        # Continue to run the unit tests.
        print("Unit tests that don't need boto3 calls can be run in the 'test/unit_tests.py' file")
        unit_tests.run_test()

        bud_helper_util.print_delta_time(
            start_time, 'Finished: Unit-Test section')
    except AssertionError as assert_error:
        print('Unit Test Failed: {}'.format(assert_error.message))
        cp_client.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': 'Failed Unit Tests: {}'.format(assert_error.message)
            }
        )
        return 'done'

    except Exception as ex:
        print('Unit tests had an exception.')

        # Put stack trace into logs.
        template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

        cp_client.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': 'Unit Tests had exception'
            }
        )
        return 'done'

    # Pass this stage.
    print('Passed all tests. Done.')
    cp_client.put_job_success_result(
        jobId=job_id,
    )
    return 'done'


def verify_log_contain_string(verification_string, the_log):
    """
    Verify that a string is found in the log.
    :param verification_string: A log with a good result should contain this string
    :param the_log: last 4K bytes of log, it needs to be base64 decoded from boto3 call.
    :return: boolean  True if found, otherwise False
    """
    if verification_string in the_log:
        print('Found "{}" in log'.format(verification_string))
        return True
    return False


def create_slack_help_event_for_lambda():
    """
    Create an lambda event for a quick smoke test
    of latest deployment of lambda function.

    This is the command '/buddev help' and is useful
    for finding errors with invalid imports python files.
    :return:
    """
    lambda_event = {
        'body':
            'token=p95izu9Wn'
            'S9sdiqPxbCQKi3r&team_id=T025H70HY&team_domain=roku&channel_id=D5FKEN3HD&'
            'channel_name=directmessage&user_id=U5E4YURHN&user_name=asnyder&command=%2Fbuddev&text=help&'
            'response_url=https%3A%2F%2Fhooks.slack.com%2Fcommands%2FT025H70HY%2F335764193537%2FOCHFLvLdTjfGNTagKYHDANiI&'
            'trigger_id=335764193585.2187238610.ab4ad1ed10dccc59cb03000c7cd16db5',
         'resource': '/slackapi',
         'requestContext': {
             'requestTime': '26/Mar/2018:17:42:59 +0000',
             'protocol': 'HTTP/1.1',
             'resourceId': 'n9ibvg',
             'apiId': '4umlc7fcuh',
             'resourcePath': '/slackapi',
             'httpMethod': 'POST',
             'requestId': '1fc819ca-311d-11e8-90ac-856a4e02a6b5',
             'extendedRequestId': 'EXSdfGTtvHcFhUw=',
             'path': '/dev/slackapi',
             'stage': 'dev',
             'requestTimeEpoch': 1522086179182,
             'identity': {
                 'userArn': None,
                 'cognitoAuthenticationType': None,
                 'accessKey': None,
                 'caller': None,
                 'userAgent': 'Slackbot 1.0 (+https://api.slack.com/robots)',
                 'user': None,
                 'cognitoIdentityPoolId': None,
                 'cognitoIdentityId': None,
                 'cognitoAuthenticationProvider': None,
                 'sourceIp': '54.85.176.102',
                 'accountId': None
             },
             'accountId': '661796028321'
         },
        'queryStringParameters': None,
        'httpMethod': 'POST',
        'pathParameters': None,
        'headers': {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Via': '1.1 738914e1c987985551e83e7e80882749.cloudfront.net (CloudFront)',
            'Accept-Encoding': 'gzip,deflate',
            'CloudFront-Is-SmartTV-Viewer': 'false',
            'CloudFront-Forwarded-Proto': 'https',
            'X-Forwarded-For': '54.85.176.102, 204.246.180.43',
            'CloudFront-Viewer-Country': 'US',
            'Accept': 'application/json,*/*',
            'User-Agent': 'Slackbot 1.0 (+https://api.slack.com/robots)',
            'X-Amzn-Trace-Id': 'Root=1-5ab93123-4a7d097e17199de869406272',
            'Host': '4umlc7fcuh.execute-api.us-west-2.amazonaws.com',
            'X-Forwarded-Proto': 'https',
            'X-Amz-Cf-Id': 'QScRVRCqsVUjTFmu-nByLHCkxAp8BJixojsg_1nB3g1lQRgPPafa1A==',
            'CloudFront-Is-Tablet-Viewer': 'false',
            'X-Forwarded-Port': '443',
            'CloudFront-Is-Mobile-Viewer': 'false',
            'CloudFront-Is-Desktop-Viewer': 'true'
        },
        'stageVariables': None,
        'path': '/slackapi',
        'isBase64Encoded': False
    }

    return lambda_event


def create_test_event_for_lambda(entire_cli_str):
    """
    Creates the event needs to test a
    :param entire_cli_str:
    :return:
    """
    command = '/buddev2'
    str_text = {
        'command': command,
        'text': 'buildinfo content-test:master-702a945-20180111-189',
        'response_url': 'http://int-res-url.infra.sr.roku.com'
    }

    check_text = urllib.urlencode(str_text)

    request_body = 'token=jZC06GGnNtrmcpn5M2XRdGK5&' \
                   'team_id=T025H70HY&' \
                   'team_domain=roku&' \
                   'channel_id=D5FKEN3HD&' \
                   'channel_name=directmessage&' \
                   'user_id=U5E4YURHN&' \
                   'user_name=asnyder&' \
                   '{}&' \
                   'trigger_id=' \
                   '316046794321.2187238610.be67e67b9c73657d05cc0926ca7c2035'
    request_body = request_body.format(check_text)

    event = {
        "body": request_body,
        "httpMethod": "POST",
        "resource": "/slackapi",
        "queryStringParameters": None,
        "requestContext": {
            "protocol": "HTTP/1.1",
            "resourceId": "wmr22g",
            "apiId": "vd5et7bdac",
            "resourcePath": "/slackapi",
            "httpMethod": "POST",
            "path": "/qa/slackapi",
            "identity": {
                "userArn": None,
                "user": None,
                "cognitoIdentityPoolId": None,
                "userAgent": "Slackbot 1.0 (+https://api.slack.com/robots)",
                "accountId": None,
                "cognitoAuthenticationType": None,
                "accessKey": None,
                "caller": None,
                "cognitoIdentityId": None,
                "sourceIp": "52.54.222.230",
                "cognitoAuthenticationProvider": None
            },
            "requestTimeEpoch": 1518816864538,
            "requestTime": "16/Feb/2018:21:34:24 +0000",
            "requestId": "2866c7e1-1361-11e8-a608-9f2653c3ffa2",
            "accountId": "661796028321",
            "stage": "qa"
        },
        "headers": {
            "Via": "1.1 c22c4412e99cd1531f9be3528fe422a5.cloudfront.net (CloudFront)",
            "Accept-Encoding": "gzip,deflate",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Forwarded-Proto": "https",
            "X-Forwarded-For": "52.54.222.230, 54.240.144.75",
            "CloudFront-Viewer-Country": "US",
            "Accept": "application/json,*/*",
            "User-Agent": "Slackbot 1.0 (+https://api.slack.com/robots)",
            "X-Amzn-Trace-Id": "Root=1-5a874e60-d947d1a0db776180164ec920",
            "CloudFront-Is-Mobile-Viewer": "false",
            "Host": "vd5et7bdac.execute-api.us-west-2.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "z7hkeU2lJfUAO_zGLNssJLN_LPnq8d3HEHe5xwBfBjIAZLyGHM0lhQ==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "X-Forwarded-Port": "443",
            "Content-Type": "application/x-www-form-urlencoded",
            "CloudFront-Is-Desktop-Viewer": "true"
        },
        "stageVariables": None,
        "path": "/slackapi",
        "pathParameters": None,
        "isBase64Encoded": False
    }

    return event


if __name__ == '__main__':
    #  from AWS CodeBuild during build stage
    create_build_info_file()
