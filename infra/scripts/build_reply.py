import argparse
import boto3
import datetime
import logging
import requests
import json
import time
from requests_aws_sign import AWSV4Sign
from elasticsearch import Elasticsearch, RequestsHttpConnection, TransportError

JOB_URL = 'https://cidsr.eng.roku.com/view/Docker/job/docker-create-javaserver-image-v2/'

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Replies build to slack channel')
PARSER.add_argument('-v', '--version', metavar='', default=None, help='Service commit')
PARSER.add_argument('-r', '--response_url', metavar='', default=None, help='Slack response URL')
PARSER.add_argument('--status', metavar='', default=None, help='Build number')
PARSER.add_argument('-s', '--service', metavar='', default=None, help='Service Name')
args = PARSER.parse_args()

print args.version
print args.response_url
print args.status
print args.service

header = {"Content-type": "application/json"}

if int(args.status) != 0:
    slack_data = {
        "response_type": "ephemeral",
        "attachments": [
            {
                "color": "#ff3d3d",
                "text": "The Jenkins build of `%s` failed. Check Jenkins to see why..." % args.service,
                "mrkdwn_in": ["text"],
                "attachment_type": "default",
            }
        ]
    }
    r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)
    exit(0)

# To differentiate between S3_copy_script job, recsys-wiki-extractor, and the regular docker v2 job
s3_job = False
recsys_emr_job = False
recsys_wiki_extractor = False

if 'jenkins' in args.version:
    s3_job = True
elif 'recsys-emr-jar' in args.version:
    recsys_emr_job = True
elif args.service == 'recsys-wikipedia-extractor-batch':
    recsys_wiki_extractor = True

if s3_job or recsys_emr_job:
    id = args.version
else:
    url, id = args.version.split('/')

host = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
# host = "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
session = boto3.session.Session()
credentials = session.get_credentials()
region = 'us-west-2'
service = 'es'
auth = AWSV4Sign(credentials, region, service)

try:
    es_client = Elasticsearch(host=host, port=443, connection_class=RequestsHttpConnection,
                              http_auth=auth, use_ssl=True, verify_ssl=True)
except TransportError as e:
    raise ValueError("Problem in {} connection, Error is {}".format(host, e.message))

