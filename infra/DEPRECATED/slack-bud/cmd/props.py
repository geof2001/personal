"""Methods for changing values in archaius property tables."""
import json
import re
from operator import itemgetter
import boto3
import aws_util
import slack_ui_util
import bud_helper_util

MAX_HISTORY_ITEMS = 15
AWS_REGIONS = bud_helper_util.AWS_REGIONS
ENVIRONMENTS = bud_helper_util.ENVIRONMENTS


def props_line_separator():
    return '---------------------------------------------------' \
           '------------------------------------------------\n'


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


def props_delete(data, environments):
    """Delete properties."""

    prop, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    session = aws_util.get_session(environments, env)
    dynamodb = aws_util.get_dynamo_resource(session, region)
    table = dynamodb.Table(db_table)
    if data['actions'][0]['value'] == 'yes':
        try:
            if not prop.startswith('_deleted_'):
                response = table.get_item(Key={'key': prop})
                value = response['Item']['value'] if 'value' in response['Item'] else ''
                time = response['Item']['time'] if 'time' in response['Item'] else ''
                history = response['Item']['history'] if 'history' in response['Item'] else ''
                user = response['Item']['user'] if 'user' in response['Item'] else ''

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


def props_set(data, environments):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    session = aws_util.get_session(environments, env)
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


def props_create(data, environments):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    session = aws_util.get_session(environments, env)
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


def props_restore(data, environments):

    prop, value, db_table, stack, region, env =\
        re.findall('\(([^)]+)', data['original_message']['text'])
    session = aws_util.get_session(environments, env)
    dynamodb = aws_util.get_dynamo_resource(session, region)
    table = dynamodb.Table(db_table)
    if data['actions'][0]['value'] == 'yes':
        try:
            time = aws_util.get_prop_table_time_format()
            user = data['user']['name']
            response = table.get_item(Key={'key': '_deleted_{}'.format(prop)})
            value = response['Item']['value'] if 'value' in response['Item'] else ''
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
    text = "Select the region in *(%s)* you would like to copy table *(%s)* of *(%s)* from *(%s)(%s)* to..."\
           % (to_env, from_table, from_service, from_region, from_env)
    fallback = 'Properties'
    callback = 'select_copy_region'
    return slack_ui_util.prompt_regions(text, fallback, callback, regions)


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
    session_src = aws_util.get_session(ENVIRONMENTS, from_env)
    session_dest = aws_util.get_session(ENVIRONMENTS, to_env)

    # Copy table from src to dest
    dynamodb_src = aws_util.get_dynamo_resource(session_src, from_region, client=True)
    dynamodb_dest = aws_util.get_dynamo_resource(session_dest, to_region, client=True)

    # Gather CF info for tables
    try:
        props_table_src = bud_helper_util.get_props_table_name_for_stack_name(
            session_src, from_region, stack_name, from_service
        )
        props_table_dest = bud_helper_util.get_props_table_name_for_stack_name(
            session_dest, to_region, stack_name, from_service
        )
    except:
        error_text = 'Unable to copy. Either the CF stack does not exist or there is a missing CF output.'
        return slack_ui_util.error_response(error_text)

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
    except:
        error_text = 'The dynamodb tables of the src/dest may not exist.'
        return slack_ui_util.error_response(error_text)


def props_confirm(body, environments):
    data = json.loads(body['payload'][0])

    if data['callback_id'] == 'confirm_delete':
        return props_delete(data, environments)
    if data['callback_id'] == 'confirm_set':
        return props_set(data, environments)
    if data['callback_id'] == 'confirm_create':
        return props_create(data, environments)
    if data['callback_id'] == 'confirm_restore':
        return props_restore(data, environments)
    if data['callback_id'] == 'select_copy_env':
        return props_copy_env(data)
    if data['callback_id'] == 'select_copy_region':
        return props_copy_region(data)


