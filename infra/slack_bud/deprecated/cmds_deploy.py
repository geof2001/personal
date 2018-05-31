"""Implements Deploy command by asnyder@roku.com"""
from __future__ import print_function

import argparse
import re
import logging
import json
import urllib2
import time
from datetime import datetime
import boto3
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

ENVIRONMENTS = aws_util.ENVIRONMENTS
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
TOKEN = 'REGRESSIONISGOOD'
HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
DEPLOY_METHODS = {
    'CF_deploy_V1': 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-service-stack-v2/'
}
DATADOG_HEALTH_URL = 'https://app.datadoghq.com/dash/669562/' \
                     'sr-service-health?live=true&page=0&is_auto=false&tile_size=m'
# Accounts Map
ACCOUNTS = {"dev": "638782101961",
            "qa": "181133766305",
            "prod": "886239521314",
            "admin-dev": "dev",
            "admin-qa": "qa",
            "admin-prod": "prod"}


class CmdDeploy(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Deploys the specified service onto Cloudformation with a build version."

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Formats:* _/bud deploy -s <service>_\n                 " \
               "_/bud deploy -s <service> -v <version>_\n" \
               "_(Optional Flags) - /bud deploy -s <service> -v <version> " \
               "-e <environment> -r <region>_" \
               "\n\nExamples: _/bud deploy -s content_\n                  " \
               "_/bud deploy -s content -v master-631bd11-20180122-70_\n                  " \
               "_/bud deploy -s content -v master-631bd11-20180122-70 -e dev -r us-east-1_" \
               "\n\n*To rollback to the previously deployed version, " \
               "use the --rollback flag:*\n_/bud deploy -s <service> " \
               "-e <dev> -r <region> --rollback_\n\nExample: _/bud deploy -s content -e prod" \
               " -r us-east-1 --rollback_\n\n_NOTE: When using the --rollback flag, " \
               "an environment -e and region -r must be provided._\n\n\n*To check current " \
               "deployment version status:*\n _/bud deploy status" \
               " -s <service>_\n\nExample: _/bud deploy status -s content_\n\n\n"
        help_text += "*To check history of a service, use the* `<history>` *subcommand:*\n\n"
        help_text += "*<Flags>*\n"
        help_text += "`-s` - Service to show deploys for. (Required)\n"
        help_text += "`-n` - Number of deploys to show. (Default: 10)\n"
        help_text += "`-e` - Environment filter of deploys.\n"
        help_text += "`-r` - Region filter of deploys.\n"
        help_text += "`-c` - Changeset flag, takes in string *true* or *false*. (Default: Shows both)\n\n"
        help_text += "Example: _/bud deploy history -s content -n 5 -e dev -r us-east-1 -c false_\n"
        help_text += "Example: _/bud deploy history -s homescreen -r us-east-1 -c true_\n\n\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, command_text, response_url, raw_inputs):
        """
        Return help text for your command in slack format here.
        """
        # Argument Parser Configuration
        parser = argparse.ArgumentParser(description='Parses show command input')
        parser.add_argument(
            'command', metavar='', default=None, nargs='*',
            help='The command before the flags')
        parser.add_argument(
            '--services', '--service', '-s',
            metavar='', default=None, nargs='*',
            help='qa, dev, prod')
        parser.add_argument(
            '--envs', '--env', '-e',
            metavar='', default=None, nargs='*',
            help='qa, dev, prod')
        parser.add_argument(
            '--regions', '--region', '-r',
            metavar='', nargs='*',
            help='AWS Region(s)')
        parser.add_argument(
            '--num', '-n',
            default=10, type=int,
            help='Number of info to show')
        parser.add_argument(
            '--changeset', '-c',
            default=None,
            help='If true, display changeset')
        parser.add_argument(
            '--version', '-version', '-v',
            default=None,
            help='Version of service image to deploy')
        parser.add_argument(
            '--rollback', '-rollback',
            default=False, action='store_true',
            help='If true, rolls back stack to previous version')

        args, unknown = parser.parse_known_args(command_text.split())
        print('ARGS: %s' % args)
        try:
            if sub_command == 'help':
                return self.get_help_text()

            fallback_value = self.set_fallback_value()
            print('Set fallback_value ={}'.format(fallback_value))

            # Prompt Environments
            if not args.services:
                text = 'A service was not specified. Use the flag ' \
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

            region_map = service['Item']['serviceInfo']['regions']
            stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
            cf_image = service['Item']['serviceInfo']['deploy']['image_name']

            # Handle Status
            if sub_command.strip() == 'status':
                payload = {
                    'task': 'deploy_status',
                    'service': args.services[0],
                    'stack_name': stack_name,
                    'cf_image': cf_image,
                    'region_map': region_map,
                    'response_url': response_url
                }
                lambda_function = boto3.client('lambda')
                response = lambda_function.invoke(
                    FunctionName="slackbud-longtasks",
                    InvocationType="Event",
                    Payload=json.dumps(payload)
                )
                print(response)
                return slack_ui_util.text_command_response('_Processing..._', '')

            # Handle History
            if sub_command.strip() == 'history':
                return handle_deploy_history(args)

            # Make sure when --rollback is called, -e and -r is also provided
            if args.rollback and (not args.envs or not args.regions):
                text = 'Please provide an environment `-e` ' \
                       'and region `-r` to rollback for service `%s`' % args.services[0]
                return slack_ui_util.error_response(text)

            # If no version flag value was provided, look up previous builds from ES
            es_client = aws_util.setup_es()

            # Exception for services tfs-legacy and tfs-legacy-canary
            tfs_other_flag = False
            tfs_service_holder = ''
            if args.services[0] == 'tfs-legacy' or args.services[0] == 'tfs-legacy-canary':
                tfs_other_flag = True
                tfs_service_holder = args.services[0]
                args.services[0] = 'tfs'

            # If version flag value is provided
            if args.version:
                if args.rollback:
                    text = 'The `-v` and `--rollback` flags can not be used at the same time.'
                    return slack_ui_util.error_response(text)

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

                # Change back to original tfs service if true if -v specified
                if tfs_other_flag:
                    args.services[0] = tfs_service_holder

                # Cases of when -e and/or -r flags are specified
                if '-r' in raw_inputs.split() and '-e' in raw_inputs.split():
                    test_status = get_test_status_on_build(image, args.envs[0]) + '\n'
                    text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                                         % (args.services[0], image, args.envs[0], args.regions[0])
                    # fallback = 'Deploy'
                    callback = 'select_deploy_changeset'
                    return slack_ui_util.prompt_changeset(text, fallback_value, callback)

                elif '-e' in raw_inputs.split():
                    # Prompt regions buttons
                    regions = [region for region in service['Item']['serviceInfo']['regions'][args.envs[0]]]
                    text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
                           "be deployed to." % (args.envs[0], args.services[0], image)
                    # fallback = 'Deploy'
                    callback = 'select_deploy_region'
                    return slack_ui_util.prompt_regions(text, fallback_value, callback, regions)

                text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
                       '`(%s)`. If you do not want to deploy, press cancel.' % (image, args.services[0])
                # fallback = 'Deploy'
                callback = 'select_deploy_env'
                return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)

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
                                      size=3)

            # Change back to original tfs service if true if -v not specified
            if tfs_other_flag:
                args.services[0] = tfs_service_holder

            # If flags -r/-e
            if '-r' in raw_inputs.split() and '-e' in raw_inputs.split():
                if args.rollback:

                    # ES query for deploy history
                    rollback_query = {
                        "query": {
                            "query_string": {
                                "query": "service.keyword:\"%s\" AND environment:\"%s\" AND region:\"%s\""
                                         % (args.services[0], ENVIRONMENTS[args.envs[0]], args.regions[0])
                            }
                        }
                    }
                    rollback_search = es_client.search(index='deploy*',
                                                       body=rollback_query,
                                                       sort=['deploy_time:desc'],
                                                       size=4)

                    # Loop through images and find first one thats not equal to currently deployed one
                    current_image = rollback_search['hits']['hits'][0]['_source']['image_name'].split(':')[1]
                    rollback_image = ''
                    for full_image in rollback_search['hits']['hits'][1:]:
                        this_image = full_image['_source']['image_name'].split(':')[1]
                        if this_image != current_image:
                            rollback_image = this_image
                            break

                    text = 'The current deployed version is `%s` for this ' \
                           'environment and region. Would you like to ' \
                           'rollback to the previous deployed version of `(%s)` `(%s)` `(%s)` `(%s)`? ' \
                           % (current_image, args.services[0], rollback_image, args.envs[0], args.regions[0])
                    callback = 'select_deploy_changeset'
                    return slack_ui_util.prompt_changeset(text, fallback_value, callback, rollback=True)

                text = 'Here are the last couple builds for service `(%s)`. ' \
                       'Select the one you would like to deploy to `(%s)` `(%s)`. ' \
                       'Otherwise press cancel.' % (args.services[0], args.envs[0], args.regions[0])
                # fallback = 'Deploy'
                callback = 'select_deploy_images_with_all'
                return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

            elif '-e' in raw_inputs.split():
                text = 'Here are the last couple builds for service `(%s)`. ' \
                       'Select the one you would like to deploy to `(%s)`. ' \
                       'Otherwise press cancel.' % (args.services[0], args.envs[0])
                # fallback = 'Deploy'
                callback = 'select_deploy_images_with_env'
                return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

            text = 'Here are the last couple builds for service `(%s)`. ' \
                   'Select the one you would like to deploy. Otherwise press cancel.' \
                   % args.services[0]
            # fallback = 'Deploy'
            callback = 'select_deploy_images'
            return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def invoke_confirm_command(self, params):
        """
        Return help text for your command in slack format here.

        :param body: - Data sent back via Slack
        """
        try:
            data = json.loads(params['payload'][0])

            callback_id = data['callback_id']
            print('CmdDeploy invoke_confirm_command. callback_id: {}'.format(callback_id))

            if callback_id == 'select_deploy_images':
                return select_images(data)
            if callback_id == 'select_deploy_images_with_env':
                return select_images(data, env=True)
            if callback_id == 'select_deploy_images_with_all':
                return select_images(data, all_flags=True)
            if callback_id == 'select_deploy_env':
                return select_regions(data)
            if callback_id == 'select_deploy_region':
                return select_changeset(data)
            if callback_id == 'select_deploy_changeset':
                return deploy(data)
            print('Failed to find callback_id: {}'.format(callback_id))

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def is_confirm_command(self, params):
        """
        Return help text for your command in slack format here.
        """
        try:
            fallback_str = self.get_fallback_string_from_payload(params)
            if fallback_str is None:
                return False
            elif fallback_str == self.__class__.__name__:
                return True
            return False

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return False

    def invoke_longtask_command(self, event):
        """
        Put longtask command stuff here.
        :param event:
        :return:
        """
        # Temp just to not break build.
        return None

    def set_fallback_value(self):
        return self.__class__.__name__


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

    # If unchanged version was selected, get current image on CF
    if 'Unchanged/Current Image' in image:
        image = get_current_image(service_name, selected_env, selected_region)

    test_status = get_test_status_on_build(image, selected_env) + '\n'

    # Prompt changeset confirmation
    text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                         % (service_name, image, selected_env, selected_region)
    # fallback_value = self.set_fallback_value()
    # ToDo: move this into the call.
    fallback_value = CmdDeploy().set_fallback_value()
    # fallback = 'Deploy'
    callback = 'select_deploy_changeset'
    return slack_ui_util.prompt_changeset(text, fallback_value, callback)


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

    missing_regions = []
    # Prompt regions buttons
    if selected_env == 'dev/qa':
        regions_dev = [region for region in service['Item']['serviceInfo']['regions']['dev']]
        regions_qa = [region for region in service['Item']['serviceInfo']['regions']['qa']]
        regions = [region for region in regions_dev if region in frozenset(regions_qa)]
        missing_regions = [region for region in regions_dev if region not in frozenset(regions_qa)]
    else:
        regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
    text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
           "be deployed to." % (selected_env, service_name, image)
    # fallback = 'Deploy'
    # ToDo: Make this a member of the class.
    fallback_value = CmdDeploy().set_fallback_value()
    callback = 'select_deploy_region'

    if 'Unchanged/Current Image' in image:
        return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, all_regions=False)

    return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, missing_regions=missing_regions)


