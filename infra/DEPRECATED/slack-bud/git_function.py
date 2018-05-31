"""Downloads code from repo into S3."""
import sys
import os
import shutil
import time
import boto3
import gitlab
import git


GITLAB_URL = 'https://gitlab.eng.roku.com/'
REPO_NAME = "slack-bud"
GIT_TOKEN = 'B8cREFMrfFKF7MKWi8jP'
REPO_NAME_FOR_ZIP = "slack-bud-bare-repo-files"
BUCKET_NAME = "sr-infra-lambda-function-zipfiles"


def get_latest_repo():
    """Read latest code from Gitlab repo"""
    current_dir_path = os.getcwd()
    if os.path.exists(current_dir_path +'/' + REPO_NAME_FOR_ZIP):
        sys.stdout.write(
            "Old repository already exist into folder, removing now.."
        )
        shutil.rmtree(current_dir_path +'/' + REPO_NAME_FOR_ZIP)
    try:
        git_connection = gitlab.Gitlab(GITLAB_URL, GIT_TOKEN)
        git_connection.auth()

        # Search Project by name and get project object by id.
        project = git_connection.projects.list(search=REPO_NAME)
        if project is None:
            sys.stderr.write(
                "Repository {} is not found in gitlab {}, "
                "Please check again".format(REPO_NAME, GITLAB_URL)
            )

        project_id = project[0].id
        project_params = git_connection.projects.get(project_id)
        git_project_url = project_params.http_url_to_repo

        try:
            sys.stdout.write("Fetching a new repository now...")
            git.Git().clone(git_project_url)
        except:
            sys.stderr.write("Error in Git Cloning")
        # Rename git repo to desired zip name

        os.rename(current_dir_path + '/' + REPO_NAME, current_dir_path + '/' + REPO_NAME_FOR_ZIP)
    except GitlabError as e:
        sys.stderr.write("Gitlab exception : {}", format(e.message))


def zip_repo():
    """Zip the raw code from repo"""
    current_dir_path = os.getcwd()
    if os.path.exists(current_dir_path + '/' + REPO_NAME_FOR_ZIP):
        shutil.make_archive(
            REPO_NAME_FOR_ZIP,
            'zip',
            current_dir_path + '/' + REPO_NAME_FOR_ZIP)
    else:
        sys.stderr.write("Please check repo, might be not there?")


def upload_zip_file_to_s3(bucket_name):
    """Upload ZIP file to S3"""

    sts = boto3.client('sts')
    session = sts.assume_role(
        RoleArn="arn:aws:iam::661796028321:role/bud-lambda-2",
        RoleSessionName='test-session'
    )
    # role_obj = "arn:aws:iam:assume:role/qa"
    # print(session['Credentials']['AccessKeyId'])
    s3 = boto3.client(
        's3', aws_access_key_id=session['Credentials']['AccessKeyId'],
        aws_secret_access_key=session['Credentials']['SecretAccessKey'],
        aws_session_token=session['Credentials']['SessionToken'])
    s3.upload_file("slack-bud-repo-file-test.zip", bucket_name, "slack-bud-repo-file-test.zip")


def lambda_handler(event, context):
    """Entry-point for a lambda function."""
    t1 = time.time()
    get_latest_repo()
    zip_repo()
    upload_zip_file_to_s3(BUCKET_NAME)
    t2 = time.time()
    print("Total time taken by file fetch and zip is {} seconds".format(t2-t1))
