"""Module handles the pipeline lambda."""
from __future__ import print_function
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

import json
import os
import requests
import boto3
import aws_util
from aws_util import CodePipelineStageError
import bud_helper_util


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

    recipients = ['asnyder@roku.com', 'qzhong@roku.com', 'areynolds@roku.com']
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
            update_lambda_function_code(
                'gitdiff-prod',
                s3bucket, s3key, True
            )
            update_lambda_function_code(
                'pipeline-send-test-results',
                s3bucket, s3key
            )
            update_lambda_function_code(
                'pipeline-deploy-prod',
                s3bucket, s3key
            )
            update_lambda_function_code(
                'pipeline-deploy-dev',
                s3bucket, s3key
            )
        elif deploy_stage == 'prod':
            slack_command = '/bud'
            update_lambda_function_code(
                'serverless-slackbud-prod-slackBud',
                s3bucket, s3key, True
            )
        else:
            error_msg = "Unknown deploy stage. Expected 'dev'|'prod'. Was %s."\
                        % deploy_stage
            raise CodePipelineStageError(error_msg)

        cp_client.put_job_success_result(
            jobId=job_id,
        )

        # Look inside the zip file to get the build_info.txt
        extra_build_info = get_build_info_from_zip(s3bucket, s3key)
        slack_msg_text = "Deployed to %s" % slack_command
        if extra_build_info is not None:
            slack_msg_text += '\nversion: %s' % extra_build_info

        # Put a success message on a Slack Channel
        post_message_to_slack_channel(
            title="Deployment",
            text=slack_msg_text
        )

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

    return 'done'


def get_build_info_from_zip(s3bucket, s3key):
    """Get the build info from the zip file.
    Handle errors by logging and returning None"""
    try:
        s3_client = boto3.client('s3')
        s3_client.download_file(
            s3bucket,
            s3key,
            '/tmp/deployed.zip'
        )

        bud_helper_util.unzip_file('/tmp/deployed.zip', '/tmp/deployed')

        txt_files = bud_helper_util.get_files_in_dir_by_type(
            '/tmp/deployed', 'txt'
        )

        if len(txt_files) > 0:
            build_info_map =\
                bud_helper_util.read_key_value_file_to_dictionary(
                    '/tmp/deployed/build_info.txt',
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


def update_lambda_function_code(function_name, s3_bucket, s3_key,
                                fail_stage_on_error=False):
    """Update code but handle and report errors gracefully"""
    try:
        print('Updating code for lambda function: %s' % function_name)
        lambda_client = boto3.client('lambda')
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            S3Bucket=s3_bucket,
            S3Key=s3_key
        )

        # If status code is 200 return success.
        status_code = response['ResponseMetadata']['HTTPStatusCode']
        if status_code == 200:
            print('SUCCESS: Deployed function: %s' % function_name)
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
    """Post a status message to the slack channel"""
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
    print('Slack status code: %s' % res.status_code)


if __name__ == '__main__':
    #  from AWS CodeBuild during build stage
    create_build_info_file()
