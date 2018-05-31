"""Utility class for Slack UI responses."""
from __future__ import print_function

import json
import requests

HEADER = {"Content-type": "application/json"}

# Put all Slack channels that have a webhook here.
SLACK_NAME_TO_WEBHOOK_MAP = {
    'sr-slack-deploy': 'https://hooks.slack.com/services/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'
}


# Exception class to pass messages back to Slack UI
class ShowSlackError(Exception):
    """Raise this exception when you want to show an error in Slack UI."""
    def __init__(self, *args):
        Exception.__init__(self, *args)


def respond(err, res=None):
    """Response wrapper needed for all Slack UI responses."""
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def ephemeral_text_response(text):
    """
    User for text response that needs just simple ephemeral text which
    will disappear when done.
    :param text:
    :return:
    """
    return respond(
        None,
        {
            "response_type": "ephemeral",
            "text": text
        }
    )


# Generate Slack response with title and text.
# If title is None, no title section is included.
def text_command_response(title, text, color="#a0ffaa", post=False, response_url='', is_public=False):
    """Slack UI response when needing standard text."""
    print('Inside beginning text_command_response with params title:{}, '
          'text:{}, color:{}, post:{}, response_url:{}, '
          'is_public:{}'.format(title, text, color, str(post), response_url, str(is_public)))

    response_type = 'ephemeral'
    if is_public:
        response_type = 'in_channel'

    slack = {
        "response_type": response_type,
        "attachments": [
            {
                "text": "%s" % text,
                "mrkdwn_in": ["text"],
                "color": "%s" % color
            }
        ]
    }

    if title:
        slack["text"] = title
    if post:
        print('In Post')
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    print('Slack Dictionary returned:')
    print(slack)

    return respond(None, slack)


# Generate a response to an exception
def error_response(text, post=False, response_url=''):
    """Slack UI response for errors."""

    slack = {
        "response_type": "ephemeral",
        "attachments": [
            {
                "text": "%s" % text,
                "mrkdwn_in": ["text"],
                "color": "#ff3d3d"
            }
        ]
    }
    if post:
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    return respond(None, slack)


# Generate Slack response asking for confirmation
def ask_for_confirmation_response(
        text, fallback, callback_id,
        danger_style=False,
        cancel=False,
        post=False,
        response_url='',
        is_public=False):
    """Slack UI response when needing a confirmation."""

    response_type = 'ephemeral'
    if is_public:
        response_type = "in_channel"

    slack = {
        "response_type": response_type,
        "text": "%s" % text,
        "attachments": [
            {
                "fallback": fallback,
                "callback_id": callback_id,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "button1",
                        "text": "Yes",
                        "type": "button",
                        "value": "yes"
                    },
                    {
                        "name": "button2",
                        "text": "No",
                        "type": "button",
                        "value": "no"
                    },
                ]
            }
        ],
    }

    if response_type == 'ephemeral':
        original_message_text = {
            'text': text
        }
        slack['original_message'] = original_message_text


    if danger_style:
        slack["attachments"][0]["actions"][0]["style"] = "danger"
    if cancel:
        cancel_button = {
            "name": "button3",
            "text": "Cancel",
            "type": "button",
            "value": "cancel"
        }
        slack['attachments'][0]['actions'].append(cancel_button)
    if post:
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    return respond(None, slack)


def loading_msg(response_url):
    """Shows the Processing... message on Slack UI."""

    loading = {
        "response_type": "ephemeral",
        "text": "_Processing..._"
    }
    requests.post(response_url, data=json.dumps(loading), headers=HEADER)


# Prompt Environments
def prompt_envs(text, fallback, callback_id,
                region_map,
                dev_and_qa=True,
                post=False,
                response_url=''):
    """Slack UI response when needing a confirmation."""

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
    if dev_and_qa and 'dev' in region_map and 'qa' in region_map:
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

    slack = {
        # "response_type": "in_channel",
        "response_type": "ephemeral",
        "text": text,
        "attachments": [
            {
                "fallback": fallback,
                "callback_id": callback_id,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": env_buttons
            }
        ]
    }
    if post:
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    return respond(None, slack)


# Prompt regions
def prompt_regions(text, fallback, callback_id, regions, post=False,
                   response_url='', all_regions=True, missing_regions=None):
    """Slack UI response when needing a confirmation."""

    region_buttons = []
    count = 0
    for region in regions:
        region_buttons.append(
            {
                "name": "button1",
                "text": region.upper(),
                "type": "button", "value": region
            }
        )
        count += 1
    if all_regions:
        if missing_regions:
            all_region_str = '/'.join(regions + missing_regions)
            region_buttons.append(
                {"name": "button%s" % str(count + 1),
                 "text": 'ALL REGIONS AVAILABLE', "type": "button",
                 "value": all_region_str}
            )
            count += 1
        elif len(regions) > 1:
            region_buttons.append(
                {"name": "button%s" % str(count + 1),
                 "text": 'ALL REGIONS AVAILABLE', "type": "button",
                 "value": '/'.join(regions)}
            )
            count += 1

    region_buttons.append(
        {"name": "button%s" % str(count + 1),
         "text": 'Cancel', "type": "button",
         "value": 'cancel'}
    )

    slack = {
        # "response_type": "in_channel",
        "response_type": "ephemeral",
        "text": text,
        "attachments": [
            {
                "fallback": fallback,
                "callback_id": callback_id,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": region_buttons
            }
        ]
    }
    if post:
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    return respond(None, slack)


