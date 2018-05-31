"""This module handles the build command of bud calls on Slack."""
import urllib2
import logging
import boto3
import slack_ui_util

TOKEN = 'REGRESSIONISGOOD'
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
BUILD_METHODS = {'docker_build_V2': 'https://cidsr.eng.roku.com/view/Docker/job/docker-create-javaserver-image-v2/'}


def handle_build(command, args, user, response_url):
    """
    Entry point when build command is called via Slack.

    :param command: - Command user typed on Slack
    :param args: - Flags of the command
    :param user: - User that called the command
    :param response_url: - Slack URL to post to
    """

    # Help message
    if 'help' in command.strip():
        title = "Builds the specified service."
        text = "*Format:* _/bud build -s <service>_\n\nExample: _/bud " \
               "build -s content_\n",
        return slack_ui_util.text_command_response(title, text, "#00b2ff")

    # If no service flag was given
    if not args.services:
        text = 'Unable to build. A service was not specified. Use the flag ' \
               '`-s` to specify one.'
        return slack_ui_util.error_response(text)

    # Get DynamoDB service table for info
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': args.services[0]})

    # If service does not exist
    if 'Item' not in service:
        text = "Unable to build. Service `%s` does not exist in table " \
               "*[ServiceInfo]*." % args.services[0]
        return slack_ui_util.error_response(text)

    # Determine build method and URL from table
    build_method = service['Item']['serviceInfo']['build']['method'] \
        if 'method' in service['Item']['serviceInfo']['build'] else ''
    build_url = BUILD_METHODS[build_method] if build_method in BUILD_METHODS else ''
    if not build_url:
        text = "Service `%s` does not have a build method/URL associated with it..."\
               % args.services[0]
        return slack_ui_util.error_response(text)

    # Handle builds based on their methods
    if build_method == 'docker_build_V2':
        full_build_url = '{url}buildWithParameters?token={token}' \
                         '&BRANCH={branch}&SERVICE_NAME={service}' \
                         '&TAGS={user}&RESPONSE_URL={response_url}'\
            .format(url=build_url,
                    token=urllib2.quote(TOKEN),
                    branch=urllib2.quote(args.branch),
                    service=urllib2.quote(args.services[0]),
                    user=urllib2.quote(user),
                    response_url=response_url)
        LOGGER.info(full_build_url)
        urllib2.urlopen(full_build_url)
        text = "The build for `%s` has kicked off. Check ```%s``` to " \
               "monitor it..." % (args.services[0], build_url)
        return slack_ui_util.text_command_response(None, text)

    # Error text
    text = "The build for `%s` failed to kicked off. Check ```%s``` to see " \
           "why..." % (args.services[0], build_url)
    return slack_ui_util.error_response(text)
