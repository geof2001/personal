"""Entry point for all slack calls"""
import json
from urlparse import parse_qs
from cmds.cmd_inputs import CmdInputs
from cmds.cmds_flamegraph import CmdFlamegraph
from cmds.cmds_version import CmdVersion
from cmds.cmds_help import CmdHelp
from cmds.cmds_backup import CmdBackup
from cmds.cmds_gitwebhook import CmdGitwebhook
from cmds.cmds_test import CmdTest
from cmds.cmds_deploy import CmdDeploy
from cmds.cmds_show import CmdShow
from cmds.cmds_canary import CmdCanary
from cmds.cmds_buildinfo import CmdBuildinfo
from cmds.cmds_untagged import CmdUntagged
from cmds.cmds_user import CmdUser
from cmds.cmds_props import CmdProps
from cmds.cmds_build import CmdBuild
from cmds.cmds_service import CmdService
# {cmdimportline}
import util.bud_helper_util as bud_helper_util
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
from util.bud_helper_util import BudHelperError
from util.bud_helper_util import squash_token_print

# 

def lambda_handler(event, context):
    """
    Entry point to SlackBud lambda function.
    :param event: event from the lambda entry point
    :param context: context from the lambda entry point
    :return: Slack response
    """
    try:
        # Check for scheduled event which just keeps this lambda function active.
        #print("REFACTORING lambda_function Event: {}".format(event))
        squash_token_print("Incoming lambda function event", event)
        if is_scheduled_event(event):
            return 'done'

        params = parse_qs(event['body'])
        #print("REFACTORING params: {}".format(params))
        squash_token_print("Incoming params", params)
        
        cmd_inputs = CmdInputs(params)
        cmd_inputs.set_where_am_i('shorttask')
        if cmd_inputs.is_confirmation_cmd():
            print('This is a confirmation command!'.format(cmd_inputs))
            cmd_inputs.log_state('ConfCmd:')
            print('VERIFY. cmd is set about, otherwise need to use callback_value')
        else:
            cmd_inputs.log_state('StdCmd:')

        slack_bud_env = cmd_inputs.get_slack_bud_env()
        print('SlackBud environment: {}'.format(slack_bud_env))

        # Confirmation commands use fallback_value with class name.
        if cmd_inputs.is_confirmation_cmd():
            cmd_inputs.convert_fallback_value_to_command()
            cmd_inputs.set_confirmation_params(params)

        command = cmd_inputs.get_command()
        print('REFACTORING: command={}'.format(command))

        # Create the Cmd class.
        cmd_class = None
        if command == 'flamegraph':
            cmd_class = CmdFlamegraph(cmd_inputs)
        elif command == 'version':
            cmd_class = CmdVersion(cmd_inputs)
        elif command == 'help':
            cmd_class = CmdHelp(cmd_inputs)
        elif command == 'backup':
            cmd_class = CmdBackup(cmd_inputs)
        elif command == 'gitwebhook':
            cmd_class = CmdGitwebhook(cmd_inputs)
        elif command == 'test':
            cmd_class = CmdTest(cmd_inputs)
        elif command == 'deploy':
            cmd_class = CmdDeploy(cmd_inputs)
        elif command == 'show':
            cmd_class = CmdShow(cmd_inputs)
        elif command == 'canary':
            cmd_class = CmdCanary(cmd_inputs)
        elif command == 'buildinfo':
            cmd_class = CmdBuildinfo(cmd_inputs)
        elif command == 'untagged':
            cmd_class = CmdUntagged(cmd_inputs)
        elif command == 'user':
            cmd_class = CmdUser(cmd_inputs)
        elif command == 'props':
            cmd_class = CmdProps(cmd_inputs)
        elif command == 'build':
            cmd_class = CmdBuild(cmd_inputs)
        elif command == 'service':
            cmd_class = CmdService(cmd_inputs)
# {cmdswitchline}
        else:
            err_msg = "The command '{}' is invalid. Please enter a valid command...".format(command)
            return slack_ui_util.error_response(err_msg)

        cmd_class.authenticate_request(params)
        cmd_class.parse_inputs()
        return cmd_class.run_command()

    except BudHelperError as bhe:
        return slack_ui_util.error_response(bhe.message)

    except ShowSlackError as sse:
        return slack_ui_util.error_response(sse.message)

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        bud_helper_util.log_traceback_exception(ex)
        slack_error_message = 'An error occurred. Please check logs.'
        return slack_ui_util.error_response(slack_error_message)


def is_scheduled_event(event):
    """
    Events are sent by CloudWatch to keep the lambda function active
    and avoid start-up deploys after long idle periods.

    This method detects those events so they can be filtered from the logs.
    :param event: event from the lambda entry point
    :return: True if an Scheduled Event to keep lambda function active otherwise False
    """
    try:
        if type(event) is dict:
            key_list = list(event.keys())
            if 'detail-type' in key_list:
                detail_type = event['detail-type']
                if detail_type == 'Scheduled Event':
                    return True
        return False
    except Exception as ex:
        template = 'Failed at step "is_scheduled_event" type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))


def get_fallback_value(params):
    """
    The fallback value is the same as the class name as defined
    by the abstract base class.

    :param params:
    :return: string fallback value.
    """
    try:
        return json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']
    except Exception as ex:
        raise ShowSlackError('Failed to find fallback value. Reason: {}'.format(ex.message))
