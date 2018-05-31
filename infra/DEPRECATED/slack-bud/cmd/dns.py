"""Methods for slack-bud DNS commands."""
from __future__ import print_function

import json
import decimal
import re
import boto3
from boto3.dynamodb.conditions import Attr
import slack_ui_util
from slack_ui_util import ShowSlackError


# Generate Slack response with title and text
def slack_ui_text_command_response(title, text, color="#a0ffaa"):
    # """Migrating to slack_ui_util.py"""
    return slack_ui_util.text_command_response(title, text, color)


# Generate Slack response asking for confirmation
def slack_ui_ask_for_confirmation_response(text):
    """Slack UI response when needing a confirmation."""
    return slack_ui_util.ask_for_confirmation_response(
        text, "DNS", "confirm_dns_set"
    )


# Generate a response to an exception
def slack_error_response(text):
    """Slack UI response for errors."""
    return slack_ui_util.error_response(text)


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    """For decoding decimals in Python dictionaries."""
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def scan_state_table_for_env(env):
    """Scan state table for entries from environment"""
    dynamodb = boto3.resource('dynamodb')
    state_table = dynamodb.Table('MultiregionServiceDnsState')
    # Query for key that start with environment. like "dev:"
    results = state_table.scan(
        FilterExpression=Attr('key').begins_with(env)
    )

    # Parse the result looking for service names.
    print('scan results')
    print(results)
    return results


def handle_dns(command, environments, args, params):
    """Entry point for all DNS calls to lambda function."""
    try:
        print("handle_dns() Command and args ...")
        print(command)
        print(args)
        print("params ...")
        print(params)

        if 'help' in command.strip():
            return handle_dns_help_command()

        if args.command[1] == 'service':
            return handle_dns_service_command(args)

        if args.command[1] == 'status':
            return handle_dns_status_command(args)

        if args.command[1] == 'set':
            return handle_dns_set_command(args, params)

        # This section is for new command set.
        if args.command[1] == 'a':
            return handle_dns_a_service_command(args)

        if args.command[1] == 'b':
            return handle_dns_b_status_command(args)

        if args.command[1] == 'c':
            return handle_dns_c_set_command(args, params)

        return invalid_command_response()
    except ShowSlackError as slack_error_message:
        print(type(slack_error_message))
        print(slack_error_message.args)
        print(slack_error_message)

        return slack_error_response(slack_error_message)


def invalid_command_response():
    """Response to an invalid command."""
    return slack_ui_text_command_response(
        "Invalid Command", invalid_command_text(), "#ff0000"
    )


# Handle the services command
def handle_dns_service_command(args):
    """Handle the DNS service ... command."""
    env = args.envs[0]
    print('dns service env=%s' % env)
    text_response = do_dns_service(env)
    return slack_ui_text_command_response("DNS Service Command", text_response)


# Handle the status command
def handle_dns_status_command(args):
    """Handle the DNS status ... command."""
    env = args.envs[0]
    service = args.services[0]
    print('dns status env=%s service=%s' % (env, service))
    response_text = do_dns_status(env, service)
    return slack_ui_text_command_response(
        "DNS Status Command", response_text
    )


# Handle the set command
def handle_dns_set_command(args, params):
    """Handle the DNS set command when not confirmed version."""
    setting = args.command[2]
    env = args.envs[0]
    service = args.services[0]
    region = args.regions[0]
    print('dns set %s env=%s service=%s region=%s' %
          (setting, env, service, region))
    if not check_for_is_dns_set_confirmed(params):
        return do_dns_set_before_confirm(setting, env, service, region)
    else:
        raise ShowSlackError(
            'Invalid PATH....  confirmed handle_dns_set_command()'
        )


def check_for_is_dns_set_confirmed(params):
    """Is this the DNS SET confirmation?"""
    if 'payload' in params:
        return True
    return False


def do_dns_set_before_confirm(setting, env, service, region):
    """Send the confirmation for DNS SET if command is valid"""
    return slack_ui_ask_for_confirmation_response(
        'Are you sure you want to change (%s) in (%s) to (%s) for (%s)'
        % (service, region, setting, env)
    )


def not_modified_message():
    """Return message about not making the change"""
    text = "We are *NOT* making any change."
    return text


# Handle the help command
def handle_dns_help_command():
    """DNS help command."""
    return slack_ui_text_command_response(
        "DNS Help command", help_text(), "#00b2ff"
    )


def invalid_command_text():
    """Text to display for invalid dns commands."""
    ret = "*Invalid Command*\n"
    ret += "*Use:* _/bud dns help_\n\n"
    return ret


def help_text():
    """Text for help command."""
    ret = "*Format:* _/bud dns <action>  -e <env> -s <service> -r <region>_\n"
    ret += "*Example:* _/bud dns status -e dev -s dns-demo_\n\n"
    ret += "*<service>* _Gets information for a service_\n"
    ret += "*<status>* _DNS status of multi-region service_\n"
    ret += "*<set>* _Change DNS setting for a service_\n"
    return ret


