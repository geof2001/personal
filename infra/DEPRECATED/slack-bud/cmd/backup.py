"""Methods for doing DynamoDB table backups commands."""
from __future__ import print_function

import slack_ui_util
from slack_ui_util import ShowSlackError
import aws_util
import bud_helper_util


def handle_dynamo_backup(command, environments, args, params):
    """Entry-point for the dynamo backup feature"""
    print("handle_dynamo_backup() Command and args ...")
    print(command)
    print(args)
    print("params ...")
    print(params)

    try:
        if 'help' in command.strip():
            return handle_backup_help_command()

        # Get dynamo client
        dynamo_client = get_dynamo_client(environments, args)

        print("backup Subcommand: %s" % args.command[1])

        if args.command[1] == 'create':
            return handle_backup_create_command(dynamo_client, args)

        if args.command[1] == 'list':
            return handle_backup_list_command(dynamo_client, args)

    except ShowSlackError as slack_error_message:
        print(type(slack_error_message))
        print(slack_error_message.args)
        print(slack_error_message)

        return slack_ui_util.error_response(slack_error_message)


def handle_backup_help_command():
    """help"""
    return slack_ui_util.text_command_response(
        "Dynamo Backup Help command v0.5", help_text(), "#00b2ff"
    )


def help_text():
    """Help for this command."""
    ret = "*Format:* _/bud backup <action> -e <env> -t <table> -r <region>_\n"
    ret += "*Example:* _/bud backup create -e dev -t MyFeed -r us-east-1_\n\n"
    ret += "*Example:* _/bud backup create -e dev -s homescreen -r us-east-1_\n\n"
    ret += "*<create>* _Creates a backup for a table_\n"
    ret += "           _use -s for Property Table of a service_\n"
    ret += "           _use -t for a specific DynamoDB table_\n"
    ret += "*<list>* _Lists all backups for a region_\n"
    return ret


def handle_backup_create_command(dynamo_client, args):
    """Slack entry point for create command

    Expect either the -s service
    or -t table argument.
    """
    print('handle_backup_create_command')
    if args.services is not None:
        service = args.services[0]
        print('service: %s' % service)
        table_name = find_prop_table_for_service(
            service=service,
            env=args.envs[0],
            region=args.regions[0]
        )
        print("Create backup for %s in service %s"
              % (table_name, service))
    else:
        if args.table is None:
            raise ShowSlackError("Command needs service[-s] or table[-t] attribute")
        table_name = args.table
        print('Create backup for table: %s' % table_name)

    return do_create_backup(dynamo_client, table_name)


def handle_backup_list_command(dynamo_client, args):
    """slack entry point for list command"""
    print('handle_backup_list_command')
    return do_list_backup(dynamo_client, None)


def get_dynamo_client(environments, args):
    """Get dynamo client for AWS account and region."""
    try:
        print("get_dynamo_client")
        env = args.envs[0]
        session = aws_util.get_session(environments, env)
        if session is None:
            raise ShowSlackError("Failed to get session for %s" % env)
        region = args.regions[0]
        if region is None:
            raise ShowSlackError("No AWS region specified.")
        print("Have session for region %s" % region)
        return aws_util.get_dynamo_resource(session, region, client=True)
    except Exception as ex:
        err_text = "Error while getting dynamo client: %s" % ex.message
        print(err_text)
        raise ShowSlackError(err_text)


def do_create_backup(dynamo_client, table_name):
    """
    Backup a table.
    The BackupName is in format - TableName-timestamp.
    :param dynamo_client: Boto3 DynamoDB client for AWS account
    and AWS region specified.
    :param table_name:
    :return:
    """
    backup_name = create_backup_name(table_name)
    response = dynamo_client.create_backup(
        TableName=table_name,
        BackupName=backup_name
    )

    is_valid_response = check_response_from_create_backup(response)
    if is_valid_response:
        return slack_ui_util.text_command_response(
            title="Create Backup",
            text="Starting backup: %s" % backup_name
        )
    else:
        return slack_ui_util.error_response('Failed to start backup')


def check_response_from_create_backup(response):
    """Return True if the response is valid.
    """
    print(response)
    # ToDo: implement.
    return True


def create_backup_name(table_name):
    """Create a Dynamo backup name, which is name of table and timestamp.

    Example:
        2018-jan-19-0955-MyDynamoDBTableName
    """
    timestamp = aws_util.get_dynamo_backup_name_time_format()
    return '%s-%s' % (timestamp, table_name)


def find_prop_table_for_service(service, env, region):
    """Get dynamo property table for a service."""
    # Hard coding a name for testing.

    # test props look-up here.
    props_table = bud_helper_util.get_props_table_name_for_service(
        service_param=service,
        env_param=env,
        region_param=region
    )

    if props_table is None:
        print(
            'Use default: '
            'tableprop-manager-api-PropManagerPropertiesTable-1FMELEQVRO482'
        )
        return 'prop-manager-api-PropManagerPropertiesTable-1FMELEQVRO482'
    return props_table


def do_list_backup(dynamo_client, table_name):
    """Creates the table backup"""
    print('do_list_backup')
    if table_name is None:
        print('Listing all table backups in region')
        response = dynamo_client.list_backups()
    else:
        print('List backups for table: %s' % table_name)
        response = dynamo_client.list_backups(
            TableName=table_name
        )

    text = convert_list_response_to_slack(response)
    return slack_ui_util.text_command_response(
        title="List Backup",
        text=text
    )


def convert_list_response_to_slack(response):
    """Convert JSON from AWS boto3 response to slack text.

    :param response: - JSON response from boto3 for list_backups()
    :return:
    """
    print('convert_list_response_to_slack. response')
    print(response)

    ret = "_Backup list_\n"
    if len(response['BackupSummaries']) > 0:
        for curr_summary in response['BackupSummaries']:
            table_name = curr_summary['TableName']
            backup_name = curr_summary['BackupName']
            create_time = curr_summary['BackupCreationDateTime']
            backup_status = curr_summary['BackupStatus']
            backup_size = curr_summary['BackupSizeBytes']
            print(
                'Table: %s\nBackupName: %s\nCreated: %s\nStatus: %s\nSize: %s'
                % (table_name, backup_name, create_time, backup_status, backup_size)
            )
            ret += "_%s: %s_\n" % (backup_name, backup_status)
    else:
        ret += "No backups found"
    return ret
