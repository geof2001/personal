"""Smoke tests run against the deployed /buddev lambda"""
from __future__ import print_function
import json
import boto3

LAMBDA = boto3.client('lambda')


def invoke_help_commands():
    print('Start help commands')

    payload = {
        'body': 'token=p95izu9WnS9sdiqPxbCQKi3r&team_id=T025H70HY&team_domain=roku&channel_id=D5FKEN3HD&channel_name=directmessage&user_id=U5E4YURHN&user_name=asnyder&command=%2Faliasdev&text=dns+help&response_url=https%3A%2F%2Fhooks.slack.com%2Fcommands%2FT025H70HY%2F296051460327%2FVqN5VAb0Ai6Q8oyJv81u0JbP&trigger_id=294470313569.2187238610.b98ccbfb96ff6ee48301a03eb823861a',
        'resource': '/slackapi',
        'requestContext':
            {
                'requestTime': '06/Jan/2018:02:03:09 +0000',
                'protocol': 'HTTP/1.1',
                'resourceId': 'n9ibvg',
                'apiId': '4umlc7fcuh',
                'resourcePath': '/slackapi',
                'httpMethod': 'POST',
                'requestId': 'be5764e3-f285-11e7-a995-fd5b99351645',
                'path': '/dev/slackapi',
                'accountId': '661796028321',
                'requestTimeEpoch': 1515204189606,
                'identity':
                    {
                        'userArn': None,
                        'cognitoAuthenticationType': None,
                        'accessKey': None,
                        'caller': None,
                        'userAgent': 'Slackbot 1.0 (+https://api.slack.com/robots)',
                        'user': None,
                        'cognitoIdentityPoolId': None,
                        'cognitoIdentityId': None,
                        'cognitoAuthenticationProvider': None,
                        'sourceIp': '54.89.92.4',
                        'accountId': None
                    },
                'stage': 'dev'
            },
        'queryStringParameters': None,
        'httpMethod': 'POST',
        'pathParameters': None,
        'headers':
            {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Via': u'1.1 fd885dc16612d4e9d70f328fd0542052.cloudfront.net (CloudFront)',
                'Accept-Encoding': 'gzip,deflate',
                'CloudFront-Is-SmartTV-Viewer': 'false',
                'CloudFront-Forwarded-Proto': 'https',
                'X-Forwarded-For': '54.89.92.4, 54.182.230.54',
                'CloudFront-Viewer-Country': 'US',
                'Accept': 'application/json,*/*',
                'User-Agent': 'Slackbot 1.0 (+https://api.slack.com/robots)',
                'X-Amzn-Trace-Id': 'Root=1-5a502e5d-55a4da5d1595735408259319',
                'Host': '4umlc7fcuh.execute-api.us-west-2.amazonaws.com',
                'X-Forwarded-Proto': 'https',
                'X-Amz-Cf-Id': 'iSGUQhIWKNliufAgvWPfegPrXGSbbgWHnZDfqqc6knPHs5AAZMRtKg==',
                'CloudFront-Is-Tablet-Viewer': 'false',
                'X-Forwarded-Port': '443',
                'CloudFront-Is-Mobile-Viewer': 'false',
                'CloudFront-Is-Desktop-Viewer': 'true'
            },
        'stageVariables': None,
        'path': '/slackapi',
        'isBase64Encoded': False
    }

    response = LAMBDA.invoke(
        FunctionName="serverless-slackbud-dev-slackBud",
        InvocationType="Event",
        Payload=json.dumps(payload)
    )


if __name__ == '__main__':
    try:
        invoke_help_commands()

        print('SUCCESS: Smoke tests finished')
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        print('/nFAIL: Smoke tests failed.')
