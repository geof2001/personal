"""Implements Props command by asnyder"""
from __future__ import print_function
import json
import re
from operator import itemgetter
import boto3

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

DYNAMO_RESOURCE = boto3.resource('dynamodb')
SERVICE_INFO_TABLE = DYNAMO_RESOURCE.Table('ServiceInfo')

MAX_HISTORY_ITEMS = 15
AWS_REGIONS = aws_util.AWS_REGIONS


class CmdProps(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['list', 'set', 'get', 'history', 'restore', 'delete', 'copy'],
            'help_title': 'Gets the properties of the specified service',
            'permission_level': 'dev',
            'props_list': self.get_list_properties(),
            'props_set': self.get_set_properties(),
            'props_get': self.get_get_properties(),
            'props_history': self.get_history_properties(),
            'props_restore': self.get_restore_properties(),
            'props_delete': self.get_delete_properties(),
            'props_copy': self.get_copy_properties()
        }

        return props

    def get_list_properties(self):
        """
        The properties for the "list" sub-command
        Modify the values as needed, by leave keys alone.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*List* Lists service properties of all regions based on given environment',
            'help_examples': [
                '/bud props list -s content -e dev'
            ],
            'switch-templates': ['env', 'service', 'region-default'],
        }
        return props

    def invoke_list(self, cmd_inputs):
        """
        Placeholder for "list" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_list")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            regions = cmd_specific_data.get('regions')
            session = cmd_specific_data.get('session')
            service_response = cmd_specific_data.get('service_response')


            # Start Set code section #### output to "text" & "title".
            # text = ''
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if props_table:
            #     text += 'props_table = {}\n'.format(props_table)
            # if regions:
            #     text += 'regions = {}\n'.format(regions)
            # if session:
            #     text += 'session = {}\n'.format(session)
            # if service_response:
            #     text += 'service_response = {}\n'.format(service_response)


            # try:
            tables = {}
            stack_name = service_response['Item']['serviceInfo']['properties_table']['stack_name']
            for region in regions:
                props_table = bud_helper_util.get_props_table_name_for_stack_name(
                    session, region, stack_name, arg_service
                )
                dynamodb = aws_util.get_dynamo_resource(session, region)
                table = dynamodb.Table(props_table)
                tables[region] = table

            return  self.slack_ui_standard_response(
                title="Here are the properties of service *[%s]* for *[%s]* for every region...\n" % (
                    arg_service, arg_env),
                text=props_list_table(tables),
                color="#d77aff",
            )

            # End Set code section. ####

            # # Standard response below. Change title and text for output.
            # title = "Set title"
            # return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_set_properties(self):
        """
        The properties for the "set" sub-command
        Modify the values as needed, by leave keys alone.
        The 'confirmation' section is and advanced feature and commented out.
        Remove it unless you plan on using confirmation responses.

        When done reduce the DocString to a description of the
            sub-commands properties.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Set* Sets a property to the specified value. Add the *--create* flag to create a new property',
            'help_examples': [
                '/bud props set maxRetries 3 -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['region-default', 'env', 'service'],
            'switch-create': {
                'aliases': ['create'],
                'type': 'property',
                'required': False,
                'lower_case': True,
                'help_text': '--create property needed to create new property'
            },
            'switch-comment': {
                'aliases': ['c', 'comment'],
                'type': 'string',
                'required': False,
                'lower_case': False,
                'help_text': 'Optional comment to add to the table'
            }
        }
        return props

    def invoke_set(self, cmd_inputs):
        """
        Placeholder for "set" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_set")
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_service = cmd_inputs.get_by_key('service')
            arg_create = cmd_inputs.get_by_key('create')
            arg_comment = cmd_inputs.get_by_key('comment')

            response_url = cmd_inputs.get_response_url()
            is_public_response = cmd_inputs.is_public_response()

            arg_item_2 = cmd_inputs.get_by_index(2)
            arg_item_3 = cmd_inputs.get_by_index(3)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            session = cmd_specific_data.get('session')

            table = get_props_dynamo_table(session, arg_region, props_table)
        
            # Start Set code section #### output to "text" & "title".

            arg_item_2 = url_checker(arg_item_2)
            arg_item_3 = url_checker(arg_item_3)
            deleted_prop = table.get_item(
                Key={'key': '_deleted_{}'.format(arg_item_2)}
            )
            if not arg_create:
                text = "Are you sure you want to set property `(%s)` to value `(%s)`" \
                       ", from table `(%s)` for stack `(%s)` in `(%s)` `(%s)` with an optional comment of `%s`?" \
                       % (arg_item_2, arg_item_3,
                          props_table,
                          arg_service, arg_region, arg_env, arg_comment)
                fallback = CmdProps(None).set_fallback_value()

                session_id = self.store_original_message_text_in_session(text)
                callback_id = "callback_set_CmdProps_confirm_" + session_id
                return slack_ui_util.ask_for_confirmation_response(
                    text, fallback, callback_id,
                    is_public_response
                )
            else:
                if 'Item' in deleted_prop:

                    text = "This property used to exist and can be restored via " \
                           "the restore command. Are you sure you want to " \
                           "continue creating property `(%s)` with value `(%s)`, " \
                           "for table `(%s)` of stack `(%s)` in `(%s)` `(%s)` with an optional comment of `%s`?" \
                           % (arg_item_2, arg_item_3,
                              props_table,
                              arg_service, arg_region, arg_env, arg_comment)

                    fallback = CmdProps(None).set_fallback_value()

                    session_id = self.store_original_message_text_in_session(text)
                    callback_id = "callback_set_CmdProps_create_confirm_" + session_id

                    return slack_ui_util.ask_for_confirmation_response(
                        text, fallback, callback_id,
                        is_public_response
                    )

                text = "Are you sure you want to create property `(%s)` with" \
                       " value `(%s)`, for table `(%s)` of stack `(%s)` in `(%s)` `(%s)` " \
                       "with an optional comment of `%s`?" \
                       % (arg_item_2, arg_item_3,
                          props_table,
                          arg_service, arg_region, arg_env, arg_comment)

                session_id = self.store_original_message_text_in_session(text)
                fallback = CmdProps(None).set_fallback_value()
                callback_id = "callback_set_CmdProps_create_confirm_" + session_id

                return slack_ui_util.ask_for_confirmation_response(
                    text, fallback, callback_id,
                    is_public_response
                )
            # End Set code section. ####
        
            # # Standard response below. Change title and text for output.
            # title = "Set title"
            # return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_get_properties(self):
        """
        The properties for the "get" sub-command
        Modify the values as needed, by leave keys alone.

        The 'confirmation' section is and advanced feature and commented out.
        Remove it unless you plan on using confirmation responses.

        When done reduce the DocString to a description of the
            sub-commands properties.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Get* Gets the value of a specified property in all regions based on given environments',
            'help_examples': [
                '/bud props get maxRetries -s content -e dev'
            ],
            'switch-templates': ['env', 'service', 'region-default'],
        }
        return props

    def invoke_get(self, cmd_inputs):
        """
        Placeholder for "get" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_get")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()

            arg_item_2 = cmd_inputs.get_by_index(2)
            arg_item_2 = url_checker(arg_item_2)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            regions = cmd_specific_data.get('regions')
            session = cmd_specific_data.get('session')
            service_response = cmd_specific_data.get('service_response')
        
            # Start Get code section #### output to "text" & "title".
            prop_exists = False
            output = ''

            #if len(args.command) == 2:  # from cmds_props.py line 262
            if arg_item_2.startswith('-'):
                error_text = "Please specify which property value to get for stack " \
                             "*[%s]* in *[%s][%s]*. " \
                             % (arg_service, arg_env, arg_region)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            # Gathers regions from ServiceNames table
            stack_name = service_response['Item']['serviceInfo']['properties_table']['stack_name']
            for region in regions:
                props_table = bud_helper_util.get_props_table_name_for_stack_name(
                    session, region, stack_name, arg_service
                )
                dynamodb = aws_util.get_dynamo_resource(session, region)
                table = dynamodb.Table(props_table)
                response = table.get_item(Key={'key': arg_item_2})
                if 'Item' in response:
                    output += '_{}_ : {}\n'.format(region, response['Item']['value'])
                    prop_exists = True
                else:
                    output += '_{}_ : {}\n'.format(region, '-')

            if prop_exists:
                return  self.slack_ui_standard_response(
                    title="Here is the value of property *[%s]* for *[%s]* in all regions...\n"
                          % (arg_item_2, arg_env),
                    text=output,
                    color="#d77aff"
                )
            else:
                error_text = "Unable to get value of property *[%s]* for stack " \
                             "*[%s]* in *[%s]*. The property may not exist in " \
                             "any regions..." \
                             % (arg_item_2, arg_service, arg_env)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            # End Get code section. ####
        
            # # Standard response below. Change title and text for output.
            # title = "Get title"
            # return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_history_properties(self):
        """
        The properties for the "history" sub-command
        Modify the values as needed, by leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*History* Gets the value history of a specified property',
            'help_examples': [
                '/bud props history maxRetries -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['region-default', 'env', 'service']
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
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()

            arg_item_2 = cmd_inputs.get_by_index(2)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            session = cmd_specific_data.get('session')

            table = get_props_dynamo_table(session, arg_region, props_table)
        
            # Start History code section #### output to "text" & "title".
            # text = ''
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if props_table:
            #     text += 'props_table = {}\n'.format(props_table)

            arg_item_2 = url_checker(arg_item_2)
            item = table.get_item(
                Key={'key': arg_item_2}
            )
            deleted_item = table.get_item(
                Key={'key': '_deleted_{}'.format(arg_item_2)}
            )
            if 'Item' in item:
                try:
                    title = "History of property *[%s]* in table *[%s]* for " \
                            "stack *[%s]* in *[%s][%s]*..." \
                            % (arg_item_2,
                               props_table,
                               arg_service, arg_region, arg_env)
                    text = "%s" % self.props_history(table, arg_item_2)
                    return self.slack_ui_standard_response(title, text)
                except:
                    error_text = "Unable to gather history for property " \
                                 "*[%s]* of table *[%s]* for stack " \
                                 "*[%s]* in *[%s][%s]*. This property " \
                                 "may have never existed..." \
                                 % (arg_item_2,
                                    props_table,
                                    arg_service,
                                    arg_region,
                                    arg_env)
                    return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
            elif 'Item' in deleted_item:
                try:
                    title = "History of property *[%s]* in table *[%s]* for " \
                            "stack *[%s]* in *[%s][%s]*..." \
                            % (arg_item_2,
                               props_table,
                               arg_service,
                               arg_region,
                               arg_env)
                    text = "%s" % self.props_history(
                        table, '_deleted_{}'.format(arg_item_2)
                    )
                    return  self.slack_ui_standard_response(title, text)
                except:
                    error_text = "Unable to gather history for property *[%s]* " \
                                 "of table *[%s]* for stack *[%s]* in " \
                                 "*[%s][%s]*. There may be no history of this " \
                                 "property..." \
                                 % (arg_item_2,
                                    props_table,
                                    arg_service,
                                    arg_region,
                                    arg_env)
                    return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
            else:
                error_text = "Unable to gather history for property *[%s]* of " \
                             "table *[%s]* for stack *[%s]* in *[%s][%s]*. " \
                             "The property may have never existed..." \
                             % (arg_item_2,
                                props_table,
                                arg_service,
                                arg_region,
                                arg_env)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            # End History code section. ####
        
            # # Standard response below. Change title and text for output.
            # title = "History title"
            # return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_restore_properties(self):
        """
        The properties for the "restore" sub-command
        Modify the values as needed, by leave keys alone.

        The 'confirmation' section is and advanced feature and commented out.
        Remove it unless you plan on using confirmation responses.

        When done reduce the DocString to a description of the
            sub-commands properties.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Restore* Restores a specified property if it was deleted',
            'help_examples': [
                '/bud props restore maxRetries -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['region-default', 'env', 'service'],
        }
        return props

    def invoke_restore(self, cmd_inputs):
        """
        Placeholder for "restore" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_restore")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()

            arg_item_2 = cmd_inputs.get_by_index(2)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            session = cmd_specific_data.get('session')

            table = get_props_dynamo_table(session, arg_region, props_table)
        
            # Start Restore code section #### output to "text" & "title".
            # text = ''
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if props_table:
            #     text += 'props_table = {}\n'.format(props_table)

            arg_item_2 = url_checker(arg_item_2)
            deleted_prop = table.get_item(
                Key={'key': '_deleted_{}'.format(arg_item_2)}
            )
            if 'Item' not in deleted_prop:
                error_text = "Property *[%s]* from table *[%s]* for stack *[%s]*" \
                             " in *[%s][%s]* cannot be restored... The property " \
                             "may already exist, or no history exists for it." \
                             % (arg_item_2,
                                props_table,
                                arg_service, arg_region, arg_env)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)


            text = "Are you sure you want to restore property *(%s)* with value " \
                   "*(%s)* for table *(%s)* for stack *(%s)* in *(%s)(%s)*?" \
                   % (arg_item_2, deleted_prop['Item']['value'],
                      props_table,
                      arg_service, arg_region, arg_env)

            session_id = self.store_original_message_text_in_session(text)
            fallback = CmdProps(None).set_fallback_value()
            callback_id = "callback_restore_CmdProps_confirm_" + session_id

            return slack_ui_util.ask_for_confirmation_response(
                text, fallback, callback_id
            )

            # End Restore code section. ####
        
            # # Standard response below. Change title and text for output.
            # title = "Restore title"
            # return self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_delete_properties(self):
        """
        The properties for the "delete" sub-command
        Modify the values as needed, by leave keys alone.

        The 'confirmation' section is and advanced feature and commented out.
        Remove it unless you plan on using confirmation responses.

        When done reduce the DocString to a description of the
            sub-commands properties.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Delete* Deletes the specified property from the table',
            'help_examples': [
                '/bud props delete maxRetries -s content -e dev -r us-east-1'
            ],
            'switch-templates': ['region-default', 'env', 'service']
        }
        return props

    def invoke_delete(self, cmd_inputs):
        """
        Placeholder for "delete" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_delete")
            arg_region = cmd_inputs.get_by_key('region')
            arg_env = cmd_inputs.get_by_key('env')
            arg_service = cmd_inputs.get_by_key('service')
            response_url = cmd_inputs.get_response_url()

            arg_item_2 = cmd_inputs.get_by_index(2)

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            session = cmd_specific_data.get('session')

        
            # Start Delete code section #### output to "text" & "title".
            # text = ''
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if props_table:
            #     text += 'props_table = {}\n'.format(props_table)

            table = get_props_dynamo_table(session, arg_region, props_table)

            arg_item_2 = url_checker(arg_item_2)
            response = table.get_item(Key={'key': arg_item_2})
            if 'Item' not in response:
                error_text = "Key *[%s]* does not exist in table *[%s]* for " \
                             "stack *[%s]* in *[%s][%s]*..." \
                             % (arg_item_2,
                                props_table,
                                arg_service,
                                arg_region,
                                arg_env)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            text = "Are you sure you want to delete *(%s)* from table *(%s)* for" \
                   " stack *(%s)* in *(%s)(%s)*?" \
                   % (arg_item_2, props_table,
                      arg_service, arg_region, arg_env)

            session_id = self.store_original_message_text_in_session(text)
            fallback = CmdProps(None).set_fallback_value()
            callback_id = "callback_delete_CmdProps_confirm_" + session_id
            return slack_ui_util.ask_for_confirmation_response(
                text, fallback, callback_id, danger_style=True
            )

            # End Delete code section. ####

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_copy_properties(self):
        """
        The properties for the "copy" sub-command
        Modify the values as needed, but leave keys alone.

        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Copy* Copies the specified service properties table to another region/env',
            'help_examples': [
                '/bud props copy -s content -e dev -r us-east-1',
                'NOTE : The destination region/env must have a CF stack with its properties table listed',
                'as an output. Also the environment and region must exist for the service in the',
                'service_info.yaml file in GitLab'
            ],
            'switch-templates': ['region', 'env', 'service']
        }
        return props

    def invoke_copy(self, cmd_inputs):
        """
        Placeholder for "copy" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_copy")
            arg_region = cmd_inputs.get_by_key('region')  # remove if not used
            arg_env = cmd_inputs.get_by_key('env')  # remove if not used
            arg_service = cmd_inputs.get_by_key('service')  # remove if not used
            response_url = cmd_inputs.get_response_url()

            cmd_specific_data = cmd_inputs.get_cmd_specific_data()
            props_table = cmd_specific_data.get('props_table')
            region_map = cmd_specific_data.get('region_map')
            session = cmd_specific_data.get('session')

        
            # Start Copy code section #### output to "text" & "title".
            # text = ''
            # if arg_region:
            #     text += 'arg_region = {}\n'.format(arg_region)
            # if arg_env:
            #     text += 'arg_env = {}\n'.format(arg_env)
            # if arg_service:
            #     text += 'arg_service = {}\n'.format(arg_service)
            # if props_table:
            #     text += 'props_table = {}\n'.format(props_table)
            # if region_map:
            #     text += 'region_map = {}\n'.format(region_map)

            table = get_props_dynamo_table(session, arg_region, props_table)

            result = table.scan()
            if 'Items' not in result:
                error_text = 'The properties table *[%s]* is empty in *[%s][%s]* or does not exist...' \
                             % (props_table, arg_region, arg_env)
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
            text = 'Select the environment you would like to copy table *(%s)* of *(%s)* from *(%s)(%s)* to...' \
                   % (props_table, arg_service, arg_region, arg_env)

            session_id = self.store_original_message_text_in_session(text)
            fallback = CmdProps(None).set_fallback_value()
            callback_id = 'callback_copy_CmdProps_select_env_' + session_id
            return slack_ui_util.prompt_envs(
                text, fallback, callback_id, region_map, dev_and_qa=False)

            # End Copy code section. ####
        
            # Standard response below. Change title and text for output.
            title = "Copy title"
            return self.slack_ui_standard_response(title, text)
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
        return self.default_run_command()

    def build_cmd_specific_data(self):
        """
        If you need specific things common to many sub commands like
        dynamo db table names or sessions get it here.

        If nothing is needed return an empty dictionary.
        :return: dict, with cmd specific keys. default is empty dictionary
        """

        # We want to make a map with
        cmd_inputs = self.get_cmd_input()

        arg_env = cmd_inputs.get_by_key('env')
        arg_service = cmd_inputs.get_by_key('service')
        arg_region = cmd_inputs.get_by_key('region')
        service_response = SERVICE_INFO_TABLE.get_item(Key={'serviceName': arg_service})

        try:
            session = aws_util.create_session(arg_env)
        except:
            err_msg = 'The environment *[{}]* does not exist for this service...'.format(arg_env)
            raise ShowSlackError(err_msg)

        if arg_region not in AWS_REGIONS:
            err_msg = 'The region *[{}]* does not exist for this service...'.format(arg_region)
            raise ShowSlackError(err_msg)

        try:
            stack_name = service_response['Item']['serviceInfo']['properties_table']['stack_name']
            props_table = bud_helper_util.get_props_table_name_for_stack_name(
                session, arg_region, stack_name, arg_service
            )
        except:
            err_msg = 'The service *{}* may not have a properties ' \
            'table in its CF output, or does not exist in *[serviceInfo]*...'.format(arg_service)
            raise ShowSlackError(err_msg)

        region_map = service_response['Item']['serviceInfo']['regions']
        regions = [region for region in region_map[arg_env]]

        cmd_specific_data = {
            'props_table': props_table,  # This will be props table name
            'regions': regions,  # This is a region list.
            'region_map': region_map,  # This is a region_map
            'session': session,  # This is a session
            'service_response': service_response  # This is a service response.
        }

        # Some sub-command will want a dynamo table for a region.
        # They can use session information and region info to build that.

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
            print('invoke_confirm_command: callback_id = {}'.format(callback_id))

            # Start confirmation code section.
            # Callback Id convention is callback_<sub-command-name>_<anything>

            # Replace_example below.
            # if callback_id == 'callback_mysubcommand_prompt_env':
            #     return some_method_to_handle_this_case(params)
            # if callback_id == 'callback_mysubcommand_prompt_region':
            #     return some_other_method_to_handle_region(params)

            data = json.loads(params['payload'][0])
            original_message_text = self.get_original_message_text_from_callback_id(callback_id)

            print('invoke_confirm_command: data={}'.format(data))

            if callback_id.startswith('callback_delete_CmdProps_confirm'):
                return self.props_delete(data, original_message_text)
            if callback_id.startswith('callback_set_CmdProps_confirm'):
                return self.props_set(data, original_message_text)
            if callback_id.startswith('callback_set_CmdProps_create_confirm'):
                return self.props_create(data, original_message_text)
            if callback_id.startswith('callback_restore_CmdProps_confirm'):
                return self.props_restore(data, original_message_text)
            if callback_id.startswith('callback_copy_CmdProps_select_env'):
                return self.props_copy_env(data, original_message_text)
            if callback_id.startswith('callback_copy_CmdProps_select_region'):
                return self.props_copy_region(data, original_message_text)
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

    def props_history(self, table, key):
        """Output history"""
        current_value = table.get_item(Key={'key': key})['Item']['value']
        history = table.get_item(Key={'key': key})['Item']['history'] \
            if 'history' in table.get_item(Key={'key': key})['Item'] else '-'
        current_time = table.get_item(Key={'key': key})['Item']['time'] \
            if 'time' in table.get_item(Key={'key': key})['Item'] else '-'
        current_user = table.get_item(Key={'key': key})['Item']['user'] \
            if 'user' in table.get_item(Key={'key': key})['Item'] else '-'
        if key.startswith('_deleted_'):
            output = '*ATTENTION* : _This property has been deleted ' \
                 'and does not exist in the current table!!!_\n'
        else:
            output = ''
        output += props_line_separator()
        output += '*%s*\n' % current_time
        output += '_Set by_ : %s\n' % current_user
        output += '_Set to_ : %s\n' % current_value
        if history != '-':
            for item in reversed(history):
                output += props_line_separator()
                output += '*%s*\n' % item['Date']
                output += '_Set by_ : %s\n' % item['User']
                output += '_Set to_ : %s\n' % item['Value']
        return output

    def props_delete(self, data, original_message_text=None):
        """Delete properties."""

        prop, db_table, stack, region, env =\
            re.findall('\(([^)]+)', original_message_text)
        prop = url_checker(prop)
        session = aws_util.create_session(env)
        dynamodb = aws_util.get_dynamo_resource(session, region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                if not prop.startswith('_deleted_'):
                    response = table.get_item(Key={'key': prop})
                    value = response['Item']['value'] if 'value' in response['Item'] else '-'
                    time = aws_util.get_prop_table_time_format()
                    history = response['Item']['history'] if 'history' in response['Item'] else ''
                    user = data['user']['name']

                    if history:
                        table.update_item(Key={'key': '_deleted_{}'.format(prop)},
                                          UpdateExpression="set #v = :r, #t = :t, history = :h, #u = :u",
                                          ExpressionAttributeValues={':r': value, ':t': time, ':h': history, ':u': user},
                                          ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'},
                                          ConditionExpression='attribute_not_exists(#k)',
                                          ReturnValues="UPDATED_NEW")
                    else:
                        table.update_item(Key={'key': '_deleted_{}'.format(prop)},
                                          UpdateExpression="set #v = :r, #t = :t, #u = :u",
                                          ExpressionAttributeValues={':r': value, ':t': time, ':u': user},
                                          ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'},
                                          ConditionExpression='attribute_not_exists(#k)',
                                          ReturnValues="UPDATED_NEW")
                table.delete_item(Key={'key': prop})
                text = "Successfully deleted key *[%s]* in table *[%s]* for " \
                       "stack *[%s]* in *[%s][%s]*.."\
                       % (prop, db_table, stack, region, env)
                return self.slack_ui_standard_response(None, text)
            except:
                error_text = "Unable to delete key *[%s]* in table *[%s]*" \
                             " for stack *[%s]* in *[%s][%s]*..."\
                             % (prop, db_table, stack, region, env)
                return slack_ui_util.error_response(error_text)
        else:
            error_text = "Property *[%s]* will not be deleted from " \
                         "table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                         % (prop, db_table, stack, region, env)
            return slack_ui_util.error_response(error_text)

    def props_set(self, data, original_message_text=None):
        prop, value, db_table, stack, region, env, comment = \
            re.findall('\(([^)]+)', original_message_text)
            # re.findall('\(([^)]+)', data['original_message']['text'])

        print('SET VALUE PROPS:' + value)
        prop = url_checker(prop)
        value = url_checker(value)
        comment = url_checker(comment)
        session = aws_util.create_session(env)
        dynamodb = aws_util.get_dynamo_resource(session, region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                time = aws_util.get_prop_table_time_format()
                user = data['user']['name']
                if 'history' not in table.get_item(Key={'key': prop})['Item']:
                    history = []
                else:
                    history = table.get_item(Key={'key': prop})['Item']['history']
                    if len(history) == MAX_HISTORY_ITEMS:
                        del history[0]
                previous_value = {
                    'User': table.get_item(Key={'key': prop})['Item']['user']
                    if 'user' in table.get_item(Key={'key': prop})['Item'] else '-',
                    'Value': table.get_item(Key={'key': prop})['Item']['value'],
                    'Date': table.get_item(Key={'key': prop})['Item']['time']
                    if 'time' in table.get_item(Key={'key': prop})['Item'] else '-',
                    'Comment': table.get_item(Key={'key': prop})['Item']['comment']
                    if 'comment' in table.get_item(Key={'key': prop})['Item'] else '-'
                }
                history.append(previous_value)
                table.update_item(Key={'key': prop},
                                  UpdateExpression="set #v = :r, #t = :t, history = :p, #u = :u, #c = :c",
                                  ExpressionAttributeValues={':r': value, ':p': history, ':t': time, ':u': user, ':c': comment},
                                  ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user', '#c': 'comment'},
                                  ConditionExpression='attribute_exists(#k)',
                                  ReturnValues="UPDATED_NEW")
                text = "Successfully set property *[%s]* to value *[%s]* in " \
                       "table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                       % (prop, value, db_table, stack, region, env)
                return  self.slack_ui_standard_response(None, text)
            except:
                error_text = "Unable to set property *[%s]* to value *[%s]* in " \
                             "table *[%s]* for stack *[%s]* in *[%s][%s]*. That " \
                             "property may not exist. To create a new property, " \
                             "make sure to include the --create flag in your " \
                             "command..."\
                             % (prop, value, db_table, stack, region, env)
                return slack_ui_util.error_response(error_text)
        else:
            error_text = "Property *[%s]*'s value will not be set to *[%s]* for " \
                         "table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                         % (prop, value, db_table, stack, region, env)
            return slack_ui_util.error_response(error_text)

    def props_create(self, data, original_message_text=None):

        prop, value, db_table, stack, region, env, comment = \
            re.findall('\(([^)]+)', original_message_text)
            # re.findall('\(([^)]+)', data['original_message']['text'])
        prop = url_checker(prop)
        value = url_checker(value)
        comment = url_checker(comment)
        session = aws_util.create_session(env)
        dynamodb = aws_util.get_dynamo_resource(session, region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                delete_exists = table.get_item(Key={'key': '_deleted_{}'.format(prop)})
                if 'Item' in delete_exists:
                    table.delete_item(Key={'key': '_deleted_{}'.format(prop)})
                time = aws_util.get_prop_table_time_format()
                user = data['user']['name']
                table.update_item(Key={'key': prop},
                                  UpdateExpression="set #v = :r, #t = :t, #u = :u, #c = :c",
                                  ExpressionAttributeValues={':r': value, ':t': time, ':u': user, ':c': comment},
                                  ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user', '#c': 'comment'},
                                  ConditionExpression='attribute_not_exists(#k)',
                                  ReturnValues="UPDATED_NEW")
                text = "Successfully created property *[%s]* with value *[%s]* " \
                       "in table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                       % (prop, value, db_table, stack, region, env)
                return  self.slack_ui_standard_response(None, text)
            except:
                error_text = "Unable to create property *[%s]* with value *[%s]* " \
                             "in table *[%s]* for stack *[%s]* in *[%s][%s]*. " \
                             "That property may already exist..." \
                             % (prop, value, db_table, stack, region, env)
                return slack_ui_util.error_response(error_text)
        else:
            error_text = "Property *[%s]* will not be created for table *[%s]* " \
                         "for stack *[%s]* in *[%s][%s]*..."\
                         % (prop, db_table, stack, region, env)
            return slack_ui_util.error_response(error_text)

    def props_restore(self, data, original_message_text=None):

        prop, value, db_table, stack, region, env = \
            re.findall('\(([^)]+)', original_message_text)
            # re.findall('\(([^)]+)', data['original_message']['text'])
        prop = url_checker(prop)
        value = url_checker(value)
        session = aws_util.create_session(env)
        dynamodb = aws_util.get_dynamo_resource(session, region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                time = aws_util.get_prop_table_time_format()
                user = data['user']['name']
                response = table.get_item(Key={'key': '_deleted_{}'.format(prop)})
                value = response['Item']['value'] if 'value' in response['Item'] else '-'
                history = response['Item']['history'] if 'history' in response['Item'] else ''

                if history:
                    table.update_item(
                        Key={'key': prop},
                        UpdateExpression="set #v = :r, #t = :t, "
                                         "history = :h, #u = :u",
                        ExpressionAttributeValues={
                            ':r': value, ':t': time, ':h': history, ':u': user},
                        ExpressionAttributeNames={
                            '#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'
                        },
                        ConditionExpression='attribute_not_exists(#k)',
                        ReturnValues="UPDATED_NEW"
                    )
                else:
                    table.update_item(
                        Key={'key': prop},
                        UpdateExpression="set #v = :r, #t = :t, #u = :u",
                        ExpressionAttributeValues={
                            ':r': value, ':t': time, ':u': user},
                        ExpressionAttributeNames={
                            '#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'
                        },
                        ConditionExpression='attribute_not_exists(#k)',
                        ReturnValues="UPDATED_NEW"
                    )
                table.delete_item(Key={'key': '_deleted_{}'.format(prop)})

                text = "Successfully restored property *[%s]* with value *[%s]* " \
                       "in table *[%s]* for stack *[%s]* in *[%s][%s]*..." \
                       % (prop, value, db_table, stack, region, env)
                return self.slack_ui_standard_response(None, text)
            except:
                error_text = "Unable to restore property *[%s]* with value " \
                             "*[%s]* in table *[%s]* for stack *[%s]* in " \
                             "*[%s][%s]*. That property may already exist..."\
                             % (prop, value, db_table, stack, region, env)
                return slack_ui_util.error_response(error_text)
        else:
            error_text = "Property *[%s]* will not be created for table *[%s]* " \
                         "for stack *[%s]* in *[%s][%s]*..."\
                         % (prop, db_table, stack, region, env)
            return slack_ui_util.error_response(error_text)

    def props_copy_env(self, data, original_message_text=None):
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        from_table, from_service, from_region, from_env = re.findall('\(([^)]+)', original_message_text)
        # from_table, from_service, from_region, from_env = re.findall('\(([^)]+)', data['original_message']['text'])
        to_env = data['actions'][0]['value']
        if to_env == 'cancel':
            text = "Gotcha! The copy was canceled!"
            return slack_ui_util.error_response(text)
        service = services_table.get_item(Key={'serviceName': from_service})
        regions = [region for region in service['Item']['serviceInfo']['regions'][to_env]]
        if from_env == to_env:
            if from_region in regions:
                regions.remove(from_region)
        text = "Select the region in *(%s)* you would like to copy table *(%s)* of *(%s)* from *(%s)(%s)* to..."\
               % (to_env, from_table, from_service, from_region, from_env)
        session_id = self.store_original_message_text_in_session(text)
        fallback = CmdProps(None).set_fallback_value()
        print ('CmdProps... fallback value is: {}'.format(fallback))
        callback = 'callback_copy_CmdProps_select_region_' + session_id
        return slack_ui_util.prompt_regions(text, fallback, callback, regions, all_regions=False)

    def props_copy_region(self, data, original_message_text=None):
        dynamodb = boto3.resource('dynamodb')
        services_table = dynamodb.Table('ServiceInfo')
        to_env, from_table, from_service, from_region, from_env = \
            re.findall('\(([^)]+)', original_message_text)
            # re.findall('\(([^)]+)', data['original_message']['text'])
        to_region = data['actions'][0]['value']
        if to_region == 'cancel':
            text = "Gotcha! The copy was canceled!"
            return slack_ui_util.error_response(text)

        service = services_table.get_item(Key={'serviceName': from_service})
        stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']

        # Get info from CF
        session_src = aws_util.create_session(from_env)
        session_dest = aws_util.create_session(to_env)

        # Copy table from src to dest
        dynamodb_src = aws_util.get_dynamo_resource(session_src, from_region, client=True)
        dynamodb_dest = aws_util.get_dynamo_resource(session_dest, to_region, client=True)

        # Gather CF info for tables
        # try:
        props_table_src = bud_helper_util.get_props_table_name_for_stack_name(
            session_src, from_region, stack_name, from_service
        )
        props_table_dest = bud_helper_util.get_props_table_name_for_stack_name(
            session_dest, to_region, stack_name, from_service
        )
        # except:
        #     error_text = 'Unable to copy. Either the CF stack does not exist or there is a missing CF output.'
        #     return slack_ui_util.error_response(error_text)

        # Copy table from src to dest
        try:
            dynamo_paginator = dynamodb_src.get_paginator('scan')
            dynamo_response = dynamo_paginator.paginate(
                TableName=props_table_src,
                Select='ALL_ATTRIBUTES',
                ReturnConsumedCapacity='NONE',
                ConsistentRead=True
            )
            for page in dynamo_response:
                for item in page['Items']:
                    dynamodb_dest.put_item(
                        TableName=props_table_dest,
                        Item=item
                    )
            print('COPIED PROPS TABLE SUCCESSFULLY')
            text = 'The properties table of `%s` was successfully copied from `[%s][%s]` ' \
                   'to `[%s][%s]`.' % (from_service, from_region, from_env, to_region, to_env)
            return self.slack_ui_standard_response(None, text)
        except:
            error_text = 'The dynamodb tables of the src/dest may not exist.'
            return slack_ui_util.error_response(error_text)

def get_props_dynamo_table(session, arg_region, props_table, arg_service=''):
    """
    Get the dynanodb propertye table in a specific region, env for a service.
    :param session:
    :param arg_region:
    :param props_table:
    :param arg_service: optionally service name, for error messages.
    :return:
    """
    dynamodb = aws_util.get_dynamo_resource(session, arg_region)
    try:
        table = dynamodb.Table(props_table)
    except:
        error_text = "The service *[%s]* may not exist in *[ServiceInfo]*, " \
                     "or the properties table does not exist... " \
                     % arg_service
        raise ShowSlackError(error_text)
    return table

def props_line_separator():
    return '---------------------------------------------------' \
           '------------------------------------------------\n'


def url_checker(value):

    print('URL_CHECK_VALUE:' + value)
    if 'http' in value and '|' in value:
        value = value.split('|')[1][:-1]
    elif 'http' in value:
        lst = value.split('<')
        if len(lst) == 1 and not lst[0]:
            value = lst[0][:-1]
        elif len(lst) > 1:
            value = lst[1][:-1]

    return value

def props_list_table(tables):
    """List all the keys in property table(s) for a service."""
    results = {}
    all_items = []
    for region in tables:
        result = tables[region].scan()
        for item in result['Items']:
            if item['key'] not in all_items and not item['key'].startswith('_deleted_'):
                all_items.append(item['key'])
        results[region] = result
    output = props_line_separator()
    all_items.sort()
    sorted_regions = get_sorted_regions(results)
    for key in all_items:
        output += '*{}*\n'.format(key)
        # for region in results:
        for region in sorted_regions:
            output += '_{}_ : {}\n'.format(
                region,
                results[region]['Items'][map(itemgetter('key'),
                                             results[region]['Items']).index(key)]['value']
                if key in map(itemgetter('key'), results[region]['Items']) else '-')
        output += props_line_separator()
    return output


def get_sorted_regions(results):
    """Find the unique regions in a result and sort them."""
    sorted_regions = []
    for region in results:
        sorted_regions.append(region)
    sorted_regions.sort()
    return sorted_regions


# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_props_main():
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