def select_images(data, env=False, all_flags=False):
    """
    Select regions to deploy button menu.

    :param data: - Data sent back via Slack
    :param env: - If -e flag is set only
    :param all_flags: - If -r and -e flags are set
    """

    # If cancel was pressed
    selected_image = data['actions'][0]['value']
    if selected_image == 'cancel':
        text = "Gotcha! The deploy was canceled!"
        return slack_ui_util.error_response(text)

    if all_flags and not env:

        # Prompt changeset
        service_name, selected_env, selected_region = \
            re.findall('\(([^)]+)', data['original_message']['text'])

        # If unchanged version was selected, get current image on CF
        if 'Unchanged/Current Image' in selected_image:
            selected_image = get_current_image(service_name, selected_env, selected_region)

        test_status = get_test_status_on_build(selected_image, selected_env) + '\n'

        text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                             % (service_name, selected_image, selected_env, selected_region)
        # fallback = 'Deploy'
        # ToDo: Make this a member of the class.
        fallback_value = CmdDeploy().set_fallback_value()
        callback = 'select_deploy_changeset'
        return slack_ui_util.prompt_changeset(text, fallback_value, callback)

    elif not all_flags and env:

        service_name, selected_env = re.findall('\(([^)]+)', data['original_message']['text'])

        # Create DDB boto3 resource
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': service_name})

        # Prompt regions buttons
        regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
        text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
               "be deployed to." % (selected_env, service_name, selected_image)
        # fallback = 'Deploy'
        fallback_value = CmdDeploy().set_fallback_value()
        callback = 'select_deploy_region'

        if 'Unchanged/Current Image' in selected_image:
            return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, all_regions=False)

        return slack_ui_util.prompt_regions(text, fallback_value, callback, regions)

    else:
        service_name = re.findall('\(([^)]+)', data['original_message']['text'])[0]

        # Create DDB boto3 resource
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': service_name})

        # Prompt environments
        text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
               '`(%s)`. If you do not want to deploy, press cancel.' % (selected_image, service_name)
        # fallback = 'Deploy'
        fallback_value = CmdDeploy().set_fallback_value()
        callback = 'select_deploy_env'
        region_map = service['Item']['serviceInfo']['regions']

        if 'Unchanged/Current Image' in selected_image:
            return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map, dev_and_qa=False)

        return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)


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

    # Put given regions and envs into a list
    regions = selected_region.split('/')
    envs = selected_env.split('/')

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
        for env in envs:
            for region in regions:
                if env == 'qa' and region == 'us-west-2':
                    continue
                full_deploy_url = '{url}buildWithParameters?token={token}&SERVICE_NAME={service}' \
                                  '&CreateChangeSet={changeset}&{accounts}&{regions}{ProdPush}' \
                                  '{user}{response_url}{image}'\
                    .format(url=deploy_url,
                            token=urllib2.quote(TOKEN),
                            service=urllib2.quote(service_name),
                            changeset=selected_changeset,
                            accounts='AWS_ACCOUNTS=' + ACCOUNTS[env],
                            regions='&AWS_REGIONS=' + region,
                            ProdPush='&ProdPush=true' if prod_status else '',
                            user='&TAGS=' + user,
                            response_url='&RESPONSE_URL=' + response_url,
                            image='&IMAGE_VERSION=' + service_name + ':' + image)
                urllib2.urlopen(full_deploy_url)
        to_ts = int(time.time()) * 1000
        from_ts = to_ts - 3600000
        text = "The deploy job(s) for `%s` have kicked off. ```%s``` " % (service_name, deploy_url)
        for env in envs:
            datadog_url = DATADOG_HEALTH_URL + \
                          '&from_ts=%s&to_ts=%s&tpl_var_servicename=%s&tpl_var_account=sr_%s' \
                          % (str(from_ts), str(to_ts), service_name, env)
            text += "Monitor the service health via DataDog for `%s` here. ```%s``` " % (env, datadog_url)
        return slack_ui_util.text_command_response(None, text)

    # Error text
    text = "The deploy job for `%s` failed to kicked off. Check ```%s``` to see " \
           "why..." % (service_name, deploy_url)
    return slack_ui_util.error_response(text)


