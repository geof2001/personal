"""Utility class for Slack UI responses."""
from __future__ import print_function

import json
import requests

HEADER = {"Content-type": "application/json"}


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


# Generate Slack response with title and text.
# If title is None, no title section is included.
def text_command_response(title, text, color="#a0ffaa", post=False, response_url=''):
    """Slack UI response when needing standard text."""
    slack = {
        "response_type": "in_channel",
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
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

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
        response_url=''):
    """Slack UI response when needing a confirmation."""

    slack = {
        "response_type": "in_channel",
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
        ]
    }

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
                all_envs=False,
                post=False,
                response_url=''):
    """Slack UI response when needing a confirmation."""

    if all_envs:
        slack = {
            "response_type": "in_channel",
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
                            "text": "DEV",
                            "type": "button",
                            "value": "dev",
                        },
                        {
                            "name": "button2",
                            "text": "QA",
                            "type": "button",
                            "value": "qa"
                        },
                        {
                            "name": "button3",
                            "text": "STG",
                            "type": "button",
                            "value": "stg"
                        },
                        {
                            "name": "button4",
                            "text": "PROD",
                            "type": "button",
                            "value": "prod",
                            "style": "danger"
                        },
                        {
                            "name": "button5",
                            "text": "Cancel",
                            "type": "button",
                            "value": "cancel",
                        }
                    ]
                }
            ]
        }
    else:
        slack = {
            "response_type": "in_channel",
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
                            "text": "DEV",
                            "type": "button",
                            "value": "dev",
                        },
                        {
                            "name": "button2",
                            "text": "QA",
                            "type": "button",
                            "value": "qa"
                        },
                        {
                            "name": "button3",
                            "text": "DEV & QA",
                            "type": "button",
                            "value": "dev_and_qa"
                        },
                        {
                            "name": "button4",
                            "text": "PROD",
                            "type": "button",
                            "value": "prod",
                            "style": "danger"
                        },
                        {
                            "name": "button5",
                            "text": "Cancel",
                            "type": "button",
                            "value": "cancel",
                        }
                    ]
                }
            ]
        }
    if post:
        requests.post(response_url, data=json.dumps(slack), headers=HEADER)
        return None

    return respond(None, slack)


# Prompt regions
def prompt_regions(text, fallback, callback_id, regions, post=False, response_url=''):
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
    region_buttons.append(
        {"name": "button%s" % str(count + 1),
         "text": 'Cancel', "type": "button",
         "value": 'cancel'}
    )

    slack = {
        "response_type": "in_channel",
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
        image_buttons.append(
            {
                "name": "button1",
                "text": hit['_source']['dockertag'],
                "type": "button", "value": hit['_source']['dockertag']
            }
        )
        count += 1
    image_buttons.append(
        {"name": "button%s" % str(count + 1),
         "text": 'Cancel', "type": "button",
         "value": 'cancel'}
    )

    slack = {
        "response_type": "in_channel",
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


# Generate Slack response asking for confirmation for chabngeset
def prompt_changeset(text, fallback, callback_id):
    """Slack UI response prompting changeset confirmation."""

    slack = {
        "response_type": "in_channel",
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
                        "value": "true"
                    },
                    {
                        "name": "button2",
                        "text": "No",
                        "type": "button",
                        "value": "false"
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
