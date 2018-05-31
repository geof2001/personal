"""This module handles the deploy command of bud calls on Slack."""
from collections import OrderedDict
import re
import logging
import json
import urllib2
import boto3
import slack_ui_util
import aws_util
import bud_helper_util


ENVIRONMENTS = bud_helper_util.ENVIRONMENTS
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
TOKEN = 'REGRESSIONISGOOD'
HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
DEPLOY_METHODS = {
    'CF_deploy_V1': 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-service-stack-v2/'
}

# Accounts Map
ACCOUNTS = {"dev": "638782101961",
            "qa": "181133766305",
            "stg": "610352865374",
            "prod": "886239521314",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-stg": "stg",
            "admin-prod": "prod"}


def deploy_confirm(body):
    """
    Entry point for confirmation buttons.

    :param body: - Data sent back via Slack
    """
    data = json.loads(body['payload'][0])

    if data['callback_id'] == 'select_deploy_images':
        return select_images(data)
    if data['callback_id'] == 'select_deploy_images_with_flags':
        return select_images(data, flags=True)
    if data['callback_id'] == 'select_deploy_env':
        return select_regions(data)
    if data['callback_id'] == 'select_deploy_region':
        return select_changeset(data)
    if data['callback_id'] == 'select_deploy_changeset':
        return deploy(data)


def select_changeset(data):
    """
    Select whether to deploy as a changeset.

    :param data: - Data sent back via Slack
    """

    # If cancel was pressed
    selected_region = data['actions'][0]['value']
    if selected_region == 'cancel':
        text = "Gotcha! The deploy was canceled!"
        return slack_ui_util.error_response(text)

    selected_env, service_name, image = re.findall('\(([^)]+)', data['original_message']['text'])

    # Prompt changeset confirmation
    text = 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` as a changeset?' \
           % (service_name, image, selected_env, selected_region)
    fallback = 'Deploy'
    callback= 'select_deploy_changeset'
    return slack_ui_util.prompt_changeset(text, fallback, callback)


def select_regions(data):
    """
    Select regions to deploy button menu.

    :param data: - Data sent back via Slack
    """

    # If cancel was pressed
    selected_env = data['actions'][0]['value']
    if selected_env == 'cancel':
        text = "Gotcha! The deploy was canceled!"
        return slack_ui_util.error_response(text)

    image, service_name = re.findall('\(([^)]+)', data['original_message']['text'])

    # Create DDB boto3 resource
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': service_name})

    # If specified service not in table
    if 'Item' not in service:
        error_text = 'The specified service does not exist in table `ServiceInfo`.'
        return slack_ui_util.error_response(error_text)

    # Prompt regions buttons
    regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
    text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
           "be deployed to." % (selected_env, service_name, image)
    fallback = 'Deploy'
    callback = 'select_deploy_region'
    return slack_ui_util.prompt_regions(text, fallback, callback, regions)


def select_images(data, flags=False):
    """
    Select regions to deploy button menu.

    :param data: - Data sent back via Slack
    :param flags: - If -r and -e flags are set
    """

    # If cancel was pressed
    selected_image = data['actions'][0]['value']
    if selected_image == 'cancel':
        text = "Gotcha! The deploy was canceled!"
        return slack_ui_util.error_response(text)

    if not flags:
        service_name = re.findall('\(([^)]+)', data['original_message']['text'])[0]

        # Prompt environments
        text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
               '`(%s)`. If you do not want to deploy, press cancel.' % (selected_image, service_name)
        fallback = 'Deploy'
        callback = 'select_deploy_env'
        return slack_ui_util.prompt_envs(text, fallback, callback, all_envs=True)

    # Prompt changeset
    service_name, selected_env, selected_region = \
        re.findall('\(([^)]+)', data['original_message']['text'])

    text = 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` as a changeset?' \
           % (service_name, selected_image, selected_env, selected_region)
    fallback = 'Deploy'
    callback = 'select_deploy_changeset'
    return slack_ui_util.prompt_changeset(text, fallback, callback)


def get_parameter_index(service, lst_of_map):
    """
    Entry point when deploy status is called

    :param service: - Service name
    :param lst_of_map: - List of the parameters map
    """
    for index, dic in enumerate(lst_of_map):
        LOGGER.info('for loop index %s dic %s value %s' % (index, dic, dic['ParameterKey']))
        if dic['ParameterKey'] == '%sImage' % service.capitalize():
            return index
    return -1