def handle_props(command, environments, args, response_url):
    if 'help' in command.strip():
        title = "Gets the properties of the specified service."
        text = "*Format:* _/bud props <action> -s <service>  " \
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
               "-s content -e dev -r us-east-1_\n\n"
        return slack_ui_util.text_command_response(
            title, text, "#00b2ff"
        )
    if not args.envs or not args.services:
        return slack_ui_util.error_response(
            'Please specify a service, environment, and region (-s, -e, -r)',
            post=True,
            response_url=response_url
        )

    slack_ui_util.loading_msg(response_url)
    dynamodb = boto3.resource('dynamodb')
    service_table = dynamodb.Table('ServiceInfo')
    service = service_table.get_item(Key={'serviceName': args.services[0]})
    try:
        session = aws_util.get_session(environments, args.envs[0])
    except:
        return slack_ui_util.error_response('The environment *[%s]* does not exist for this service...' % args.envs[0],
                                            post=True,
                                            response_url=response_url)
    if args.regions[0] not in AWS_REGIONS:
        return slack_ui_util.error_response("The region *[%s]* does not exist for this service..." % args.regions[0],
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
        # except:
        #     error_text = "Unable to list properties of service *[%s]* " \
        #                  "in *[%s]*. Ensure correctness of CF output and regions of ServiceInfo...\n"\
        #                  % (args.services[0], args.envs[0])
        #     return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    elif args.command[1] == 'history':
        item = table.get_item(
            Key={'key': args.command[2]}
        )
        deleted_item = table.get_item(
            Key={'key': '_deleted_{}'.format(args.command[2])}
        )
        if 'Item' in item:
            try:
                title = "History of property *[%s]* in table *[%s]* for " \
                        "stack *[%s]* in *[%s][%s]*..."\
                        % (args.command[2],
                           props_table,
                           args.services[0], args.regions[0], args.envs[0])
                text = "%s" % props_history(table, args.command[2])
                return slack_ui_util.text_command_response(title, text)
            except:
                error_text = "Unable to gather history for property " \
                             "*[%s]* of table *[%s]* for stack " \
                             "*[%s]* in *[%s][%s]*. This property " \
                             "may have never existed..."\
                             % (args.command[2],
                                props_table,
                                args.services[0],
                                args.regions[0],
                                args.envs[0])
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
        elif 'Item' in deleted_item:
            try:
                title = "History of property *[%s]* in table *[%s]* for " \
                        "stack *[%s]* in *[%s][%s]*..."\
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
                             "property..."\
                             % (args.command[2],
                                props_table,
                                args.services[0],
                                args.regions[0],
                                args.envs[0])
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
        else:
            error_text = "Unable to gather history for property *[%s]* of " \
                         "table *[%s]* for stack *[%s]* in *[%s][%s]*. " \
                         "The property may have never existed..."\
                         % (args.command[2],
                            props_table,
                            args.services[0],
                            args.regions[0],
                            args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
    elif args.command[1] == 'get':
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
                         "any regions..."\
                         % (args.command[2], args.services[0], args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

    elif args.command[1] == 'set':
        deleted_prop = table.get_item(
            Key={'key': '_deleted_{}'.format(args.command[2])}
        )
        if not args.create:
            text = "Are you sure you want to set property *(%s)* to value *(%s)*" \
                   ", from table *(%s)* for stack *(%s)* in *(%s)(%s)*?" \
                   % (args.command[2], args.command[3],
                      props_table,
                      args.services[0], args.regions[0], args.envs[0])
            fallback = "Properties"
            callback_id = "confirm_set"
            return slack_ui_util.ask_for_confirmation_response(
                text, fallback, callback_id
            )
        else:
            if 'Item' in deleted_prop:
                fallback = "Properties"
                callback_id = "confirm_create"

                text = "This property used to exist and can be restored via " \
                       "the restore command. Are you sure you want to " \
                       "continue creating property *(%s)* with value *(%s)*, " \
                       "for table *(%s)* of stack *(%s)* in *(%s)(%s)*?"\
                       % (args.command[2], args.command[3],
                          props_table,
                          args.services[0], args.regions[0], args.envs[0])

                return slack_ui_util.ask_for_confirmation_response(
                    text, fallback, callback_id
                )

            fallback = "Properties"
            callback_id = "confirm_create"
            text = "Are you sure you want to create property *(%s)* with" \
                   " value *(%s)*, for table *(%s)* of stack *(%s)* in *(%s)(%s)*?" \
                   % (args.command[2], args.command[3],
                      props_table,
                      args.services[0], args.regions[0], args.envs[0])

            return slack_ui_util.ask_for_confirmation_response(
                text, fallback, callback_id
            )

    elif args.command[1] == 'delete':
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
        fallback = "Properties"
        callback_id = "confirm_delete"
        text = "Are you sure you want to delete *(%s)* from table *(%s)* for" \
               " stack *(%s)* in *(%s)(%s)*?"\
               % (args.command[2], props_table,
                  args.services[0], args.regions[0], args.envs[0])
        return slack_ui_util.ask_for_confirmation_response(
            text, fallback, callback_id, danger_style=True
        )
    elif args.command[1] == 'restore':
        deleted_prop = table.get_item(
            Key={'key': '_deleted_{}'.format(args.command[2])}
        )
        if 'Item' not in deleted_prop:
            error_text = "Property *[%s]* from table *[%s]* for stack *[%s]*" \
                         " in *[%s][%s]* cannot be restored... The property " \
                         "may already exist, or no history exists for it."\
                         % (args.command[2],
                            props_table,
                            args.services[0], args.regions[0], args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
        fallback = "Properties"
        callback_id = "confirm_restore"
        text = "Are you sure you want to restore property *(%s)* with value " \
               "*(%s)* for table *(%s)* for stack *(%s)* in *(%s)(%s)*?"\
               % (args.command[2], deleted_prop['Item']['value'],
                  props_table,
                  args.services[0], args.regions[0], args.envs[0])

        return slack_ui_util.ask_for_confirmation_response(
            text, fallback, callback_id
        )
    elif args.command[1] == 'copy':
        result = table.scan()
        if 'Items' not in result:
            error_text = 'The properties table *[%s]* is empty in *[%s][%s]* or does not exist...' \
                         % (props_table, args.regions[0], args.envs[0])
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
        text = 'Select the environment you would like to copy table *(%s)* of *(%s)* from *(%s)(%s)* to...'\
               % (props_table, args.services[0], args.regions[0], args.envs[0])
        fallback = 'Properties'
        callback_id = 'select_copy_env'
        return slack_ui_util.prompt_envs(
            text, fallback, callback_id, all_envs=True)
    else:
        error_text = "Invalid command..."
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