def handle_deploy_history(args):
    """
    Shows the most recent deploys of specified service.
    :param args: Flags inputted by user.
    :return:
    """

    # Setup ES client
    es_client = aws_util.setup_es()

    env = " AND environment:\"%s\"" % ENVIRONMENTS[args.envs[0]] if args.envs else ''
    region = " AND region:\"%s\"" % args.regions[0] if args.regions else ''

    changeset = ''
    if args.changeset and args.changeset.strip().lower() == 'true':
        changeset = " AND changeset:\"true\""
    elif args.changeset and args.changeset.strip().lower() == 'false':
        changeset = " AND changeset:\"false\""

    # ES query
    query = {
        "query": {
            "query_string": {
                "query": "service.keyword:\"%s\"" % args.services[0] + env + region + changeset
            }
        }
    }
    search = es_client.search(
        index='deploy*',
        body=query,
        sort=['deploy_time:desc'],
        size=args.num
    )

    search_list = search['hits']['hits']
    output = ''

    for deploy in search_list:
        try:
            date = datetime.strptime(deploy['_source']['deploy_time'], '%Y-%m-%dT%H:%M:%S')
            date = date.strftime('%b %d, %Y - %I:%M:%S %p')
            image_name = deploy['_source']['image_name'].split(':')[1]
            job_number = deploy['_source']['deploy_job_number']
            environment = deploy['_source']['environment']
            output += '```Deploy #%s   (%s)```\n' % (job_number, date)
            output += '`Image`  -  _%s_\n' % image_name
            output += '`Environment`  -  _%s_\n' % ENVIRONMENTS.keys()[ENVIRONMENTS.values().index(environment)]
            output += '`Region`  -  _%s_\n' % deploy['_source']['region']
            output += '`Change Set`  -  _%s_\n' % deploy['_source']['changeset']
            output += '`CF Status`  -  _%s_\n' % str(deploy['_source']['cf_status']) \
                if 'cf_status' in deploy['_source'] else '`CF Status`  -  _?_\n'
            output += '`Deploy User`  -  _%s_\n' % deploy['_source']['userID']
        except ShowSlackError:
            text = '%s deploys do not exist with the specified filters. Lower the number.' % args.num
            return slack_ui_util.error_response(text)

    if search_list:
        title = 'Here are `%s` of the most recent deploy(s) for service `%s`' % (args.num, args.services[0])
    else:
        title = 'No deploys can be found for service `%s` with specified input.' % args.services[0]
    text = output
    color = "#d77aff"
    return slack_ui_util.text_command_response(title=title, text=text, color=color)


