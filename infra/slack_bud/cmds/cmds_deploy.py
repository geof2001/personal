"""Implements Deploy command by asnyder"""
from __future__ import print_function
from collections import OrderedDict
import re
import json

import logging
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
    'CF_deploy_V1': 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-service-stack-v2/',
    'serverless_lambda': 'https://cidsr.eng.roku.com/job/deploy-serverless-lambda/'
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

# Services that have qa env in us-west-2
QA_US_WEST_2_SERVICES = ['logging']

# Images to not split @ ":" , mostly recsys EMR microservices
NON_SPLIT_IMAGE_SERVICES = [
    'recsys-cf-item-to-item',
    'recsys-cb-itemtoitem',
    'recsys-log-parser',
    'recsys-matrix-factorization',
    'recsys-redis-mass-inserter',
    'recsys-wikipedia-extractor-emr',
    'recsys-wikipedia-recon'
]

DIFFERENT_NAME_IMAGE_SERVICES = {
    'recsys-wikipedia-extractor-batch': 'recsys-wikipedia-extractor',
    'recsys-wikipedia-extractor': 'recsys-wikipedia-extractor-batch',
    'recsys-api': 'recsys',
    'recsys': 'recsys-api'
}

class CmdDeploy(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['_default_', 'history', 'status'],
            'help_title': 'Deploys the specified service onto Cloudformation with a build version.',
            'formats': [
                '/bud deploy -s <service>',
                '/bud deploy -s <service> -v <version>',
            ],
            'optional_flags': '-v -e -r',
            'permission_level': 'dev',
            'props__default_': self.get_default_properties(),
            'props_history': self.get_history_properties(),
            'props_status': self.get_status_properties()
# {#sub_command_prop_methods#}
        }

        return props

    def get_default_properties(self):
        """
        The properties for the "default" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<>` Deploy docker services',
            'help_examples': [
                '/bud deploy -s content',
                '/bud deploy -s content -v master-631bd11-20180122-70',
                '/bud deploy -s content -v master-631bd11-20180122-70 -e dev -r us-east-1',
                '   `--rollback`, flag used to rollback to previously deployed version',
                '/bud deploy -s <service> -e <dev> -r <region> --rollback',
                '*NOTE:* When using the `--rollback` flag `-e` and `-r` must be provided'
            ],
            'switch-templates': ['env-optional', 'service', 'region-optional'],
            'switch-v': {
                'aliases': ['v', 'version'],
                'type': 'string',
                'required': False,
                'lower_case': True,
                'help_text': 'Version to deploy'
            },
            'switch-rollback': {
                'aliases': ['rollback'],
                'type': 'property',
                'required': False,
                'lower_case': True,
                'help_text': '--rollback, if you need to rollback'
            }
        }
        return props

    def invoke__default_(self, cmd_inputs):
        """
        Placeholder for "_default_" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke__default_")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            arg_version = cmd_inputs.get_by_key('version')
            arg_changeset = cmd_inputs.get_by_key('changeset')
            arg_rollback = cmd_inputs.get_by_key('rollback')
            response_url = cmd_inputs.get_response_url()

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            region_map = cmd_specific_data.get('region_map')

            #fallback_value = cmd_inputs.get_callback_value()  # callback and fallback are same thing.
            fallback_value = self.set_fallback_value()
            raw_inputs = cmd_inputs.get_raw_inputs()

            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': arg_service})

            if 'Item' not in service:
                text = 'The service `%s` does not exist in the database.' % arg_service
                return slack_ui_util.error_response(text)

            # Start Default code section #### output to "text" & "title".
            text='Verify inputs first:\n'
            if arg_service:
                text += 'arg_service={}\n'.format(arg_service)
            if arg_region:
                text += 'arg_region={}\n'.format(arg_region)
            if arg_env:
                text += 'arg_env={}\n'.format(arg_env)
            if arg_version:
                text += 'arg_version={}\n'.format(arg_version)
            if arg_changeset:
                text += 'arg_changeset={}\n'.format(arg_changeset)
            if arg_rollback:
                text += 'arg_rollback={}\n'.format(arg_rollback)
            if raw_inputs:
                text += 'raw_inputs={}\n'.format(raw_inputs)
            print('invoke__default_ cmd_inputs={}'.format(text))
            text = ''

            deploy_method = service['Item']['serviceInfo']['deploy']['method'] \
                if 'method' in service['Item']['serviceInfo']['deploy'] else ''

            # Start deploy section.
            try:
                if deploy_method == 'serverless_lambda':

                    # Cases of when -e and/or -r flags are specified
                    # if '-r' in raw_inputs.split() and '-e' in raw_inputs.split():
                    if arg_region and arg_env:
                        text = 'Deploy `(%s)` via `(%s)` for `(%s)` `(%s)` ?' \
                               % (arg_service, 'Serverless', arg_env, arg_region)
                        # fallback = 'Deploy'
                        session_id = self.store_original_message_text_in_session(text)
                        callback = 'callback_default_CmdDeploy_changeset_' + session_id
                        return slack_ui_util.prompt_changeset(text, fallback_value, callback, serverless=True)

                    # elif '-e' in raw_inputs.split():
                    elif arg_env:
                        # Prompt regions buttons
                        regions = [region for region in service['Item']['serviceInfo']['regions'][arg_env]]
                        text = "Select the region in `(%s)` of service `(%s)` in which you " \
                               "would like to deploy via `(%s)` " % (arg_env, arg_service, 'Serverless')
                        # fallback = 'Deploy'
                        session_id = self.store_original_message_text_in_session(text)
                        callback = 'callback_default_CmdDeploy_region_' + session_id
                        return slack_ui_util.prompt_regions(text, fallback_value, callback, regions)

                    text = 'Select the environment in which you would like to deploy via `(%s)` for service ' \
                           '`(%s)`. If you do not want to deploy, press cancel.' % ('Serverless', arg_service)
                    # fallback = 'Deploy'
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_default_CmdDeploy_env_' + session_id
                    return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)

                # Make sure when --rollback is called, -e and -r is also provided
                if arg_rollback and (not arg_env or not arg_region):
                    text = 'Please provide an environment `-e` ' \
                           'and region `-r` to rollback for service `%s`' % arg_service
                    return slack_ui_util.error_response(text)

                # If no version flag value was provided, look up previous builds from ES
                es_client = aws_util.setup_es()

                # Exception for services tfs-legacy and tfs-legacy-canary
                tfs_other_flag = False
                tfs_service_holder = ''
                if arg_service == 'tfs-legacy' or arg_service == 'tfs-legacy-canary':
                    tfs_other_flag = True
                    tfs_service_holder = arg_service
                    arg_service = 'tfs'

                # If version flag value is provided
                if arg_version:
                    if arg_rollback:
                        text = 'The `-v` and `--rollback` flags can not be used at the same time.'
                        return slack_ui_util.error_response(text)

                    # Change service name if service and image name are different so image_prompt can find builds on ES
                    # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                    #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

                    search = es_client.search(index='build*',
                                              q='dockertag.keyword:\"%s\"' % arg_version,
                                              _source_include=['buildtime', 'dockertag', 'gitrepo', 'service'],
                                              sort=['buildtime:desc'],
                                              size=1)
                    if not search['hits']['hits']:
                        text = 'The specified version `%s` does not exist in Elastic Search.' \
                               % arg_version
                        return slack_ui_util.error_response(text)

                    if search['hits']['hits'][0]['_source']['service'] != arg_service:
                        text = 'The specified version `%s` does not have a relationship with service `%s`.' \
                               % (arg_version, arg_service)
                        return slack_ui_util.error_response(text)

                    # Change service name back if changed before
                    # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                    #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

                    image = arg_version

                    # Change back to original tfs service if true if -v specified
                    if tfs_other_flag:
                        arg_service = tfs_service_holder

                    # Cases of when -e and/or -r flags are specified
                    # if '-r' in raw_inputs.split() and '-e' in raw_inputs.split():
                    if arg_region and arg_env:
                        test_status = get_test_status_on_build(image, arg_env) + '\n'
                        text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                               % (arg_service, image, arg_env, arg_region)
                        # fallback = 'Deploy'
                        session_id = self.store_original_message_text_in_session(text)
                        callback = 'callback_default_CmdDeploy_changeset_' + session_id
                        return slack_ui_util.prompt_changeset(text, fallback_value, callback)

                    # elif '-e' in raw_inputs.split():
                    elif arg_env:
                        # Prompt regions buttons
                        regions = [region for region in service['Item']['serviceInfo']['regions'][arg_env]]
                        text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
                               "be deployed to." % (arg_env, arg_service, image)
                        # fallback = 'Deploy'
                        session_id = self.store_original_message_text_in_session(text)
                        callback = 'callback_default_CmdDeploy_region_' + session_id
                        return slack_ui_util.prompt_regions(text, fallback_value, callback, regions)

                    text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
                           '`(%s)`. If you do not want to deploy, press cancel.' % (image, arg_service)
                    # fallback = 'Deploy'
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_default_CmdDeploy_env_' + session_id
                    return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)

                # Change service name if service and image name are different so image_prompt can find builds on ES
                # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

                # ES query
                query = {
                    "query": {
                        "query_string": {
                            "query": "service.keyword:\"%s\" AND coverage.unittestcases.failed:0"
                                     % arg_service
                        }
                    }
                }
                search = es_client.search(index='build*',
                                          body=query,
                                          _source_include=['buildtime', 'dockertag', 'gitrepo'],
                                          sort=['buildtime:desc'],
                                          size=3)

                # Change name back if service name was changed originally due to image name difference
                # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

                # Change back to original tfs service if true if -v not specified
                if tfs_other_flag:
                    arg_service = tfs_service_holder

                # If flags -r/-e
                # if '-r' in raw_inputs.split() and '-e' in raw_inputs.split():
                if arg_region and arg_env:
                    if arg_rollback:

                        # Change service name if service and image name are diff so image_prompt can find builds on ES
                        # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                        #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

                        # ES query for deploy history
                        rollback_query = {
                            "query": {
                                "query_string": {
                                    "query": "service.keyword:\"%s\" AND environment:\"%s\" AND region:\"%s\""
                                             % (arg_service, ENVIRONMENTS[arg_env], arg_region)
                                }
                            }
                        }
                        rollback_search = es_client.search(index='deploy*',
                                                           body=rollback_query,
                                                           sort=['deploy_time:desc'],
                                                           size=10)

                        # Change name back if service name was changed originally due to image name difference
                        # if arg_service in DIFFERENT_NAME_IMAGE_SERVICES:
                        #     arg_service = DIFFERENT_NAME_IMAGE_SERVICES[arg_service]

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
                               % (current_image, arg_service, rollback_image, arg_env, arg_region)
                        session_id = self.store_original_message_text_in_session(text)
                        callback = 'callback_default_CmdDeploy_changeset_' + session_id
                        return slack_ui_util.prompt_changeset(text, fallback_value, callback, rollback=True)

                    text = 'Here are the last couple builds for service `(%s)`. ' \
                           'Select the one you would like to deploy to `(%s)` `(%s)`. ' \
                           'Otherwise press cancel.' % (arg_service, arg_env, arg_region)
                    # fallback = 'Deploy'
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_default_CmdDeploy_images_with_all_' + session_id
                    return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

                # elif '-e' in raw_inputs.split():
                elif arg_env:
                    text = 'Here are the last couple builds for service `(%s)`. ' \
                           'Select the one you would like to deploy to `(%s)`. ' \
                           'Otherwise press cancel.' % (arg_service, arg_env)
                    # fallback = 'Deploy'
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_default_CmdDeploy_images_with_env_' + session_id
                    return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

                text = 'Here are the last couple builds for service `(%s)`. ' \
                       'Select the one you would like to deploy. Otherwise press cancel.' \
                       % arg_service
                # fallback = 'Deploy'
                session_id = self.store_original_message_text_in_session(text)
                callback = 'callback_default_CmdDeploy_images_' + session_id
                return slack_ui_util.prompt_images(search['hits']['hits'], text, fallback_value, callback)

            except ShowSlackError as slack_error_message:
                print(type(slack_error_message))
                print(slack_error_message.args)
                print(slack_error_message)

                return slack_ui_util.error_response(slack_error_message)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_history_properties(self):
        """
        The properties for the "history" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<history>` To check history of a service',
            'help_examples': [
                '/bud deploy history -s content -n 5 -e dev -r us-east-1 -c false',
                '/bud deploy history -s homescreen -r us-east-1 -c true'
            ],
            'switch-templates': ['env-optional', 'service', 'region-optional'],
            'switch-n': {
                'aliases': ['n', 'numdeploys'],
                'type': 'int',
                'required': False,
                'lower_case': True,
                'help_text': 'Number of deploys to show. (Default: 10)'
            },
            'switch-c': {
                'aliases': ['c', 'changeset'],
                'type': 'string',
                'required': False,
                'lower_case': True,
                'help_text': 'Changeset flag, takes in string *true* or *false*. (Default: Shows both)'
            }
        }
        return props

    def invoke_history(self, cmd_inputs):
        """
        Placeholder for "history" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_history")
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_service = cmd_inputs.get_by_key('service')
            arg_numdeploys = cmd_inputs.get_by_key('numdeploys')
            if not arg_numdeploys:
                arg_numdeploys = 10
            arg_changeset = cmd_inputs.get_by_key('changeset')  # String 'true' | 'false'
            response_url = cmd_inputs.get_response_url()

            # Setup ES client
            es_client = aws_util.setup_es()

            # inputs.
            env = " AND environment:\"%s\"" % ENVIRONMENTS[arg_env] if arg_env else ''
            region = " AND region:\"%s\"" % arg_region if arg_region else ''
            changeset = ''
            if arg_changeset:
                changeset = ' AND changeset: "{}"'.format(arg_changeset)
                print("Changeset: {}".format(changeset))

            # ES query
            es_query_str = '{}{}{}{}'.format(arg_service, env, region, changeset)
            print ('es_query_str={}'.format(es_query_str))
            query = {
                "query": {
                    "query_string": {
                        "query": 'service.keyword:{}'.format(es_query_str)
                    }
                }
            }
            search = es_client.search(
                index='deploy*',
                body=query,
                sort=['deploy_time:desc'],
                size=arg_numdeploys
            )

            search_list = search['hits']['hits']
            output = ''

            for deploy in search_list:
                try:
                    date = datetime.strptime(deploy['_source']['deploy_time'], '%Y-%m-%dT%H:%M:%S')
                    date = date.strftime('%b %d, %Y - %I:%M:%S %p')
                    image_name = deploy['_source']['image_name'].split(':', 1)[1]
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
                    text = '%s deploys do not exist with the specified filters. Lower the number.' % arg_numdeploys
                    return slack_ui_util.error_response(text)

            if search_list:
                title = 'Here are `%s` of the most recent deploy(s) for service `%s`' % (arg_numdeploys, arg_service)
            else:
                title = 'No deploys can be found for service `%s` with specified input.' % arg_service
            text = output
            color = "#d77aff"
            return self.slack_ui_standard_response(title=title, text=text, color=color)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_status_properties(self):
        """
        The properties for the "history" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'longtask',
            'help_text': '`<status>` check current deployment version status',
            'help_examples': [
                '/bud deploy status -s content'
            ],
            'switch-templates': ['service']
        }
        return props

    def invoke_status(self, cmd_inputs):
        """
        Placeholder for "status" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_status")
            arg_service = cmd_inputs.get_by_key('service')
            response_url = cmd_inputs.get_response_url()

            # Start Status code section #### output to "text" & "title".
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            stack_name = cmd_specific_data.get('stack_name')
            cf_image = cmd_specific_data.get('cf_image')
            region_map = cmd_specific_data.get('region_map')

            text = 'Verify inputs first:\n'
            if arg_service:
                text += 'arg_service={}\n'.format(arg_service)
            if stack_name:
                text += 'stack_name={}\n'.format(stack_name)
            if cf_image:
                text += 'cf_image={}\n'.format(cf_image)
            if region_map:
                text += 'region_map={}\n'.format(region_map)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            service = arg_service
            region_map = cmd_specific_data.get('region_map')
            stack_name = cmd_specific_data.get('stack_name')
            cf_image = cmd_specific_data.get('cf_image')
            output = ''

            # Order map to enhance env readability
            order = ['dev', 'qa', 'prod']
            ordered_map = OrderedDict()
            for env in order:
                if env in region_map:
                    ordered_map[env] = region_map[env]

            LOGGER.info('ORDERED_MAP: %s' % ordered_map)
            ordered_dict = OrderedDict()

            # Loop through map
            for env in ordered_map:
                ordered_dict[env] = OrderedDict()
                for region in ordered_map[env]:
                    LOGGER.info('ENV/REGION: %s/%s' % (env, region))
                    session = aws_util.create_session(env)
                    try:
                        cf = aws_util.get_cloudformation_client(session, region)
                        stack_description = cf.describe_stacks(StackName=stack_name)
                        LOGGER.info('STACK DESCRIPTION : %s ' % stack_description)
                        index = get_parameter_index(cf_image, stack_description['Stacks'][0]['Parameters'])
                        LOGGER.info('index : %s ' % index)
                        full_version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
                        current_version = full_version.split(':')[1] if ':' in full_version and 'recsys-emr-jar' not in full_version else full_version
                        ordered_dict[env][region] = current_version
                    except:
                        error_text = "The service *[%s]* may not have a CF stack with the version as a " \
                                     "parameter, or does not exist in *[serviceInfo]*..." % service
                        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            LOGGER.info('Ordered dict : %s' % ordered_dict)

            # Setup ES client
            es_client = aws_util.setup_es()

            # Loops through dict and fathers the image info from ES and prints
            for env in ordered_dict:
                output += '```[%s]```\n' % env
                max_num_env = 0

                # Determines max build number
                for region in ordered_dict[env]:
                    if '-' not in ordered_dict[env][region]:
                        continue
                    build_num = ordered_dict[env][region].rsplit('-', 1)[1]
                    # If last element has a .suffix (for example recsys emr builds have them
                    if '.' in build_num:
                        build_num = build_num.split('.')[0]
                    build_num = int(build_num)
                    if build_num > max_num_env:
                        max_num_env = build_num

                for region in ordered_dict[env]:
                    current_version = ordered_dict[env][region]

                    # If parameter value is None or some non traditional value
                    if '-' not in current_version:
                        output += '_%s_: `%s` - `?` `?`\n' % (region, current_version)
                        continue

                    query_version = '"' + service + '\:' + current_version + '"'
                    build_num = current_version.rsplit('-', 1)[1]
                    # If last element has a .suffix (for example recsys emr builds have them
                    if '.' in build_num:
                        build_num = build_num.split('.')[0]
                    build_num = int(build_num)
                    LOGGER.info('build num for %s  %s : %s' % (env, region, build_num))
                    LOGGER.info('max env num for %s  %s : %s' % (env, region, max_num_env))

                    # ES query
                    query = {
                        "query": {
                            "query_string": {
                                "query": "changeset.keyword:(false OR true) AND "
                                         "region.keyword:%s AND "
                                         "image_name.keyword:%s "
                                         "AND environment:%s"
                                         % (region, query_version, ENVIRONMENTS[env])
                            }
                        }
                    }

                    # Search using the specified query and sort by most recent deploy job number
                    search = es_client.search(index='deploy*',
                                              body=query,
                                              _source_include=['deploy_time',
                                                               'deploy_job_number',
                                                               'image_name',
                                                               'service',
                                                               'userID'],
                                              sort=['deploy_job_number.keyword:desc'],
                                              size=4
                                              )
                    user_id = search['hits']['hits'][0]['_source']['userID'] \
                        if search['hits']['hits'] else '?'
                    deploy_time = search['hits']['hits'][0]['_source']['deploy_time'] \
                        if search['hits']['hits'] else '?'

                    # Check if an environment in the same region has a out of date version
                    if build_num < max_num_env:
                        output += '_%s_: `%s*` - `%s` `%s`\n' \
                                  % (region, current_version, deploy_time, user_id)
                    else:
                        output += '_%s_: `%s` - `%s` `%s`\n' \
                                  % (region, current_version, deploy_time, user_id)

            output += '\n\n\n`*` - _Signifies that the version may potentially be out of ' \
                      'date compared to those of other regions in the same environment_'

            return self.slack_ui_standard_response(
                title='Here are the current versions of `%s` deployed for service `%s`:' % (cf_image, service),
                text=output,
                color="#d77aff"
            )

            # End Status code section. ####

            # Standard response below. Change title and text for output.
            title = "Status title"
            return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")