# Call the database to get list of all services
def do_dns_service(env):
    """Deals with the dns service command."""
    print('do_dns_service(%s)' % env)
    try:
        scan_items = scan_state_table_for_env(env)
        ret = '    Service name\n'
        for i in scan_items['Items']:
            print(i['key'], ":", i['value'])
            curr_value = i['value']
            service_name = curr_value.split(':')[0]
            if service_name not in ret:
                ret += '    %s\n' % service_name
        return ret
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        raise ShowSlackError('An error occurred. Check logs.')


def do_dsn_set(setting, env, service, region, confirm_data):
    """Deals with the slack-bud set command."""
    print('do_dsn_set(%s, %s, %s, %s)' % (setting, env, service, region))

    # Determine if YES/NO clicked and return appropriate value.
    try:
        # Was YES pressed?
        if confirm_data['actions'][0]['value'] == 'yes':
            scan_items = scan_state_table_for_env(env)
            found_row = verify_row_exists(scan_items, env, service, region)
            if not found_row:
                # Return error if it isn't there
                raise ShowSlackError(
                    "Failed to find: env: %s service: *%s* in *%s*"
                    % (env, service, region)
                )
            # Ask user for confirmation of change
            return "Change setting success. env: %s service: *%s* in *%s*"\
                   % (env, service, region)
        else:
            # NO was pressed.
            return not_modified_message()

    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        raise ShowSlackError('An error occurred. Check logs.')


def dns_confirm(params, ENVIRONMENTS):
    """Verify YES/NO response from user and create the change."""
    print('dns_confirm() params:')
    print(params)
    try:
        data = json.loads(params['payload'][0])
        print("data...")
        print(data)
        callback_id = data['callback_id']
        print('callback_id=%s' % callback_id)
        if 'confirm_dns_set' in callback_id:
            # Was YES pressed?
            service, region, setting, env = \
                re.findall('\(([^)]+)', data['original_message']['text'])
            print('service: %s, region: %s, setting: %s, env: %s'
                  % (service, region, setting, env))
            if data['actions'][0]['value'] == 'yes':
                print('dns_confirm() YES pressed')
                scan_items = scan_state_table_for_env(env)
                found_row = verify_row_exists(scan_items, env, service, region)
                if not found_row:
                    # Return error if it isn't there
                    raise ShowSlackError(
                        "Failed to find: env: %s service: *%s* in *%s*"
                        % (env, service, region)
                    )
                else:
                    text = change_dns_state(
                        service, region, setting, env, scan_items
                    )
                    return slack_ui_text_command_response("DNS Set", text)
            else:
                print('dns_confirm() NO pressed')
                # NO was pressed.
                return slack_ui_text_command_response(
                    "DNS Set", not_modified_message()
                )
        else:
            print(
                'ERROR. Unknown confirm value. '
                'Expected: confirm_dns_set Was: %s'
                % callback_id
            )
            return slack_error_response('An error occurred. Check logs.')
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        return slack_error_response('An error occurred. Check logs.')


def change_dns_state(service, region, setting, env, scan_items):
    """Change the DNS state for specific service."""
    print(
        "change_dns_state() service: %s region: %s setting: %s env: %s"
        % (service, region, setting, env))
    # Find key for specific row.
    for i in scan_items['Items']:
        curr_key = i['key']
        curr_value = i['value']
        if service in curr_value and region in curr_key and env in curr_key:
            # change this row.
            new_value = '%s:%s' % (service, setting)
            # Send warning if the new value is the same as the old value.
            if new_value == curr_value:
                raise ShowSlackError(
                    "No change detected for %s in %s for %s. Both: %s"
                    % (service, region, env, setting)
                )
            # Make the change
            dynamodb = boto3.resource('dynamodb')
            state_table = dynamodb.Table('MultiregionServiceDnsState')
            response = state_table.put_item(
                Item={
                    'key': curr_key,
                    'value': new_value
                }
            )
            print('PutItem succeeded:')
            print(json.dumps(response, indent=2, cls=DecimalEncoder))
            return "Change setting success. env: %s service: *%s* in *%s*" \
                % (env, service, region)
        else:
            print('skipping key=%s' % curr_key)

    raise ShowSlackError('Failed to find key for service: %s region: %s'
                         % (service, region))


def verify_row_exists(scan_items, env, service, region):
    """Verify this row exists."""
    for i in scan_items['Items']:
        curr_key = i['key']
        curr_value = i['value']
        if service in curr_value and region in curr_key and env in curr_key:
            return True
    return False


def verify_service_is_multiregion(scan_items, env, service):
    """Return TRUE if the service is multi-region"""
    row_count = 0
    for i in scan_items['Items']:
        curr_key = i['key']
        curr_value = i['value']
        if service in curr_value and env in curr_key:
            row_count += 1
        if row_count > 1:
            return True
    return False