def status(service, stack_name, region_map):
    """
    Entry point when deploy status is called

    :param service: - ServiceInfo table
    :param stack_name: - Name of the stack
    :param region_map: - map of regions of service
    """
    output = ''

    # Order map to enhance env readability
    order = ['dev', 'qa', 'stg', 'prod']
    ordered_map = OrderedDict()
    for env in order:
        if env in region_map:
            ordered_map[env] = region_map[env]

    # Loop through map
    for env in ordered_map:
        output += '*[%s]*\n' % env
        for region in ordered_map[env]:
            session = aws_util.get_session(ENVIRONMENTS, env)
            try:
                cf = aws_util.get_cloudformation_client(session, region)
                stack_description = cf.describe_stacks(StackName=stack_name)
                index = get_parameter_index(service, stack_description['Stacks'][0]['Parameters'])
                LOGGER.info('index : %s ' % index)
                full_version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
                current_version = full_version.split(':')[1]
                output += '\t\t_%s_ : `%s`\n' % (region, current_version)
            except:
                error_text = "The service *[%s]* may not have a CF stack with the version as a " \
                             "parameter, or does not exist in *[serviceInfo]*..." % service
                return slack_ui_util.error_response(error_text)
    return output


def handle_deploy(command, args, response_url, full_text):
    """
    Entry point when deploy command is called via Slack.

    :param command: - Command user typed on Slack
    :param args: - Argument flags
    :param response_url: - Response URL for slack
    """
    # Help command for deploy
    if 'help' in command.strip():
        title = "Deploys the specified service onto Cloudformation with a build version."
        text = "*Formats:* _/bud deploy -s <service>_\n          " \
               "_/bud deploy -s <service> -v <version>_" \
               "\n\nExamples: _/bud deploy -s content_\n         " \
               "_/bud deploy -s content -v master-631bd11-20180122-70_"
        return slack_ui_util.text_command_response(title, text, "#00b2ff")

    # Prompt Environments
    if not args.services:
        text = 'Unable to deploy. A service was not specified. Use the flag ' \
               '`-s` to specify one.'
        return slack_ui_util.error_response(text)

    # Create DDB boto3 resource
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': args.services[0]})

    # If specified service not in table
    if 'Item' not in service:
        error_text = 'The specified service does not exist in table `ServiceInfo`.'
        return slack_ui_util.error_response(error_text)

    # Handle Status
    if 'status' in command.strip():
        slack_ui_util.loading_msg(response_url)
        region_map = service['Item']['serviceInfo']['regions']
        stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
        return slack_ui_util.text_command_response(
            title='Here are the current image versions deployed for service `%s`...' % args.services[0],
            text=status(args.services[0], stack_name, region_map),
            color="#d77aff",
            post=True,
            response_url=response_url
        )

    # If no version flag value was provided, look up previous builds from ES
    es_client = aws_util.setup_es()

    # If version flag value is provided
    if args.version:
        search = es_client.search(index='build*',
                                  q='dockertag.keyword:\"%s\"' % args.version,
                                  _source_include=['buildtime', 'dockertag', 'gitrepo', 'service'],
                                  sort=['buildtime:desc'],
                                  size=1)
        if not search['hits']['hits']:
            text = 'The specified version `%s` does not exist in Elastic Search.' \
                   % args.version
            return slack_ui_util.error_response(text)

        if search['hits']['hits'][0]['_source']['service'] != args.services[0]:
            text = 'The specified version `%s` does not have a relationship with service `%s`.' \
                   % (args.version, args.services[0])
            return slack_ui_util.error_response(text)

        image = args.version

        # If -r and -e and -v specified
        if '-r' in full_text.split() and '-e' in full_text.split():
            text = 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` as a changeset?' \
                   % (args.services[0], image, args.envs[0], args.regions[0])
            fallback = 'Deploy'
            callback = 'select_deploy_changeset'
            return slack_ui_util.prompt_changeset(text, fallback, callback)

        text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
               '`(%s)`. If you do not want to deploy, press cancel.' % (image, args.services[0])
        fallback = 'Deploy'
        callback = 'select_deploy_env'
        return slack_ui_util.prompt_envs(text, fallback, callback, all_envs=True)

    # ES query
    query = {
        "query": {
            "query_string": {
                "query": "service.keyword:\"%s\" AND coverage.unittestcases.failed:0"
                         % args.services[0]
            }
        }
    }
    search = es_client.search(index='build*',
                              body=query,
                              _source_include=['buildtime', 'dockertag', 'gitrepo'],
                              sort=['buildtime:desc'],
                              size=4)

    if '-r' in full_text.split() and '-e' in full_text.split():
        text = 'Here are the last couple builds for service `(%s)`. ' \
               'Select the one you would like to deploy to `(%s)` `(%s)`. ' \
               'Otherwise press cancel.' % (args.services[0], args.envs[0], args.regions[0])
        fallback = 'Deploy'
        callback = 'select_deploy_images_with_flags'
        return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback, callback)

    text = 'Here are the last couple builds for service `(%s)`. ' \
           'Select the one you would like to deploy. Otherwise press cancel.' \
           % args.services[0]
    fallback = 'Deploy'
    callback = 'select_deploy_images'
    return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback, callback)


def deploy(data):
    """
    Deploys specified service with current config data in DeployConfig.

    :param data: - Data sent back via Slack
    """

    # If cancel was pressed
    selected_changeset = data['actions'][0]['value']
    if selected_changeset == 'cancel':
        text = "Gotcha! The deploy was canceled!"
        return slack_ui_util.error_response(text)

    # Gather info from data
    user = data['user']['name']
    response_url = data['response_url']
    service_name, image, selected_env, selected_region = \
        re.findall('\(([^)]+)', data['original_message']['text'])

    # Run deploy job
    return deploy_helper(service_name, image, selected_env,
                         selected_region, selected_changeset, user, response_url)


def deploy_helper(service_name, image, selected_env, selected_region, selected_changeset, user, response_url):
    """
    Calls the deploy Jenkins job.

    :param service_name: - Name of service
    :param image: - Image version
    :param selected_env: - Selected environment
    :param selected_region: - Selected region
    :param selected_changeset: - Selected changeset option
    :param user: - User that deployed
    :param response_url: - Response URL to slack
    """

    # Settings based on special environments
    if selected_env == 'prod':
        prod_status = True
    else:
        prod_status = False

    # Get DynamoDB service table for info
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': service_name})

    # If service does not exist
    if 'Item' not in service:
        text = "Unable to build. Service `%s` does not exist in table " \
               "*[ServiceInfo]*." % service_name
        return slack_ui_util.error_response(text)

    # Determine deploy method and URL from table
    deploy_method = service['Item']['serviceInfo']['deploy']['method'] \
        if 'method' in service['Item']['serviceInfo']['deploy'] else ''
    deploy_url = DEPLOY_METHODS[deploy_method] if deploy_method in DEPLOY_METHODS else ''
    if not deploy_url:
        text = "Service `%s` does not have a deploy method/URL associated with it..." \
               % service_name
        return slack_ui_util.error_response(text)

    # Handle deploys based on their methods
    if deploy_method == 'CF_deploy_V1':
        full_deploy_url = '{url}buildWithParameters?token={token}&SERVICE_NAME={service}' \
                          '&CreateChangeSet={changeset}&{accounts}&{regions}{ProdPush}' \
                          '{user}{response_url}{image}'\
            .format(url=deploy_url,
                    token=urllib2.quote(TOKEN),
                    service=urllib2.quote(service_name),
                    changeset=selected_changeset,
                    accounts='AWS_ACCOUNTS=' + ACCOUNTS[selected_env],
                    regions='&AWS_REGIONS=' + selected_region,
                    ProdPush='&ProdPush=true' if prod_status else '',
                    user='&TAGS=' + user,
                    response_url='&RESPONSE_URL=' + response_url,
                    image='&IMAGE_VERSION=638782101961.dkr.ecr.us-east-1.amazonaws.com/'
                          + service_name + ':' + image)
        urllib2.urlopen(full_deploy_url)
        text = "The deploy job for `%s` has kicked off. Check ```%s``` to " \
               "monitor it..." % (service_name, deploy_url)
        return slack_ui_util.text_command_response(None, text)

    # Error text
    text = "The deploy job for `%s` failed to kicked off. Check ```%s``` to see " \
           "why..." % (service_name, deploy_url)
    return slack_ui_util.error_response(text)
