"""Methods for changing values in archaius property tables."""
from __future__ import print_function
import json
import re
from operator import itemgetter
import boto3
import util.aws_util as aws_util
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface

MAX_HISTORY_ITEMS = 15
AWS_REGIONS = aws_util.AWS_REGIONS


class CmdProps(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Gets the properties of the specified service"

    def get_help_text(self):
        help_text = "*Format:* _/bud props <action> -s <service>  " \
               "-e <environment> -r <region>_\n\n" \
               "*<list>* _Lists service properties of all " \
               "regions based on given environment_\nExample: _/bud props " \
               "list -s content -e dev_\n\n*<set>* _Sets a property to the " \
               "specified value. Add the *--create* flag to create a new " \
               "property_\nExample: _/bud props set maxRetries 3 -s content " \
               "-e dev -r us-east-1_\n\n*<get>* _Gets the value of a " \
               "specified property in all regions based on given " \
               "environments_\n" \
               "Example: _/bud props get maxRetries -s content -e dev_\n\n" \
               "*<history>* _Gets the value history of a specified property_" \
               "\nExample: _/bud props history maxRetries -s content -e dev " \
               "-r us-east-1_\n\n*<restore>* _Restores a specified property " \
               "if it was deleted_\nExample: _/bud props restore maxRetries " \
               "-s content -e dev -r us-east-1_\n\n*<delete>* _Deletes the specified " \
               "property from the table_\nExample: _/bud props delete maxRetries " \
               "-s content -e dev -r us-east-1_\n\n*<copy>* _Copies the specified " \
               "service properties table to another region/env_\n_NOTE : The destination " \
               "region/env must have a CF stack with its properties table listed as " \
               "an output. Also the environment and region must exist for the " \
               "service in the service_info.yaml file in GitLab_\nExample: " \
               "_/bud props copy -s content -e dev -r us-east-1_\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args, response_url):
        try:
            if sub_command == 'help':
                return self.get_help_text()

            if not args.envs or not args.services:
                return slack_ui_util.error_response(
                    'Please specify a service, environment, and region (-s, -e, -r)',
                    post=True,
                    response_url=response_url
                )

            slack_ui_util.loading_msg(response_url)

            # Get Session and Table as needed.
            dynamodb = boto3.resource('dynamodb')
            service_table = dynamodb.Table('ServiceInfo')
            service = service_table.get_item(Key={'serviceName': args.services[0]})
            try:
                session = aws_util.create_session(args.envs[0])
            except:
                return slack_ui_util.error_response(
                    'The environment *[%s]* does not exist for this service...' % args.envs[0],
                    post=True,
                    response_url=response_url)
            if args.regions[0] not in AWS_REGIONS:
                return slack_ui_util.error_response(
                    "The region *[%s]* does not exist for this service..." % args.regions[0],
                    post=True,
                    response_url=response_url)
            try:
                stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
                props_table = bud_helper_util.get_props_table_name_for_stack_name(
                    session, args.regions[0], stack_name, args.services[0]
                )
            except:
                error_text = "The service *[%s]* may not have a properties " \
                             "table in its CF output, or does not exist in *[serviceInfo]*..." % args.services[0]
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
            region_map = service['Item']['serviceInfo']['regions']
            regions = [region for region in region_map[args.envs[0]]]
            dynamodb = aws_util.get_dynamo_resource(session, args.regions[0])

            try:
                table = dynamodb.Table(props_table)
            except:
                error_text = "The service *[%s]* may not exist in *[ServiceInfo]*, " \
                             "or the properties table does not exist... " \
                             % args.services[0]
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

            if sub_command == 'list':
                return handle_list_sub_command(dynamodb, props_table, args, service, regions, session, response_url)
            if sub_command == 'history':
                return handle_history_sub_command(table, props_table, args, response_url)
            if sub_command == 'get':
                return handle_get_sub_command(args, service, regions, session, response_url)
            if sub_command == 'set':
                return handle_set_sub_command(table, args, props_table)
            if sub_command == 'delete':
                return handle_delete_sub_command(table, args, props_table, response_url)
            if sub_command == 'restore':
                return handle_restore_sub_command(table, args, props_table, response_url)
            if sub_command == 'copy':
                return handle_copy_sub_command(table, args, props_table, region_map, response_url)

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def invoke_confirm_command(self, params):
        return props_confirm(params)

    def is_confirm_command(self, params):
        if self.get_fallback_string_from_payload(params) == self.__class__.__name__:
            return True
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


def props_line_separator():
    return '---------------------------------------------------' \
           '------------------------------------------------\n'


def url_checker(value):

    if 'http' in value and '|' in value:
        value = value.split('|')[1][:-1]
    elif 'http' in value:
        value = value.split('<')[1][:-1]

    return value


def handle_list_sub_command(dynamodb, props_table, args, service, regions, session, response_url):
    try:
        table = dynamodb.Table(props_table)
    except:
        error_text = "The service *[%s]* may not exist in *[ServiceInfo]*, " \
                     "or the properties table does not exist... "\
                     % args.services[0]
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

    if args.command[1] == 'list':
        # try:
        tables = {}
        stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
        for region in regions:
            props_table = bud_helper_util.get_props_table_name_for_stack_name(
                session, region, stack_name, args.services[0]
            )
            dynamodb = aws_util.get_dynamo_resource(session, region)
            table = dynamodb.Table(props_table)
            tables[region] = table

        return slack_ui_util.text_command_response(
            title="Here are the properties of service *[%s]* for *[%s]* for every region...\n" % (
                args.services[0], args.envs[0]),
            text=props_list_table(tables),
            color="#d77aff",
        )


def handle_history_sub_command(table, props_table, args, response_url):
    args.command[2] = url_checker(args.command[2])
    item = table.get_item(
        Key={'key': args.command[2]}
    )
    deleted_item = table.get_item(
        Key={'key': '_deleted_{}'.format(args.command[2])}
    )
    if 'Item' in item:
        try:
            title = "History of property *[%s]* in table *[%s]* for " \
                    "stack *[%s]* in *[%s][%s]*..." \
                    % (args.command[2],
                       props_table,
                       args.services[0], args.regions[0], args.envs[0])
            text = "%s" % props_history(table, args.command[2])
            return slack_ui_util.text_command_response(title, text)
        except:
            error_text = "Unable to gather history for property " \
                         "*[%s]* of table *[%s]* for stack " \
                         "*[%s]* in *[%s][%s]*. This property " \
                         "may have never existed..." \
                         % (args.command[2],
                            props_table,
                            args.services[0],
                            args.regions[0],
                            args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    elif 'Item' in deleted_item:
        try:
            title = "History of property *[%s]* in table *[%s]* for " \
                    "stack *[%s]* in *[%s][%s]*..." \
                    % (args.command[2],
                       props_table,
                       args.services[0],
                       args.regions[0],
                       args.envs[0])
            text = "%s" % props_history(
                table, '_deleted_{}'.format(args.command[2])
            )
            return slack_ui_util.text_command_response(title, text)
        except:
            error_text = "Unable to gather history for property *[%s]* " \
                         "of table *[%s]* for stack *[%s]* in " \
                         "*[%s][%s]*. There may be no history of this " \
                         "property..." \
                         % (args.command[2],
                            props_table,
                            args.services[0],
                            args.regions[0],
                            args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    else:
        error_text = "Unable to gather history for property *[%s]* of " \
                     "table *[%s]* for stack *[%s]* in *[%s][%s]*. " \
                     "The property may have never existed..." \
                     % (args.command[2],
                        props_table,
                        args.services[0],
                        args.regions[0],
                        args.envs[0])
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)


def handle_get_sub_command(args, service, regions, session, response_url):
    prop_exists = False
    output = ''

    if len(args.command) == 2:
        error_text = "Please specify which property value to get for stack " \
                     "*[%s]* in *[%s][%s]*. " \
                     % (args.services[0], args.envs[0], args.regions[0])
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

    # Gathers regions from ServiceNames table
    stack_name = service['Item']['serviceInfo']['properties_table']['stack_name']
    for region in regions:
        props_table = bud_helper_util.get_props_table_name_for_stack_name(
            session, region, stack_name, args.services[0]
        )
        dynamodb = aws_util.get_dynamo_resource(session, region)
        table = dynamodb.Table(props_table)
        response = table.get_item(Key={'key': args.command[2]})
        if 'Item' in response:
            output += '_{}_ : {}\n'.format(region, response['Item']['value'])
            prop_exists = True
        else:
            output += '_{}_ : {}\n'.format(region, '-')

    if prop_exists:
        return slack_ui_util.text_command_response(
            title="Here is the value of property *[%s]* for *[%s]* in all regions...\n"
                  % (args.command[2], args.envs[0]),
            text=output,
            color="#d77aff"
        )
    else:
        error_text = "Unable to get value of property *[%s]* for stack " \
                     "*[%s]* in *[%s]*. The property may not exist in " \
                     "any regions..." \
                     % (args.command[2], args.services[0], args.envs[0])
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)


def handle_set_sub_command(table, args, props_table):
    args.command[2] = url_checker(args.command[2])
    args.command[3] = url_checker(args.command[3])
    deleted_prop = table.get_item(
        Key={'key': '_deleted_{}'.format(args.command[2])}
    )
    if not args.create:
        text = "Are you sure you want to set property *(%s)* to value *(%s)*" \
               ", from table *(%s)* for stack *(%s)* in *(%s)(%s)*?" \
               % (args.command[2], args.command[3],
                  props_table,
                  args.services[0], args.regions[0], args.envs[0])
        fallback = CmdProps().set_fallback_value()
        callback_id = "confirm_set"
        return slack_ui_util.ask_for_confirmation_response(
            text, fallback, callback_id
        )
    else:
        if 'Item' in deleted_prop:
            fallback = CmdProps().set_fallback_value()
            callback_id = "confirm_create"

            text = "This property used to exist and can be restored via " \
                   "the restore command. Are you sure you want to " \
                   "continue creating property *(%s)* with value *(%s)*, " \
                   "for table *(%s)* of stack *(%s)* in *(%s)(%s)*?" \
                   % (args.command[2], args.command[3],
                      props_table,
                      args.services[0], args.regions[0], args.envs[0])

            return slack_ui_util.ask_for_confirmation_response(
                text, fallback, callback_id
            )

        fallback = CmdProps().set_fallback_value()
        callback_id = "confirm_create"
        text = "Are you sure you want to create property *(%s)* with" \
               " value *(%s)*, for table *(%s)* of stack *(%s)* in *(%s)(%s)*?" \
               % (args.command[2], args.command[3],
                  props_table,
                  args.services[0], args.regions[0], args.envs[0])

        return slack_ui_util.ask_for_confirmation_response(
            text, fallback, callback_id
        )


def handle_delete_sub_command(table, args, props_table, response_url):
        args.command[2] = url_checker(args.command[2])
        response = table.get_item(Key={'key': args.command[2]})
        if 'Item' not in response:
            error_text = "Key *[%s]* does not exist in table *[%s]* for " \
                         "stack *[%s]* in *[%s][%s]*..." \
                         % (args.command[2],
                            props_table,
                            args.services[0],
                            args.regions[0],
                            args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
        fallback = CmdProps().set_fallback_value()
        callback_id = "confirm_delete"
        text = "Are you sure you want to delete *(%s)* from table *(%s)* for" \
               " stack *(%s)* in *(%s)(%s)*?"\
               % (args.command[2], props_table,
                  args.services[0], args.regions[0], args.envs[0])
        return slack_ui_util.ask_for_confirmation_response(
            text, fallback, callback_id, danger_style=True
        )


def handle_restore_sub_command(table, args, props_table, response_url):
    args.command[2] = url_checker(args.command[2])
    deleted_prop = table.get_item(
        Key={'key': '_deleted_{}'.format(args.command[2])}
    )
    if 'Item' not in deleted_prop:
        error_text = "Property *[%s]* from table *[%s]* for stack *[%s]*" \
                     " in *[%s][%s]* cannot be restored... The property " \
                     "may already exist, or no history exists for it." \
                     % (args.command[2],
                        props_table,
                        args.services[0], args.regions[0], args.envs[0])
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    fallback = CmdProps().set_fallback_value()
    callback_id = "confirm_restore"
    text = "Are you sure you want to restore property *(%s)* with value " \
           "*(%s)* for table *(%s)* for stack *(%s)* in *(%s)(%s)*?" \
           % (args.command[2], deleted_prop['Item']['value'],
              props_table,
              args.services[0], args.regions[0], args.envs[0])

    return slack_ui_util.ask_for_confirmation_response(
        text, fallback, callback_id
    )


def handle_copy_sub_command(table, args, props_table, region_map, response_url):
    result = table.scan()
    if 'Items' not in result:
        error_text = 'The properties table *[%s]* is empty in *[%s][%s]* or does not exist...' \
                     % (props_table, args.regions[0], args.envs[0])
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    text = 'Select the environment you would like to copy table *(%s)* of *(%s)* from *(%s)(%s)* to...' \
           % (props_table, args.services[0], args.regions[0], args.envs[0])
    fallback = CmdProps().set_fallback_value()
    callback_id = 'select_copy_env'
    return slack_ui_util.prompt_envs(
        text, fallback, callback_id, region_map, dev_and_qa=False)

##
# End of sub command section.
##
##
# Start of helper functions
##


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


def props_history(table, key):
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


def props_delete(data):
    """Delete properties."""

    prop, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
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
            return slack_ui_util.text_command_response(None, text)
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


def props_set(data):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    print('SET VALUE PROPS:' + value)
    prop = url_checker(prop)
    value = url_checker(value)
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
                if 'time' in table.get_item(Key={'key': prop})['Item'] else '-'
            }
            history.append(previous_value)
            table.update_item(Key={'key': prop},
                              UpdateExpression="set #v = :r, #t = :t, history = :p, #u = :u",
                              ExpressionAttributeValues={':r': value, ':p': history, ':t': time, ':u': user},
                              ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'},
                              ConditionExpression='attribute_exists(#k)',
                              ReturnValues="UPDATED_NEW")
            text = "Successfully set property *[%s]* to value *[%s]* in " \
                   "table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                   % (prop, value, db_table, stack, region, env)
            return slack_ui_util.text_command_response(None, text)
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


def props_create(data):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    prop = url_checker(prop)
    value = url_checker(value)
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
                              UpdateExpression="set #v = :r, #t = :t, #u = :u",
                              ExpressionAttributeValues={':r': value, ':t': time, ':u': user},
                              ExpressionAttributeNames={'#v': 'value', '#k': 'key', '#t': 'time', '#u': 'user'},
                              ConditionExpression='attribute_not_exists(#k)',
                              ReturnValues="UPDATED_NEW")
            text = "Successfully created property *[%s]* with value *[%s]* " \
                   "in table *[%s]* for stack *[%s]* in *[%s][%s]*..."\
                   % (prop, value, db_table, stack, region, env)
            return slack_ui_util.text_command_response(None, text)
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