def get_current_image(service_name, env, region):
    """
    Find the current image currently deployed for service based on env/region

    :param service_name: - The name of the service
    :param env: - The environment
    :param region: - The region
    """
    # Create DDB boto3 resource
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    service = services_table.get_item(Key={'serviceName': service_name})

    session = aws_util.create_session(env)
    cf = aws_util.get_cloudformation_client(session, region)
    stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
    image_key = service['Item']['serviceInfo']['deploy']['image_name']
    stack_description = cf.describe_stacks(StackName=stack_name)

    version = 'None'

    # Return if no params to prevent error
    if 'Parameters' not in stack_description['Stacks'][0]:
        return version

    params_map = stack_description['Stacks'][0]['Parameters']

    # Find current version deployed
    for index, param in enumerate(params_map):
        if param['ParameterKey'] == image_key:
            version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
            break

    if ':' in version:
        version = version.split(':')[1]

    return version


def _get_test_status_by_environment(env, image):
    """
    :param env: name of the environment qa,dev,prod
    :param image: name of the image
    :return: test_status(str): Test status string that gives test information about that image
    """
    # Setup ES client
    es_client = aws_util.setup_es()

    # Query for build tag search
    build_test_status_query = "dockertag:\"{}\" AND testenv:\"{}\"".format(image, env)

    # ES query
    query = {
        "query": {
            "query_string": {
                "query": str(build_test_status_query)
            }
        }
    }
    print("QUERY: {}".format(query))
    search_result = es_client.search(
        index="test*",
        doc_type="json",
        body=query,
        sort=['testtime:desc'],
        size=10
    )
    print("Total :{}".format(search_result.get('hits').get('total')))
    content_list = search_result.get('hits').get('hits')
    if len(content_list) == 0:
        test_status = "No test results were found for build `{}`  in the `{}` environment.".format(image, env)
        return test_status
    else:
        passed_tc = ""
        failed_tc = ""
        test_time = ""
        result_container = []
        for result in content_list:
            result_container.append((result.get('_source')))
            latest_result = result_container[0]
            passed_tc = latest_result.get('testpassed')
            failed_tc = latest_result.get('testfailed')
            test_time = latest_result.get('testtime')
            if (passed_tc is None) or (failed_tc is None):
                passed_tc = latest_result.get('smoketestpassed')
                failed_tc = latest_result.get('smoketestfailed')
    percentage_pass = (float(passed_tc) / float(passed_tc + failed_tc)) * 100
    percentage = "%0.2f" % percentage_pass + "%"
    test_status = "Last run on build `{}` in `{}` @ `{}` Testresult:`{}`/`{}` - `{}` testcases passed".format(image,env, test_time, passed_tc,
                                                                          passed_tc + failed_tc, percentage)
    return test_status


def get_test_status_on_build(image, env):
    """
    :param image:
    :param env:
    :return:
    """
    test_status = ""
    for env in ["dev", "qa", "prod"]:
        test_status += _get_test_status_by_environment(env, image) + ". \n"
    return test_status