# Prompt deploy images
def prompt_images(es_list, text, fallback, callback_id):
    """Slack UI response when prompting deploy images."""

    image_buttons = []
    count = 0
    for hit in es_list:
        image = hit['_source']['dockertag']
        splitter = image.split('-')
        del splitter[1]
        image_text = '-'.join(splitter)

        if 'jenkins' in image:
            image_text = image
        elif 'recsys-emr-jar-with-dependencies' in image:
            # Turn str
            # 's3://roku-docker-registry/sr/jars/recsys/recsys-emr-jar-with-dependencies-20180524-140658-122.jar'
            # into recsys-emr-jar-20180524-122
            splitter = image.split('/')
            recsys_jar_str = splitter[-1]
            recsys_jar_str_without_dot = recsys_jar_str.split('.')[0]
            splitter = recsys_jar_str_without_dot.split('-')
            del splitter[6]  # Remove time in minutes
            del splitter[4]  # Remove "dependencies"
            del splitter[3]  # Remove "jar"
            image_text = '-'.join(splitter)

        image_buttons.append(
            {
                "name": "button1",
                "text": image_text,
                "type": "button", "value": image
            }
        )
        count += 1
    image_buttons.append(
        {"name": "button%s" % str(count + 1),
         "text": 'Unchanged/Current Version', "type": "button",
         "value": 'Unchanged/Current Version'}
    )
    count += 1
    image_buttons.append(
        {"name": "button%s" % str(count + 1),
         "text": 'Cancel', "type": "button",
         "value": 'cancel'}
    )

    slack = {
        # "response_type": "in_channel",
        "response_type": "ephemeral",
        "text": text,
        "attachments": [
            {
                "fallback": fallback,
                "callback_id": callback_id,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": image_buttons
            }
        ]
    }
    return respond(None, slack)


# Generate Slack response asking for confirmation for changeset
def prompt_changeset(text, fallback, callback_id, rollback=False, serverless=False):
    """Slack UI response prompting changeset confirmation."""

    if not rollback:
        slack = {
            # "response_type": "in_channel",
            "response_type": "ephemeral",
            "text": "%s" % text,
            "attachments": [
                {
                    "fallback": fallback,
                    "callback_id": callback_id,
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "button1",
                            "text": "DEPLOY",
                            "type": "button",
                            "value": "false"
                        },
                        {
                            "name": "button2",
                            "text": "CREATE CHANGESET",
                            "type": "button",
                            "value": "true"
                        },
                        {
                            "name": "button3",
                            "text": "Cancel",
                            "type": "button",
                            "value": "cancel"
                        }

                    ]
                }
            ]
        }
        # Remove changeset button option if serverless flag is set true
        if serverless:
            del slack['attachments'][0]['actions'][1]
    else:
        slack = {
            # "response_type": "in_channel",
            "response_type": "ephemeral",
            "text": "%s" % text,
            "attachments": [
                {
                    "fallback": fallback,
                    "callback_id": callback_id,
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "button1",
                            "text": "ROLLBACK",
                            "type": "button",
                            "value": "false",
                            "style": "danger"
                        },
                        {
                            "name": "button3",
                            "text": "Cancel",
                            "type": "button",
                            "value": "cancel"
                        }

                    ]
                }
            ]
        }
    return respond(None, slack)


def can_post_to_channel(slack_channel_name):
    """
    Looks up channel name to see if it has a webhook url we can post to.
    :param slack_channel_name: name of slack channel
    :return: True if you can post to this channel otherwise False
    """
    webhook_url = SLACK_NAME_TO_WEBHOOK_MAP.get(slack_channel_name, None)
    if webhook_url is None:
        return False
    return True


def post_message_to_slack_channel(slack_channel_name, title, text, color='#36a64f'):
    """
    Post a message to a slack-channel, and return True it is was a success.
    If channel is not avail for posting, or fails return False.

    :param slack_chanel_name:
    :param title: Title to include with SlackChannel
    :param text: Text to post to slack channel
    :param color: color or use the default color
    :return: True is the message posted. Otherwise False
    """
    # Verify that we can even post to this channel
    webhook_url = SLACK_NAME_TO_WEBHOOK_MAP.get(slack_channel_name, None)
    if webhook_url is None:
        print('Could not find a webhook for channel: {}'.format(slack_channel_name))
        return False

    slack_message = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": text
            }
        ]
    }

    try:
        print('posting to slack_channel: {}'.format(slack_channel_name))
        res = requests.post(
            url=webhook_url,
            data=json.dumps(slack_message),
            headers={"Content-type": "application/json"}
        )
        print('Slack status code: %s' % res.status_code)
        return True
    except Exception as ex:
        print('Failed to post to: {}'.format(slack_channel_name))
        return False