def props_restore(data):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
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
            return slack_ui_util.text_command_response(None, text)
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


def props_copy_env(data):
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    from_table, from_service, from_region, from_env = re.findall('\(([^)]+)', data['original_message']['text'])
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
    fallback = CmdProps().set_fallback_value()
    print ('CmdProps... fallback value is: {}'.format(fallback))
    callback = 'select_copy_region'
    return slack_ui_util.prompt_regions(text, fallback, callback, regions, all_regions=False)


def props_copy_region(data):
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table('ServiceInfo')
    to_env, from_table, from_service, from_region, from_env = \
        re.findall('\(([^)]+)', data['original_message']['text'])
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
        text = 'The properties table of `%s` was successfully copied from `[%s][%s]` ' \
               'to `[%s][%s]`.' % (from_service, from_region, from_env, to_region, to_env)
        return slack_ui_util.text_command_response(None, text)
    except:
        error_text = 'The dynamodb tables of the src/dest may not exist.'
        return slack_ui_util.error_response(error_text)


def props_confirm(body):
    data = json.loads(body['payload'][0])

    if data['callback_id'] == 'confirm_delete':
        return props_delete(data)
    if data['callback_id'] == 'confirm_set':
        return props_set(data)
    if data['callback_id'] == 'confirm_create':
        return props_create(data)
    if data['callback_id'] == 'confirm_restore':
        return props_restore(data)
    if data['callback_id'] == 'select_copy_env':
        return props_copy_env(data)
    if data['callback_id'] == 'select_copy_region':
        return props_copy_region(data)
