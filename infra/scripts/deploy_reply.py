import time
import argparse
import requests
import json
import urllib2
import boto3

time.sleep(3)

JOB_URL = 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-service-stack-v2/'
SERVERLESS_JOB_URL = 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-serverless-lambda/'

ENVIRONMENTS = {
    '638782101961': 'dev',
    '181133766305': 'qa',
    '886239521314': 'prod'
}

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Replies build to slack channel')
PARSER.add_argument('-v', '--version', metavar='', default=None, help='Service commit')
PARSER.add_argument('-r', '--response_url', metavar='', default=None, help='Slack response URL')
PARSER.add_argument('-s', '--service', metavar='', default=None, help='Service Name')
PARSER.add_argument('-a', '--accounts', metavar='', default=None, help='AWS Accounts')
PARSER.add_argument('-c', '--changeset', metavar='', default=None, help='Changeset boolean')
PARSER.add_argument('-n', '--buildnum', metavar='', default=None, help='Build number')
PARSER.add_argument('--regions', metavar='', default=None, help='AWS Regions')
PARSER.add_argument('--stack', metavar='', default=None, help='Stack Name')
args = PARSER.parse_args()

header = {"Content-type": "application/json"}
version = args.version.split(':')[1]

accounts = args.accounts.split(',')
envs = [ENVIRONMENTS[account] for account in accounts]
env_str = ','.join(envs)

build_url = JOB_URL + args.buildnum

if 'serverless' in version.lower():
    build_url = SERVERLESS_JOB_URL + args.buildnum

json_url = build_url + '/api/json'
print json_url
console_url = build_url + '/console'
console = json.loads(urllib2.urlopen(json_url).read())
build_result = console['result']
print 'BUILD_RESULT: %s' % build_result

boto3.setup_default_session(profile_name=args.accounts, region_name=args.regions)

cf = boto3.client('cloudformation')

if build_result == 'FAILURE':
    slack_data = {
        "response_type": "ephemeral",
        "replace_original": False,
        "attachments": [
            {
                "color": "#ff3d3d",
                "text": "The deployment of `[%s][%s][%s][%s]` failed... Check why at ```%s```"
                        % (args.service, version, args.regions, env_str, console_url),
                "mrkdwn_in": ["text"],
                "attachment_type": "default",
            }
        ]
    }
    r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)
    exit(0)

stack_events = cf.describe_stack_events(StackName=args.stack)
current_status = stack_events['StackEvents'][0]['ResourceStatus']

if args.changeset == 'true':
    slack_data = {
        "response_type": "ephemeral",
        "replace_original": False,
        "attachments": [
            {
                "color": "#a0ffaa",
                "text": "A change set for `[%s][%s][%s][%s]` was successfully created!"
                        % (args.service, version, args.regions, env_str),
                "mrkdwn_in": ["text"],
                "attachment_type": "default",
            }
        ]
    }
elif 'rollback' in current_status.lower():
    slack_data = {
        "response_type": "ephemeral",
        "replace_original": False,
        "attachments": [
            {
                "color": "#ff3d3d",
                "text": "The deployment of `[%s][%s][%s][%s]` was rolled back with the status of `[%s]`"
                        % (args.service, version, args.regions, env_str, current_status),
                "mrkdwn_in": ["text"],
                "attachment_type": "default",
            }
        ]
    }
else:
    slack_data = {
        "response_type": "ephemeral",
        "replace_original": False,
        "attachments": [
            {
                "color": "#a0ffaa",
                "text": "The deployment of `[%s][%s][%s][%s]` has completed with the status of `[%s]`"
                        % (args.service, version, args.regions, env_str, current_status),
                "mrkdwn_in": ["text"],
                "attachment_type": "default",
                }
            ]
        }
r = requests.post(args.response_url, data=json.dumps(slack_data), headers=header)