# {#sub_command_prop_method_def#}


    # End Command's Properties section
    # ###################################
    # Start Command's implemented interface method section

    def run_command(self):
        """
        DON'T change this method. It should only be changed but the
        create_command, add_sub_command, and remove_sub_command scripts.

        In this method we look up the sub-command being used, and then the
        properties for that sub-command. It parses and validates the arguments
        and deals with invalid arguments.

        If the arguments are good. It next determines if this sub command
        needs to be invoked via the longtask lambda, or can run in (this)
        shorttask lambda. It then packages the arguments up properly and
        runs that command.

        :return: SlackUI response.
        """
        return self.default_run_command()

# {#invoke_command#}

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """
        cmd_inputs = self.get_cmd_input()
        arg_service = cmd_inputs.get_by_key('service')

        # Create DDB boto3 resource
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service_info_response = services_table.get_item(Key={'serviceName': arg_service})

        # If specified service not in table
        if 'Item' not in service_info_response:
            error_text = 'The specified service does not exist in table `ServiceInfo`.'
            return slack_ui_util.error_response(error_text)

        region_map = service_info_response['Item']['serviceInfo']['regions']
        try:
            stack_name = service_info_response['Item']['serviceInfo']['properties_table']['stack_name']
        except Exception as ex:
            stack_name = ''
            bud_helper_util.log_traceback_exception(ex)

        cf_image = service_info_response['Item']['serviceInfo']['deploy']['image_name'] \
            if 'image_name' in service_info_response['Item']['serviceInfo']['deploy'] else 'None'

        cmd_specific_data = {
            'region_map': region_map,
            'stack_name': stack_name,
            'cf_image': cf_image
        }

        return cmd_specific_data

    def invoke_confirm_command(self):
        """
        Only fill out this section in the rare case your command might
        prompt the Slack UI with buttons ect. for responses.
        Most commands will leave this section blank.
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print('invoke_confirm_command')
            cmd_inputs = self.get_cmd_input()
            params = cmd_inputs.get_confirmation_params()
            callback_id = cmd_inputs.get_callback_id()
            print('callback_id = {}'.format(callback_id))

            # Start confirmation code section.

            data = json.loads(params['payload'][0])
            original_message_text = self.get_original_message_text_from_callback_id(callback_id)

            if callback_id.startswith('callback_default_CmdDeploy_images_with_env'):
                return self.select_images(data, env=True,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_default_CmdDeploy_images_with_all'):
                return self.select_images(data, all_flags=True,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_default_CmdDeploy_images'):
                return self.select_images(data,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_default_CmdDeploy_env'):
                return self.select_regions(data,
                                      original_text=original_message_text)
            if callback_id.startswith('callback_default_CmdDeploy_region'):
                return self.select_changeset(data,
                                        original_text=original_message_text)
            if callback_id.startswith('callback_default_CmdDeploy_changeset'):
                return self.deploy(data,
                                   original_text=original_message_text)

            # Don't recognize this callback_id. Raise error.
            err_msg = 'Failed to find callback_id: {}'.format(callback_id)
            print(err_msg)
            raise ValueError(err_msg)

            # End confirmation code section.
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    # End class functions
# ###################################
# Start static helper methods sections

# {#invoke_methods_section#}

    def deploy(self, data, original_text=None):
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
            re.findall('\(([^)]+)', original_text)
            # re.findall('\(([^)]+)', data['original_message']['text'])

        # Run deploy job
        return self.deploy_helper(service_name, image, selected_env,
                             selected_region, selected_changeset, user, response_url)

    def deploy_helper(self, service_name, image, selected_env, selected_region, selected_changeset, user, response_url):
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
                    if env == 'qa' and region == 'us-west-2' and service_name not in QA_US_WEST_2_SERVICES:
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
            return self.slack_ui_standard_response(None, text)

        elif deploy_method == 'serverless_lambda':
            for env in envs:
                for region in regions:
                    full_deploy_url = '{url}buildWithParameters?token={token}&' \
                                      'SERVICE_NAME={service}&AWS_ACCOUNT={account}' \
                                      '&REGION={region}{user}{response_url}'\
                        .format(url=deploy_url,
                                token=urllib2.quote(TOKEN),
                                service=urllib2.quote(service_name),
                                account=ACCOUNTS[env],
                                region=region,
                                user='&TAGS=' + user,
                                response_url='&RESPONSE_URL=' + response_url)
                    urllib2.urlopen(full_deploy_url)
                    text = "The deploy job(s) for `%s` have kicked off. ```%s``` " % (service_name, deploy_url)
                    return self.slack_ui_standard_response(None, text)

        # Error text
        text = "The deploy job for `%s` failed to kicked off. Check ```%s``` to see " \
               "why..." % (service_name, deploy_url)
        return slack_ui_util.error_response(text)

    def handle_deploy_history(self, args):
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
                full_image_name = deploy['_source']['image_name']
                image_name = full_image_name.split(':', 1)[1]
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
        return self.slack_ui_standard_response(title=title, text=text, color=color)

    def select_changeset(self, data, original_text=None):
        """
        Select whether to deploy as a changeset.

        :param data: - Data sent back via Slack
        """

        # If cancel was pressed
        selected_region = data['actions'][0]['value']
        if selected_region == 'cancel':
            text = "Gotcha! The deploy was canceled!"
            return slack_ui_util.error_response(text)

        selected_env, service_name, image = re.findall('\(([^)]+)', original_text)
        # selected_env, service_name, image = re.findall('\(([^)]+)', data['original_message']['text'])

        # If unchanged version was selected, get current image on CF
        if 'Unchanged/Current Version' in image:
            image = get_current_image(service_name, selected_env, selected_region)

        if image == 'Serverless':
            text = 'Deploy `(%s)` via `(%s)` for `(%s)` `(%s)` ?' \
                   % (service_name, image, selected_env, selected_region)

            fallback_value = CmdDeploy(None).set_fallback_value()
            # fallback = 'Deploy'
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_default_CmdDeploy_changeset_' + session_id
            return slack_ui_util.prompt_changeset(text, fallback_value, callback, serverless=True)

        test_status = get_test_status_on_build(image, selected_env) + '\n'

        # Prompt changeset confirmation
        text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                             % (service_name, image, selected_env, selected_region)

        fallback_value = CmdDeploy(None).set_fallback_value()
        # fallback = 'Deploy'
        session_id = self.store_original_message_text_in_session(text)
        callback = 'callback_default_CmdDeploy_changeset_' + session_id
        return slack_ui_util.prompt_changeset(text, fallback_value, callback)

    def select_regions(self, data, original_text=None):
        """
        Select regions to deploy button menu.

        :param data: - Data sent back via Slack
        """

        # If cancel was pressed
        selected_env = data['actions'][0]['value']
        if selected_env == 'cancel':
            text = "Gotcha! The deploy was canceled!"
            return slack_ui_util.error_response(text)

        image, service_name = re.findall('\(([^)]+)', original_text)
        # image, service_name = re.findall('\(([^)]+)', data['original_message']['text'])

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
        text = "Select the region in `(%s)` of service `(%s)` in which you would " \
               "like to deploy via `(%s)`" % (selected_env, service_name, image)

        fallback_value = CmdDeploy(None).set_fallback_value()
        session_id = self.store_original_message_text_in_session(text)
        callback = 'callback_default_CmdDeploy_region_' + session_id

        if 'Unchanged/Current Version' in image:
            return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, all_regions=False)

        return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, missing_regions=missing_regions)

    def select_images(self, data, env=False, all_flags=False, original_text=None):
        """
        Select regions to deploy button menu.

        :param data: - Data sent back via Slack
        :param env: - If -e flag is set only
        :param all_flags: - If -r and -e flags are set
        """

        print('ALL_FLAGS:' + str(all_flags))
        print('ENV:' + str(env))
        print('ORIGINAL_TEXT:' + str(original_text))

        # If cancel was pressed
        selected_image = data['actions'][0]['value']
        if selected_image == 'cancel':
            text = "Gotcha! The deploy was canceled!"
            return slack_ui_util.error_response(text)

        if all_flags and not env:

            # Prompt changeset
            service_name, selected_env, selected_region = \
                re.findall('\(([^)]+)', original_text)
                # re.findall('\(([^)]+)', data['original_message']['text'])

            # If unchanged version was selected, get current image on CF
            if 'Unchanged/Current Version' in selected_image:
                selected_image = get_current_image(service_name, selected_env, selected_region)

            test_status = get_test_status_on_build(selected_image, selected_env) + '\n'

            text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                                 % (service_name, selected_image, selected_env, selected_region)

            fallback_value = CmdDeploy(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_default_CmdDeploy_changeset_' + session_id
            return slack_ui_util.prompt_changeset(text, fallback_value, callback)

        elif not all_flags and env:

            service_name, selected_env = re.findall('\(([^)]+)', original_text)
            # service_name, selected_env = re.findall('\(([^)]+)', data['original_message']['text'])

            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})

            # Prompt regions buttons
            regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
            text = "Select the region in `(%s)` of service `(%s)` in which you would like `(%s)` to " \
                   "be deployed to." % (selected_env, service_name, selected_image)

            fallback_value = CmdDeploy(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_default_CmdDeploy_region_' + session_id

            if 'Unchanged/Current Version' in selected_image:
                return slack_ui_util.prompt_regions(text, fallback_value, callback, regions, all_regions=False)

            return slack_ui_util.prompt_regions(text, fallback_value, callback, regions)

        else:
            service_name = re.findall('\(([^)]+)', original_text)[0]
            # service_name = re.findall('\(([^)]+)', data['original_message']['text'])[0]

            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})

            # Prompt environments
            text = 'Select the environment in which you would like to deploy `(%s)` for service ' \
                   '`(%s)`. If you do not want to deploy, press cancel.' % (selected_image, service_name)

            fallback_value = CmdDeploy(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_default_CmdDeploy_env_' + session_id
            region_map = service['Item']['serviceInfo']['regions']

            if 'Unchanged/Current Version' in selected_image:
                return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map, dev_and_qa=False)

            return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)


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

    version = 'None'
    try:
        stack_description = cf.describe_stacks(StackName=stack_name)
    except Exception as ex:
        return version

    params_map = stack_description['Stacks'][0]['Parameters']

    for index, param in enumerate(params_map):
        if param['ParameterKey'] == image_key:
            version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
            break

    if ':' in version and service_name not in NON_SPLIT_IMAGE_SERVICES:
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


# Gets parameter index for deploy
def get_parameter_index(cf_image, lst_of_map):
    """
    Entry point when deploy status is called

    :param cf_image: - Image Parameter Name
    :param lst_of_map: - List of the parameters map
    """
    for index, dic in enumerate(lst_of_map):
        LOGGER.info('LIST OF MAPS PARAM:' % lst_of_map)
        LOGGER.info('for loop index %s dic %s value %s' % (index, dic, dic['ParameterKey']))
        if dic['ParameterKey'] == cf_image:
            return index
    return -1


# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_deploy_main():
    """
    Entry point for command unit tests.
    :return: True if tests pass False if they fail.
    """
    try:
        # Fill in any needed tests here.

        return True
    except Exception as ex:
        bud_helper_util.log_traceback_exception(ex)
        return False