try:
    date_now = (datetime.datetime.now()).strftime('%Y-%m')
    current_index = "build_" + date_now
    data = es_client.get(index=current_index, id=id, doc_type='_all')
    repo = data.get("_source").get("repositories",None)
    author = data.get("_source").get("gitauthor",None)
    service = data.get("_source").get("service",None)
    git_commit = data.get("_source").get("gitcommit",None)
    build_time = data.get("_source").get("buildtime", None)
    git_repo = data.get("_source").get("gitrepo", None)
    passed = data.get("_source").get("coverage").get("unittestcases").get("passed")
    failed  = data.get("_source").get("coverage").get("unittestcases").get("failed")
    skipped = data.get("_source").get("coverage").get("unittestcases").get("skipped")
    line  = int(data.get("_source").get("coverage").get("coverage").get("line"))
    class_cov  = int(data.get("_source").get("coverage").get("coverage").get("class"))
    branch =  int(data.get("_source").get("coverage").get("coverage").get("branch"))
    instruction = int(data.get("_source").get("coverage").get("coverage").get("instruction"))
    slack_data = {
        "response_type" : "ephemeral",
        "text" : "Build successful!!!\n*Information of build* : `{}`".format(id),
        "attachments": [
            {"text": "*Service*: `{}`".format(service), "mrkdwn_in": ["text"], "color": "#a0ffaa"},
            {"text": "*Build time*: `{}`".format(build_time), "mrkdwn_in": ["text"], "color": "#a0ffaa"},
            {"text": "*Repository*: `{}`".format(repo),"mrkdwn_in": ["text"],"color":"#a0ffaa"},
            {"text": "*Author*: `{}`".format(author),"mrkdwn_in": ["text"],"color":"#a0ffaa"},
            {"text": "*Git Commit*: `{}`".format(git_commit),"mrkdwn_in": ["text"],"color":"#a0ffaa"},
            {"text": "*Git Repo*: `{}`".format( git_repo),"mrkdwn_in": ["text"],"color":"#a0ffaa"}
        ]
    }
    if not s3_job and not recsys_wiki_extractor and not recsys_emr_job:
        slack_data['attachments'].append({"text": "*Unittest Case Passed*: `{}`".format(passed), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Unittest Case Failed*: `{}`".format(failed), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Unittest Case Skipped*: `{}`".format(skipped), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Line Code Coverage*: *`{}%`*".format(line), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Class Code Coverage*: *`{}%`*".format(class_cov), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Branch Code Coverage*: *`{}%`*".format(branch), "mrkdwn_in": ["text"], "color": "#a0ffaa"})
        slack_data['attachments'].append({"text": "*Instruction Code Coverage*: *`{}%`*".format(instruction), "mrkdwn_in": ["text"], "color": "#a0ffaa"})

    if recsys_emr_job:
        del slack_data['attachments'][2]  # Remove repository key since it does not apply to this build.

    r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)
    logging.info("Posted on this URL: {}".format(args.response_url))
    logging.info("Posted this DATA {}".format(slack_data))
    logging.info("Response Code for POST : {}".format(r.status_code))
    logging.info("Reason: {}".format(r.reason))

    if s3_job or recsys_emr_job:
        version = args.version
    else:
        version = args.version.split(':')[1]

    # Get service info from ServiceInfo table on DDB
    boto3.setup_default_session(profile_name='661796028321', region_name='us-west-2')
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    slack_session_table = dynamodb.Table('SlackBudSession')
    service = services_table.get_item(Key={'serviceName': args.service})
    region_map = service['Item']['serviceInfo']['regions']

    if not int(failed):
        env_buttons = []
        count = 1

        if 'dev' in region_map:
            env_buttons.append(
                {
                    "name": "button%s" % count,
                    "text": 'DEV',
                    "type": "button",
                    "value": 'dev'
                }
            )
            count += 1
        if 'qa' in region_map:
            env_buttons.append(
                {
                    "name": "button%s" % count,
                    "text": 'QA',
                    "type": "button",
                    "value": 'qa'
                }
            )
            count += 1
        if 'dev' in region_map and 'qa' in region_map:
            env_buttons.append(
                {
                    "name": "button%s" % count,
                    "text": 'DEV & QA',
                    "type": "button",
                    "value": 'dev/qa'
                }
            )
            count += 1
        if 'prod' in region_map:
            env_buttons.append(
                {
                    "name": "button%s" % count,
                    "text": 'PROD',
                    "type": "button",
                    "value": 'prod',
                    "style": "danger"
                }
            )
            count += 1
        env_buttons.append(
            {"name": "button%s" % str(count),
             "text": 'Cancel', "type": "button",
             "value": 'cancel'}
        )

        text = "If you would like to deploy `(%s)` to service `(%s)`, " \
               "please select the environment in which you would like to " \
               "do so. If you do not want to do a deploy, press cancel." % (version, args.service)

        # Create a session id. (just use clock with milli-second accuracy.)
        session_id = int(round(time.time() * 1000))

        # expire the row in one hour.
        ttl = int(round(time.time()) + 3600)

        print('Storing original message: session_id={}, text={}'.format(
            session_id,
            text)
        )

        slack_session_table.put_item(
            Item={
                'slackBudSessionId': str(session_id),
                'text': text,
                'ttl': ttl
            }
        )
        callback = 'callback_default_CmdDeploy_env_' + str(session_id)

        slack_data = {
            "response_type": "ephemeral",
            "text": text,
            "attachments": [
                {
                    "fallback": "CmdDeploy",
                    "callback_id": callback,
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": env_buttons
                }
            ]
        }
        r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)
    else:
        slack_data = {
            "response_type": "ephemeral",
            "text": "A unit test case failed and the build will not be available for deployment.",
        }
        r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)

except TransportError as e:
    slack_data = {
        "response_type": "ephemeral",
        "text": "*Unable to gather build info...*",
    }
    header = {"Content-type": "application/json"}
    r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)
    logging.info("Posted on this URL: {}".format(args.response_url))
    logging.info("Posted this DATA {}".format(slack_data))
    logging.info("Response Code for POST : {}".format(r.status_code))
    logging.info("Reason: {}".format(r.reason))
    raise ValueError("Can not get data with id: {} on index: {}, error is {}".format(args.version, current_index, e))
