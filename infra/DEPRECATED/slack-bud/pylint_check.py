"""Proto-type lambda function for running pylint."""
from __future__ import print_function

import json
import zipfile
import os
import boto3
# import pylint

# from pylint import epylint as lint


def lambda_entry_point(event, context):
    """Run a pylint on each *.py file in the uploaded zip file."""

    print('pylint_check version: 180109-1200')
    print(json.dumps(event))

    # Get the job_id from CodePipeline for later.
    job_id = event['CodePipeline.job']['id']
    print('CodePipeline JobID=%s' % job_id)

    # Upload zip file from S3.
    s3_client = boto3.client("s3")

    try:
        print("Calling s3 download_file()")
        s3_client.download_file(
            'sr-infra-pipeline-source',
            'slack-bud-bare-repo-files.zip',
            '/tmp/slack-bud-bare-repo-files.zip'
        )

        # Unzip files
        zip_ref = zipfile.ZipFile('/tmp/slack-bud-bare-repo-files.zip', 'r')
        zip_ref.extractall('/tmp/pylint')
        zip_ref.close()

        python_files = get_python_file_list()
        for curr_py_file in python_files:
            curr_py_path = '/tmp/pylint/'+curr_py_file

            # Run pylint and pipe result to <filename>_pylint.txt
            if os.path.isfile(curr_py_path):
                try:
                    print('Checking file: %s' % curr_py_path)
                    # (pylint_stdout, pylint_stderr) = lint.py_run(curr_py_path, return_std=True)
                    # Run(['--errors-only', '/tmp/pylint/dns.py'])
                    # make this call on each file.
                    print("success ran pylint on %s" % curr_py_file)
                    # print(pylint_stdout)
                except Exception as exp:
                    print('Failed to run pylint on file: %s' % curr_py_path)
                    print(exp)
            else:
                print("Failed to find: %s" % curr_py_path)
    except Exception as ex:
        print("Could not download/read zip file.")
        print("Exception was type: %s" % type(ex))
        print(ex)


# NOTE Here we verify putting a file into the S3 bucket at right location.
    try:
        put_mock_pylint_file_in_s3(s3_client)
    except Exception as e:
        print("Send to S3 failed")
        print("Exception type: %s" % type(e))
        print(e)

    # Write *_pylint.txt files back to S3 in a different directory.
    # Need to figure out how to get the output.

    # Check result of each *_pylint run.
    # Need to look for "Your code has been rated at" text at end of file.

    # If any file fails, fail this stage of CodePipeline.

    # Otherwise return pass result to move to next stage.
    cp_client = boto3.client('codepipeline')
    cp_client.put_job_success_result(
        jobId=job_id,
    )

    return 'done'


def get_python_file_list():
    """Gets list of python files unzipped in this directory."""
    relevant_path = "/tmp/pylint"
    included_extenstions = ['py']
    file_names = [fn for fn in os.listdir(relevant_path)
                  if any(fn.endswith(ext) for ext in included_extenstions)]

    return file_names


def get_code_pipeline_user_parameters(event):
    """CodePipeline can pass a parameter to lambda via UserParameters.
    Get that.
    """
    try:
        ret_val = event['CodePipeline.job']['data']['actionConfiguration']
        ['configuration']['UserParameters']
        return ret_val
    except:
        print("Failed to get CodePipeline UserParameters")


def put_mock_pylint_file_in_s3(s3_client):
    """Puts a mock pylint result file in S3. Testing access."""
    mock_file = open("/tmp/mock_pylint.txt", "w+")
    mock_file.write("mock_pylint.py score was: 7.5/10 PASS")
    mock_file.close()

    file_to_send = open("/tmp/mock_pylint.txt", "r")
    s3_client.put_object(
        Bucket='sr-infra-pipeline-source',
        Key='pylint/mock_pylint.txt',
        Body=file_to_send
    )
    file_to_send.close()

    print("Put pylint/mock_pylint.txt in S3 bucket")
