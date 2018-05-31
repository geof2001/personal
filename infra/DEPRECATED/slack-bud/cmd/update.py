"""This module handles the update command of bud calls on Slack."""
import json
import re
import boto3
from botocore.exceptions import ClientError
import aws_util
import slack_ui_util


def update_confirm(body):
    """
    Entry point for confirmation buttons.

    :param body: - Data sent back via Slack
    """
    data = json.loads(body['payload'][0])

    if data['callback_id'] == 'select_update_env':
        return select_regions(data)
    if data['callback_id'] == 'select_update_region':
        return update(data)


def select_regions(data):
    """
    Select regions to update button menu.

    :param data: - Data sent back via Slack
    """

    # If cancel was pressed
    selected_env = data['actions'][0]['value']
    if selected_env == 'cancel':
        text = "Gotcha! The update was canceled!"
        return slack_ui_util.error_response(text)

    service_name, image = re.findall('\(([^)]+)', data['original_message']['text'])

    # Create boto3 DDB client
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': service_name})

    # If service does not exist in table
    if 'Item' not in service:
        error_text = 'The specified service does not exist in table `ServiceInfo`.'
        return slack_ui_util.error_response(error_text)

    # Prompt regions
    if selected_env == 'dev_and_qa':
        regions_dev = [region for region in service['Item']['serviceInfo']['regions']['dev']]
        regions_qa = [region for region in service['Item']['serviceInfo']['regions']['qa']]
        regions = set(regions_dev + regions_qa)
    else:
        regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
    text = "Select the region in `(%s)` of service `(%s)` in which you would like to " \
           "update the config data with `(%s)`." % (selected_env, service_name, image)
    fallback = 'Update'
    callback = 'select_update_region'
    return slack_ui_util.prompt_regions(text, fallback, callback, regions)


def handle_update(command):
    """
    Entry point when update command is called via Slack, or after a build.

    :param command: - Command use typed on Slack
    """
    # Help command for update
    if 'help' in command.strip():
        title = "Updates the specified service on the DeployConfig DDB Table."
        text = "*Format:* _/bud update <service>_\n\nExample: " \
               "_/bud update content_\n"
        return slack_ui_util.text_command_response(title, text, "#00b2ff")

    # Prompt Environments
    command_args = command.split()
    text = 'Select the config environment for service `(%s)` in which you would like to update with ' \
           '`(%s)`. If you do not want to update the config data, press cancel.' \
           % (command_args[0], command_args[1])
    fallback = 'Update'
    callback = 'select_update_env'
    return slack_ui_util.prompt_envs(text, fallback, callback)


def update(data):
    """
    Updates DeployConfig table with config data.

    :param data: - Data sent back via Slack
    """

    # If cancel was pressed
    selected_region = data['actions'][0]['value']
    if selected_region == 'cancel':
        text = "Gotcha! The update was canceled!"
        return slack_ui_util.error_response(text)

    selected_env, service_name, config = re.findall('\(([^)]+)', data['original_message']['text'])
    user = data['user']['name']

    # Get the part of config data with the required format
    config = config.split('|')[1][:-1]

    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('DeployConfig')
    service = services_table.get_item(Key={'serviceName': service_name})

    # If service does not exist in table
    if 'Item' not in service:
        error_text = 'The specified service does not exist in table `DeployConfig`.'
        return slack_ui_util.error_response(error_text)

    # Update config data
    try:
        if selected_env == 'dev_and_qa':
            services_table.update_item(
                Key={'serviceName': service_name},
                UpdateExpression="set config.#r.#d = :i, config.#r.#q = :i, #u = :t, #n = :n",
                ExpressionAttributeValues={':i': config, ':n': user, ':t': aws_util.get_prop_table_time_format()},
                ExpressionAttributeNames={'#k': 'serviceName',
                                          '#u': 'update',
                                          '#n': 'user',
                                          '#r': selected_region,
                                          '#d': 'dev',
                                          '#q': 'qa'},
                ConditionExpression='attribute_exists(#k)',
                ReturnValues="UPDATED_NEW"
            )
            text = 'Successfully updated `(%s)(%s)(%s)` in table `DeployConfig` with `(%s)`. ' \
                   'Would you like to deploy the update on Cloudformation for this service with ' \
                   'this environment and region?' \
                   % (service_name, selected_env, selected_region, config)
            fallback = 'Deploy'
            callback = 'update_to_deploy'
            return slack_ui_util.ask_for_confirmation_response(text, fallback, callback, danger_style=True)
        else:
            services_table.update_item(
                Key={'serviceName': service_name},
                UpdateExpression="set config.#r.#e = :i, #u = :t, #n = :n",
                ExpressionAttributeValues={':i': config, ':n': user, ':t': aws_util.get_prop_table_time_format()},
                ExpressionAttributeNames={'#k': 'serviceName',
                                          '#u': 'update',
                                          '#n': 'user',
                                          '#r': selected_region,
                                          '#e': selected_env},
                ConditionExpression='attribute_exists(#k)',
                ReturnValues="UPDATED_NEW"
            )
            text = 'Successfully updated `(%s)(%s)(%s)` in table `DeployConfig` with `(%s)`. ' \
                   'Would you like to deploy the update on Cloudformation for this service with ' \
                   'this environment and region?' \
                   % (service_name, selected_env, selected_region, config)
            fallback = 'Deploy'
            callback = 'update_to_deploy'
            return slack_ui_util.ask_for_confirmation_response(text, fallback, callback, danger_style=True)

    # Update exception
    except ClientError:
        error_text = 'Unable to update `[%s][%s][%s]` in table `DeployConfig` with `[%s]`.' \
                     'Make sure config envs and regions exist for the service.' \
                     % (service_name, selected_env, selected_region, config)
        return slack_ui_util.error_response(error_text)
