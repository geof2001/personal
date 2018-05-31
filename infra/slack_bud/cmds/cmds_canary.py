"""Implements Canary command by jscott"""
from __future__ import print_function
import trace
import re
import requests
import logging
import json
import time
import boto3
import urllib2
from datetime import datetime

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


ENVIRONMENTS = aws_util.ENVIRONMENTS
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
TOKEN = 'REGRESSIONISGOOD'
ES_HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
CREATE_METHODS = {
    'CF_create_V1': 'https://cidsr.eng.roku.com/job/zJs-cm/'
    # 'CF_create_V1': 'https://cidsr.eng.roku.com/view/Deploy/job/deploy-canary-service/'
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

class CmdCanary(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['create'],
            'help_title': '((WIP)Deploy canary builds for services)',
            'permission_level': 'dev',
            'props_create': self.get_create_properties()
        }
        return props

    # {#sub_command_prop_methods#}

    def get_create_properties(self):
        """
        The properties for the "create" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '`<create>` create a canary for the specified service',
            'help_examples': [
                '/bud canary create -e dev -r us-east-1 -s content',
                '/bud canary create -s content'
            ],
            'switch-templates': ['env-optional', 'service', 'region-optional'],
            'switch-v': {
                'aliases': ['v', 'version'],
                'type': 'string',
                'required': False,
                'lower_case': True,
                'help_text': 'Version of build to create as canary'
            }
        }
        return props

    def invoke_create(self, cmd_inputs, original_message_text=None):
        """
        Placeholder for "create" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        # Begin outer try statement
        try:
            print("invoke_create")
            print("@IC: cmd_inputs: {}".format(cmd_inputs))

            raw_inputs = cmd_inputs.get_raw_inputs()

            arg_service = cmd_inputs.get_by_key('service')
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_version = cmd_inputs.get_by_key('version')
            
            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': arg_service})
            region_map = service['Item']['serviceInfo']['regions']

            if 'Item' not in service:
                text = 'The service `%s` does not exist in the database.' % arg_service
                return slack_ui_util.error_response(text)

            text = 'Verify inputs first:\n'
            if arg_service:
                text += 'arg_service={}\n'.format(arg_service)
            if arg_region:
                text += 'arg_region={}\n'.format(arg_region)
            if arg_env:
                text += 'arg_env={}\n'.format(arg_env)
            if arg_version:
                text += 'arg_version={}\n'.format(arg_version)
            if raw_inputs:
                text += 'raw_inputs={}\n'.format(raw_inputs)
            print('@IC invoke_create_cmd_inputs={}'.format(text))
            text = ''
            
            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            user = cmd_specific_data.get('user_name')
        
            # stack_name = cmd_specific_data.get('stack_name')
            # image = arg_version
            callback = cmd_inputs.get_callback_id()
            fallback = self.set_fallback_value()
            
            print("@IC: Username is: {}".format(user))
            print("@IC: CMD_SPECIFIC_DATA: {}".format(cmd_specific_data))
            print("@IC: CALLBACK: {}".format(callback))
            print("@IC: FALLBACK: {}".format(fallback))
            
            es_client = aws_util.setup_es()

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
                                        _source_include=['buildtime', 'dockertag', 'gitrepo','service'],
                                        sort=['buildtime:desc'],
                                        size=3)
            print("@IC: SEARCH: {}".format(search))
            print("@IC: SEARCH-HITS: {}".format(search['hits']['hits']))

            if arg_version:
                if not search['hits']['hits']:
                    text = 'The specified version `%s` does not exit in Elastic Search.' \
                            % arg_version
                    return slack_ui_util.error_response(text)

                if search['hits']['hits'][0]['_source']['service'] != arg_service:
                    text = 'The specified version `%s` is not related with service `%s`.'\
                            % (arg_version, arg_service)
                    return slack_ui_util.error_response(text)

                if arg_region and arg_service:
                    # Prompt environments
                    text = 'Which environment would you like to run `(%s)` as ' \
                           'canary for service `(%s)` in region `(%s)`.  If you ' \
                           'do not want to launch this canary, press cancel.' \
                            % (arg_version, arg_service, arg_region)
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_create_CmdCanary_env_' + session_id
                    return slack_ui_util.prompt_envs(text, fallback, callback, region_map, dev_and_qa=False)

                else:
                    text = 'Which environment would you like to deploy `(%s)` ' \
                           'for service `(%s)`.  Otherwise press cancel.' \
                           % (arg_version, arg_service)
                    session_id = self.store_original_message_text_in_session(text)
                    callback = 'callback_create_CmdCanary_env_' + session_id
                    return slack_ui_util.prompt_envs(text, fallback, callback, region_map)
                
                    
            if arg_service and arg_region:
                text = 'Pick an image for `(%s)` in region `(%s)` or press cancel' \
                    % (arg_service, arg_region)
                session_id = self.store_original_message_text_in_session(text)
                callback = 'callback_create_CmdCanary_images_with_all_' + session_id
                return slack_ui_util.prompt_images(
                    search['hits']['hits'],
                    text,
                    fallback,
                    callback
                )

            if arg_region and arg_env:
                # do ES query and prompt 
                text = 'Pick an image for `(%s)` in `(%s)` in region `(%s)` ' \
                'from below or press cancel.' % (arg_service, arg_env, arg_region)
                session_id = self.store_original_message_text_in_session(text)
                callback = 'callback_create_CmdCanary_' + session_id
                return slack_ui_util.prompt_images(
                    search['hits']['hits'],
                    text,
                    fallback,
                    callback
                )
            
            elif arg_env:
                # get regions from service info table and prompt
                # region_map = cmd_specific_data.get('region_map')
                # regions = [region for region in region_map[arg_env]]

                text = 'Pick an image for `(%s)` from below to deploy in `(%s)`.' \
                    % (arg_service, arg_env)
                session_id = self.store_original_message_text_in_session(text)
                callback = 'callback_create_CmdCanary_images_with_env_' + session_id
                return slack_ui_util.prompt_images(
                    search['hits']['hits'],
                    text,
                    fallback,
                    callback
                )

            text = 'Here are the last couple builds for service `(%s)`. ' \
                   'Select the one you would like to launch as a canary. ' \
                   'Otherwise press cancel.' % arg_service
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_images_' + session_id
            return slack_ui_util.prompt_images(search['hits']['hits'],text , fallback, callback)

        # Outer try except statements
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

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
        # This is default. Over ride if needed.
        return self.default_run_command()

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """
        # return empty dict by default
        cmd_inputs = self.get_cmd_input()
        arg_service = cmd_inputs.get_by_key('service')

        # fetching service table
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': arg_service})

        ###FROM USER CMD###
        print('@BCSD: service {}'.format(service))
        print('@BCSD: cmd_inputs={}'.format(cmd_inputs))

        if 'Item' not in service:
            text = 'The specified service does not exist in table `ServiceInfo`.'
            return slack_ui_util.error_response(text)

        # region_map = service['Item']['serviceInfo']['regions']
        
        try:
            stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
        except Exception as ex:
            stack_name=''
            bud_helper_util.log_traceback_exception(ex)

        cf_image = service['Item']['serviceInfo']['deploy']['image_name'] \
            if 'image_name' in service['Item']['serviceInfo']['deploy'] else 'None'
        
        sub_command = cmd_inputs.get_sub_command()
        raw_inputs = cmd_inputs.get_raw_inputs()

        print("%s invokes %s" % (self.__class__.__name__, sub_command))
        print("@raw_inputs", raw_inputs)

        if sub_command != 'list':
            user_name = cmd_inputs.get_slack_user_name()
            cmd_specific_data = {
                'user_name': user_name,
                'stack_name': stack_name,
                'cf_image': cf_image
            }
        else:
            cmd_specific_data = {}

        print('@BCSD: cmd_specific_data:{}'.format(cmd_specific_data))
        return cmd_specific_data
        ###FROM USER CMD###

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
            original_message_text = self.get_original_message_text_from_callback_id(callback_id)

            # Start confirmation code section.
            # Callback Id convention is callback_<sub-command-name>_<anything>

            # Replace_example below.
            # if callback_id == 'callback_mysubcommand_prompt_env':
            #     return some_method_to_handle_this_case(params)
            # if callback_id == 'callback_mysubcommand_prompt_region':
            #     return some_other_method_to_handle_region(params)
            
            data = json.loads(params['payload'][0])
            original_message_text = self.get_original_message_text_from_callback_id(callback_id)
            
            print('@ICC: cmd_inputs={}'.format(cmd_inputs))
            print('@ICC: params={}'.format(params))
            print('@ICC: callback_id={}'.format(callback_id))
            print('@ICC: original_message_text={}'.format(original_message_text))
            print('@ICC: data={}'.format(data))

            if callback_id.startswith('callback_create_CmdCanary_images_with_env'):
                print('@ICC-if[0]: Got a callback_id of {}'.format(callback_id))
                return self.select_images(data, env=True,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_create_CmdCanary_images_with_all'):
                print('@ICC-if[1]: Got a callback_id of {}'.format(callback_id))
                return self.select_images(data, all_flags=True,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_create_CmdCanary_images'):
                print('@ICC-if[2]: Got a callback_id of {}'.format(callback_id))
                return self.select_images(data,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_create_CmdCanary_env'):
                print('@ICC-if[3]: Got a callback_id of {}'.format(callback_id))
                return self.select_env(data,
                                     original_text=original_message_text)
            if callback_id.startswith('callback_create_CmdCanary_regions'):
                print('@ICC-if[4]: Got a callback_id of {}'.format(callback_id))
                return self.approve_canary(data,    
                    original_text=original_message_text)
            if callback_id.startswith('callback_create_CmdCanary_'):
                print('@ICC-if[5]: Got a callback_id of {}'.format(callback_id))
                return self.canary_create(data, 
                    original_text=original_message_text)
            else:
                print('ERROR: Failed to find callback id! callback_id="{}"'.format(callback_id))
                raise ShowSlackError("Invalid callback id. Check logs.")

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

# End class functions
# ###################################
# Start static helper methods sections

    def canary_create(self, data, original_text=None):
        """
            Create canary helper
        """
        print("@ENTRYPOINT_canary_create: data={}".format(data))

        # Gather info from data
        cmd_inputs = self.get_cmd_input()

        cmd_specific_data = cmd_inputs.get_cmd_specific_data()
        user = data['user']['name']
        
        # If cancel as pressed
        selected_response = data['actions'][0]['value']
        
        if selected_response in ["cancel", "no"]:
            text = "Understood, your canary will fly another day!"
            return slack_ui_util.error_response(text)

        else:
            response_url = data['response_url']
            print('@CC: original_text: {}'.format(original_text))


            image, service_name, selected_env, selected_region = \
                re.findall('\(([^)]+)', original_text)
            
            fieldCount = len(image.rsplit('-'))
            branchName = []
            if fieldCount >= 4:
                print('have fun it was longer!')
                while fieldCount > 3:
                    branchName.append(image.rsplit('-')[-fieldCount])
                    fieldCount -= 1
                branchName = '-'.join(branchName)
            else:
                text = 'This is no image what have you done!'
                print(text)
                return slack_ui_util.error_response(text)
                
            stack_name = service_name + '-' + image.rsplit('-')[-1]
            print('@CC: ', branchName, stack_name)
            print('@CC: ',service_name,image,selected_env,selected_region,user)
            print('@CC: ',response_url)
            print('@CC: ',original_text)
        
            create_event = dict()

            date = datetime.now()
            createtime = datetime.strftime(date, '%Y-%m-%dT%H:%M:%S')

            # create_event['eventCategory'] = arg_cmd_0
            # create_event['eventType'] = arg_cmd_1
            create_event['createTime'] = createtime
            create_event['serviceName'] = service_name
            create_event['version'] = image
            create_event['region'] = selected_region
            create_event['environment'] = selected_env

            # record_event = es_client.index(index="canary", doc_type="event", id=1, body=create_event)
            record_event = aws_util.upload_json_to_es(create_event,'canary',ES_HOST, image)

            print("@IC: Event to record: %s \n %s" % (create_event, record_event))

            # Building URL to pass to jenkins (refactor later since we're not looking this up in dynamo really)
            create_method = 'CF_create_V1'
            create_url = CREATE_METHODS[create_method]

            if create_method == 'CF_create_V1':
                if selected_env == 'qa' and selected_region == 'us-west-2':
                    print('Doing nothing and returning') # do nothing and return
                full_create_url = '{url}buildWithParameters?token={token}&SERVICE_NAME={service}' \
                                    '&{accounts}&{regions}&{stack_name}' \
                                    '&{user}&{response_url}&{image}'\
                        .format(url=create_url, # STACK_COLOR - > STACK_NAME, BRANCH, CreateChangeSet??(not required)
                                token=urllib2.quote(TOKEN), # SUPERSECRETTOKEN Switch me to params
                                service=urllib2.quote(service_name), # SERVICE_NAME
                                accounts='AWS_ACCOUNTS=' + ACCOUNTS[selected_env], # AWS_ACCOuNTS
                                regions='&AWS_REGIONS=' + selected_region, # AWS_REGIONS
                                # ProdPush='&ProdPush=true' if prod_status else '', # ProdPush
                                stack_name='&STACK_NAME=' + stack_name, # STACK_NAME
                                user='&TAGS=' + user, # TAGS
                                response_url='&RESPONSE_URL=' + response_url, # RESPONSE_URL
                                image='&IMAGE_VERSION=' + service_name + ':' + image) #IMAGE_VERSION
                urllib2.urlopen(full_create_url)
                print(full_create_url)

            if not selected_region:
                # title = 'You didn\'t supply any regions for the create'
                title = cmd_specific_data.get('servicetable')
            else:    
                title = 'Creating a canary for `(%s)` with version `(%s)`' % (service_name, image)
            text = 'create_event: {}'.format(create_event)
            # session_id = self.store_original_message_text_in_session(text)
            # callback = 'callback_create_CmdCanary_' + session_id
            return  self.slack_ui_standard_response(title, text)

    def select_images(self, data, env=False, all_flags=False, original_text=None):
        """
        Select regions to deploy button menu.

        :param data: - Data sent back via Slack
        :param env: - If -e flag is set only
        :param all_flags: - If -r and -e flags are set
        """

        print('@SI: ALL_FLAGS: ' + str(all_flags))
        print('@SI: ENV: ' + str(env))
        print('@SI: ORIGINAL_TEXT: ' + str(original_text))
        print('@SI: DATA: {}'.format(data))
        print('@SI: BUILD: {}'.format(data['actions'][0]['value']))

        # If cancel was pressed
        selected_image = data['actions'][0]['value']
        if selected_image == 'cancel':
            text = "Understood, your canary will fly another day!"
            return slack_ui_util.error_response(text)

        if all_flags and env:

            # Prompt changeset
            service_name, selected_env, selected_region = \
                re.findall('\(([^)]+)', original_text)
                # re.findall('\(([^)]+)', data['original_message']['text'])

            test_status = get_test_status_on_build(selected_image, selected_env) + '\n'

            text = test_status + 'Deploy `(%s)` `(%s)` `(%s)` `(%s)` ?' \
                    % (service_name, selected_image, selected_env, selected_region)

            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_' + session_id
            return slack_ui_util.prompt_envs(text, fallback_value, callback)

        elif not all_flags and env:

            service_name, selected_env = re.findall('\(([^)]+)', original_text)
            
            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})

            # Prompt regions buttons
            regions = [region for region in service['Item']['serviceInfo']['regions'][selected_env]]
            
            text = 'Select the region in `(%s)` of service `(%s)` in which ' \
                    'you would like `(%s)` to be deployed to.' % \
                    (selected_env, service_name, selected_image)

            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_regions_' + session_id

            if 'Unchanged/Current Image' in selected_image:
                return slack_ui_util.prompt_regions(
                                                    text,
                                                    fallback_value,
                                                    callback,
                                                    regions,
                                                    all_regions=False
                                                    )

            return slack_ui_util.prompt_regions(
                                                text,
                                                fallback_value,
                                                callback,
                                                regions
                                                )
        elif all_flags and not env:
            service_name, selected_region = re.findall('\(([^)]+)', original_text)

            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})
            region_map = service['Item']['serviceInfo']['regions']

            text = 'Which environment would you like to run `(%s)` as canary ' \
                    'for service `(%s)` in region `(%s)`.  If you do not want ' \
                    'to launch this canary, press cancel.' % \
                    (selected_image, service_name, selected_region)
            
            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_env_' + session_id

            return slack_ui_util.prompt_envs(text, fallback_value, callback, region_map)

        else:
            service_name = re.findall('\(([^)]+)', original_text)[0]
            
            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})
            region_map = service['Item']['serviceInfo']['regions']
            
            # Prompt environments

            text = 'Which environment would you like to run `(%s)` as canary ' \
                    'for service `(%s)`.  If you do not want ' \
                    'to launch this canary, press cancel.' % \
                    (selected_image, service_name)

            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_env_' + session_id
            
            # if 'Unchanged/Current Image' in selected_image:
            #     return slack_ui_util.prompt_envs(
            #         text,
            #         fallback_value,
            #         callback,
            #         region_map,
            #         dev_and_qa=False
            #     )

            return slack_ui_util.prompt_envs(
                text,
                fallback_value,
                callback,
                region_map,
                dev_and_qa=False
            )

    def select_regions(self, data, original_text=None):
        """
        Select regions to launch canary button menu.

        :param data: - Data sent back via Slack
        """

        # If cancel was pressed
        selected_env = data['actions'][0]['value']
        if selected_env == 'cancel':
            text = "Understood, your canary will fly another day!"
            return slack_ui_util.error_response(text)
        print('@SR: data: {}'.format(data))
        print('@SR: selected_env: {}'.format(selected_env))
        print('@SR: original_text: {}'.format(original_text))

        image, service_name = re.findall('\(([^)]+)', original_text)
        
        print('@SR: image: {}, service_name: {}'.format(image, service_name))
        
        # Create DDB boto3 resource
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        service = services_table.get_item(Key={'serviceName': service_name})
        print('@SR: service_table: {}'.format(service))
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
               "like to launch a canary for `(%s)`" % (selected_env, service_name, image)

        fallback_value = CmdCanary(None).set_fallback_value()
        session_id = self.store_original_message_text_in_session(text)
        callback = 'callback_create_CmdCanary_regions_' + session_id

        if 'Unchanged/Current Image' in image:
            return slack_ui_util.prompt_regions(
                                                text,
                                                fallback_value,
                                                callback,
                                                regions,
                                                all_regions=False
                                                )

        return slack_ui_util.prompt_regions(
                                            text,
                                            fallback_value,
                                            callback,
                                            regions,
                                            missing_regions=missing_regions
                                            )

    def select_env(self, data, original_text=None):
        """
        Select the environment to deploy the canary in.

        :param data: data returned via Slack
        """

        print("@SE_ENTRYPOINT: data={}\n\toriginal_text: {}".format(data, original_text))

        # Cancel if requests

        selected_env = data['actions'][0]['value']
        if selected_env == 'cancel':
            text = "Understood, your canary will fly another day!"
            return slack_ui_util.error_response(text)

        if 'region' in original_text:
            print('@SE: original_text contained region'.format(original_text))
            image, service_name, selected_region = \
            re.findall('\(([^)]+)', original_text)
            print("@SE inputs: IMAGE: {}, SERVICE: {}, REGION: {}.".format(image, service_name, selected_region))
            
            text = "Start a canary of `(%s)` for `(%s)` in `(%s)` `(%s)`?" % \
            (image, service_name, selected_env, selected_region)

            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_' + session_id
            
            return slack_ui_util.ask_for_confirmation_response(text, fallback_value, callback)

        else:
            image, service_name = \
            re.findall('\(([^)]+)', original_text)
            print("@SE inputs: IMAGE: {}, SERVICE: {}.".format(image, service_name))
        
            # Create DDB boto3 resource
            dynamodb = boto3.resource('dynamodb')
            services_table = dynamodb.Table('ServiceInfo')
            service = services_table.get_item(Key={'serviceName': service_name})

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
                "like to launch a canary for `(%s)`" % (selected_env, service_name, image)

            fallback_value = CmdCanary(None).set_fallback_value()
            session_id = self.store_original_message_text_in_session(text)
            callback = 'callback_create_CmdCanary_regions_' + session_id
            
            if 'Unchanged/Current Image' in image:
                return slack_ui_util.prompt_regions(
                                                    text,
                                                    fallback_value,
                                                    callback,
                                                    regions,
                                                    all_regions=False
                                                    )

            return slack_ui_util.prompt_regions(
                                                text,
                                                fallback_value,
                                                callback,
                                                regions,
                                                missing_regions=missing_regions
                                                )

            
    
    def approve_canary(self, data, original_text=None):
        """
        Approve the canary that you want to launch with selected values

        :param data: Data returned via Slack
        """

        print("@AC_ENTRYPOINT: data={}".format(data))

        # Cancel pressed abort here
        selected_region = data['actions'][0]['value']
        if selected_region == 'no':
            text = "Understood, your canary will fly another day!"
            return slack_ui_util.error_response(text)

        # user = data['user']['name']
        # response_url = data['response_url']
        selected_env, service_name, image = re.findall('\(([^)]+)', original_text)

        print('@AC: selected_region: {}'.format(selected_region))
        print('@AC: selected_env: {}'.format(selected_env))
        print('@AC: service_name: {}'.format(service_name))
        print('@AC: image: {}'.format(image))

        text = "Start a canary of `(%s)` for `(%s)` in `(%s)` `(%s)`?" % \
            (image, service_name, selected_env, selected_region)

        fallback_value = CmdCanary(None).set_fallback_value()
        session_id = self.store_original_message_text_in_session(text)
        callback = 'callback_create_CmdCanary_' + session_id

        return slack_ui_util.ask_for_confirmation_response(text, fallback_value, callback)

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

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

def test_cases_cmd_canary_main():
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

if __name__ == "__main__":
    print("This is my main call")