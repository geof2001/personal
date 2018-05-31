"""Implements Backup command by asnyder"""
from __future__ import print_function
import traceback

import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdBackup(CmdInterface):

    # ###################################
    # Start Command's Properties section

    def get_cmd_properties(self):
        """
        Creates the properties for this file and returns it as a
        python dictionary.
        :return: python dictionary
        """
        props = {
            'sub_commands': ['create', 'list'],
            'help_title': 'Backup DynamoDB tables',
            'permission_level': 'dev',
            'props_create': self.get_create_properties(),
            'props_list': self.get_list_properties()
# {#sub_command_prop_methods#}
        }

        return props


    def get_create_properties(self):
        """
        The properties for the "create" sub-command
        Modify the values as needed, but leave keys alone.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*Create* Creates a backup for a dynamo table',
            'help_examples': [
                '/bud backup create -e dev -t MyFeed -r us-east-1',
                '/bud backup create -e dev -s homescreen -r us-east-1'
            ],
            'switch-templates': ['env', 'service-optional', 'region'],
            'switch-t': {
                'aliases': ['t', 'table'],
                'type': 'string',
                'required': False,
                'lower_case': False,
                'help_text': 'Name of DynamoDb table to backup'
            }
        }
        return props

    def invoke_create(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_create")
            region = cmd_inputs.get_by_key('region')  # remove if not used
            env = cmd_inputs.get_by_key('env')  # remove if not used
            service = cmd_inputs.get_by_key('service')  # remove if not used
            # Put Create code below.
            dynamo_client = get_dynamo_client(cmd_inputs)
            table = cmd_inputs.get_by_key('table') # custom parameter.

            if table is not None:
                print('service: %s' % service)
                table_name = find_prop_table_for_service(
                    service=service,
                    env=env,
                    region=region
                )
                print("Create backup for %s in service %s"
                      % (table_name, service))
            else:
                if table is None:
                    raise ShowSlackError("Command needs service[-s] or table[-t] attribute")
                table_name = table
                print('Create backup for table: %s' % table_name)

            return self.do_create_backup(dynamo_client, table_name)
        
            # Optional response below. Change title and text as needed.
            self.slack_ui_standard_response(title, text)
        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    def get_list_properties(self):
        """
        The properties for the "list" sub-command
        Modify the values as needed, but leave keys alone.
        :return: python dictionary
        """
        props = {
            'run-type': 'shorttask',
            'help_text': '*List* Lists all dynamodb backups for a region',
            'help_examples': ['/bud backup list -e dev -r us-east-1'],
            'switch-templates': ['env', 'region']
        }
        return props

    def invoke_list(self, cmd_inputs):
        """
        Placeholder for "{}" sub-command
        :param cmd_inputs: class with input values.
        :return:
        """
        try:
            print("invoke_list")
            region = cmd_inputs.get_by_key('region')  # remove if not used
            env = cmd_inputs.get_by_key('env')  # remove if not used
            service = cmd_inputs.get_by_key('service')  # remove if not used
            # Put List code below.

            dynamo_client = get_dynamo_client(cmd_inputs)
            return self.do_list_backup(dynamo_client, None)
        
            # Optional response below. Change title and text as needed.
            title = "List title"
            text = "List response. Fill in here"
            self.slack_ui_standard_response(title, text)
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
        return {}

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
            # Callback Id convention is callback_<sub-command-name>_<anything>

            # Replace_example below.
            # if callback_id == 'callback_mysubcommand_prompt_env':
            #     return some_method_to_handle_this_case(params)
            # if callback_id == 'callback_mysubcommand_prompt_region':
            #     return some_other_method_to_handle_region(params)

            # End confirmation code section.
            # Default return until this section customized.
            title = 'Default invoke_confirm_command'
            text = 'Need to customize, invoke_confirm_command'
            return self.slack_ui_standard_response(title, text)

        except ShowSlackError:
            raise
        except Exception as ex:
            bud_helper_util.log_traceback_exception(ex)
            raise ShowSlackError("Invalid request. See log for details.")

    # End class functions
# ###################################
# Start static helper methods sections

# {#invoke_methods_section#}

    def do_create_backup(self, dynamo_client, table_name):
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
            return self.slack_ui_standard_response(
                title="Create Backup",
                text="Starting backup: %s" % backup_name
            )
        else:
            return slack_ui_util.error_response('Failed to start backup')

    def do_list_backup(self, dynamo_client, table_name):
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
        return self.slack_ui_standard_response(
            title="List Backup",
            text=text
        )


def get_dynamo_client(cmd_inputs):
    """Get dynamo client for AWS account and region."""
    try:
        print("get_dynamo_client")
        env = cmd_inputs.get_by_key('env')
        session = aws_util.create_session(env)
        if session is None:
            raise ShowSlackError("Failed to get session for %s" % env)
        region = cmd_inputs.get_by_key('region')
        if region is None:
            raise ShowSlackError("No AWS region specified.")
        print("Have session for region %s" % region)
        return aws_util.get_dynamo_resource(session, region, client=True)
    except Exception as ex:
        err_text = "Error while getting dynamo client: %s" % ex.message
        print(err_text)
        raise ShowSlackError(err_text)


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



# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."

def test_cases_cmd_backup_main():
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