# Handle the dns status command
def do_dns_status(env, service):
    """Deals with the slack-bud dns status command."""
    print('do_dns_status(%s, %s)' % (env, service))
    scan_items = scan_state_table_for_env(env)
    is_multiregion_service = \
        verify_service_is_multiregion(scan_items, env, service)
    if not is_multiregion_service:
        # Let user know this doesn't seem to be a multi-region service
        raise ShowSlackError(
            "Service: *%s* doesn't seem to be multiregion in *%s*"
            % (service, env)
        )

    try:
        ret = '    Service: %s\n' % service
        for i in scan_items['Items']:
            print(i['key'], ":", i['value'])
            curr_value = i['value']
            service_name = curr_value.split(':')[0]
            if service_name in service:
                status_line = make_status_line(i['key'], i['value'])
                status_line += append_update_to_status(i['key'])
                ret += '    %s\n' % status_line
        return ret
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        raise ShowSlackError('An error occurred. Check logs.')


def make_status_line(key, value):
    """Make output like:  us-west-2 ON"""
    on_off = value.split(':')[1]
    region_parts = key.split('-')
    num_parts = len(region_parts)
    r3 = region_parts[num_parts-1]
    r2 = region_parts[num_parts-2]
    r1 = region_parts[num_parts-3]
    region = "region: %s-%s-%s" % (r1, r2, r3)
    print("region: %s" % region)
    return "%s %s" % (region, on_off.upper())


def append_update_to_status(key):
    """Look up update attribute in the dynamo table and add it if there."""
    ret = ''
    try:
        client = boto3.client('dynamodb')

    except Exception as e:
        print('ERROR in append_update_to_status(): key=%s' % key)
        print(e)
    return ret

# Command list
# /bud2 dns help
#    Gives standard help like this
#
# /bud2 dns status -e dev
#    Gives a list of services like:   dns-demo
#
# /bud2 dns status -e dev -s <service-name>
#    Gives a list of locations like:    us-east-1(*), us-west-2(*)
#
# /bud2 dns set <target-alias> -e dev -s <service-name> -r <region>
#    Makes the specified change to a service.

#  Example:  EPGREG
#       target-alias:   api2-us-west-2   (NOTE: region is part of target-alias)
#       service-name:   epgreg
#


def handle_dns_a_service_command(args):
    """The service command entry point"""
    env = args.envs[0]
    print('dns service env=%s' % env)
    text_response = do_dns_service_v2(env)
    return slack_ui_text_command_response("DNS Service Command", text_response)


def handle_dns_b_status_command(args):
    """The status command entry point"""
    env = args.envs[0]
    service = args.services[0]
    print('dns status env=%s service=%s' % (env, service))
    response_text = do_dns_status_v2(env, service)
    return slack_ui_text_command_response(
        "DNS Status Command", response_text
    )


def handle_dns_c_set_command(args, params):
    """The set command entry point"""
    setting = args.command[2]
    env = args.envs[0]
    service = args.services[0]
    region = args.regions[0]
    print('dns set %s env=%s service=%s region=%s' %
          (setting, env, service, region))
    if not check_for_is_dns_set_confirmed_v2(params):
        return do_dns_set_before_confirm(setting, env, service, region)
    else:
        raise ShowSlackError(
            'Invalid PATH....  confirmed handle_dns_set_command()'
        )

# Below are the v2 helper functions


def do_dns_service_v2(env):
    """Deals with the dns service command.(V2)"""
    print('(V2) do_dns_service(%s)' % env)
    try:
        ret = '    Service name\n'
        ret += '    %s\n' % 'mock_service_a'
        ret += '    %s\n' % 'mock_service_b'
        return ret
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        raise ShowSlackError('An error occurred. Check logs.')


def do_dns_status_v2(env, service):
    """Deals with the slack-bud dns status command.(V2)"""
    print('do_dns_status(%s, %s)' % (env, service))
    # scan_items = scan_state_table_for_env(env)
    # is_multiregion_service = \
    #     verify_service_is_multiregion(scan_items, env, service)
    is_multiregion_service = True
    if not is_multiregion_service:
        # Let user know this doesn't seem to be a multi-region service
        raise ShowSlackError(
            "Service: *%s* doesn't seem to be multiregion in *%s*"
            % (service, env)
        )

    try:
        ret = '    Service: %s\n' % service
        # for i in scan_items['Items']:
        #     print(i['key'], ":", i['value'])
        #     curr_value = i['value']
        #     service_name = curr_value.split(':')[0]
        #     if service_name in service:
        #         status_line = make_status_line(i['key'], i['value'])
        #         status_line += append_update_to_status(i['key'])
        #         ret += '    %s\n' % status_line
        ret += '    %s\n' % 'status_line_1'
        ret += '    %s\n' % 'status_line_2'
        return ret
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        raise ShowSlackError('An error occurred. Check logs.')


def check_for_is_dns_set_confirmed_v2(params):
    """"""
    return False
