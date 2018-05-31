"""Does the gitdiff command """
from __future__ import print_function

import json
import boto3
import slack_ui_util


print("loading lambda client")
LAMBDA = boto3.client('lambda')


def handle_git_diff(builds, response_url, args):
    """Entry-point for this function."""
    jira = args.jira
    print("JIRA VALUE PASSED :{}".format(jira))

    if 'help' in builds:
        title = "Get git commit information between two docker builds"
        text = "*Format:* _/bud builddiff <build1> <build2> <optional --jira>_\n" \
               "*Example:*\n" \
               "*Usage1*: _/bud builddiff content-test:master-e47a45d-20171113-176" \
               " content-test:master-a64b119-20171101-163_\n" \
               "*Usage2*:_/bud builddiff content-test:master-e47a45d-20171113-176" \
               " content-test:master-a64b119-20171101-163 --jira_\n" \
               "*<build1>* _Current build_\n" \
               "*<build2>* _Older build_\n" \
               "*<--jira>*: _Pass '--jira' in argument to get " \
               "JIRA associate between two builds_"
        return slack_ui_util.text_command_response(title, text, "#00b2ff")
    try:
        if not jira:
            build1, build2 = builds.split(" ")
            print("Build1: {}".format(build1))
            print("Build2: {}".format(build2))
            payload = {
                "build1": build1,
                "build2": build2,
                "url": response_url,
                "jira": False
            }
        else:
            payload = {}
            build1, build2, jira = builds.split(" ")
            payload["build1"] = build1
            payload["build2"] = build2
            payload["url"] = response_url
            payload["jira"] = True
        response = LAMBDA.invoke(
            FunctionName="gitdiff-prod",
            InvocationType="Event",
            Payload=json.dumps(payload)
        )
        print(response)
        return slack_ui_util.respond(
            None,
            {
                "response_type": "ephemeral",
                "text":
                    "*Work is in progress, Please wait for a moment.....*"
            }
        )
    except ValueError:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "in_channel",
                "text": "*Please check the build argumets ,provide "
                        "in `/bud builddiff <build1> <build2> "
                        "--jira` format*"
            }
        )
