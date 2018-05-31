"""Entry point for longer running lambda tasks for the lambda function, called from slack-bud."""
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
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
from util.bud_helper_util import BudHelperError


def lambda_handler(event, context):
    try:
        print '(Z) LONGTASKS event: {}'.format(event)
        task = event.get('task')
        print('(Z) TASK: {}'.format(task))

        cmd_inputs = get_cmd_inputs_from_event(event)
        cmd_inputs.set_where_am_i('longtask')
        print('lambda_handler cmd_inputs: {}'.format(cmd_inputs))

        response_url = cmd_inputs.get_response_url()

        if task == 'CmdFlamegraph':
            cmd_class = CmdFlamegraph(cmd_inputs)
        elif task == 'CmdVersion':
            cmd_class = CmdVersion(cmd_inputs)
        elif task == 'CmdHelp':
            cmd_class = CmdHelp(cmd_inputs)
        elif task == 'CmdTest':
            cmd_class = CmdTest(cmd_inputs)
        elif task == 'CmdDeploy':
            cmd_class = CmdDeploy(cmd_inputs)
        elif task == 'CmdShow':
            cmd_class = CmdShow(cmd_inputs)
        elif task == 'CmdCanary':
            cmd_class = CmdCanary(cmd_inputs)
        elif task == 'CmdBuildinfo':
            cmd_class = CmdBuildinfo(cmd_inputs)
        elif task == 'CmdUntagged':
            cmd_class = CmdUntagged(cmd_inputs)
        elif task == 'CmdUser':
            cmd_class = CmdUser(cmd_inputs)
        elif task == 'CmdProps':
            cmd_class = CmdProps(cmd_inputs)
        elif task == 'CmdBuild':
            cmd_class = CmdBuild(cmd_inputs)
        elif task == 'CmdService':
            cmd_class = CmdService(cmd_inputs)
        elif task == 'CmdGitwebhook':
            cmd_class = CmdGitwebhook(cmd_inputs)
        elif task == 'CmdBackup':
            cmd_class = CmdBackup(cmd_inputs)
# {cmdlongtaskswitchline}

        else:
            print("WARNING: Unrecognized task value: {}".format(task))
            response_url = cmd_inputs.get_response_url
            error_text = "Unrecognized long task '{}'. Check error logs".format(task)
            return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

        cmd_class.run_command()

        print('Finished task: {}'.format(task))

    except BudHelperError as bhe:
        return slack_ui_util.error_response(
            bhe.message,
            post=True,
            response_url=response_url
        )

    except ShowSlackError as sse:
        return slack_ui_util.error_response(
            sse.message,
            post=True,
            response_url=response_url
        )

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        bud_helper_util.log_traceback_exception(ex)
        slack_error_message = 'An error occurred. Please check logs.'
        return slack_ui_util.error_response(
            slack_error_message,
            post=True,
            response_url=response_url
        )


def get_cmd_inputs_from_event(event):
    """
    Read the event and pull out the cmd_input class.
    :param event:
    :return:
    """
    cmd_inputs_serialized = event.get('params')
    print('longtask params: {}'.format(cmd_inputs_serialized))

    cmd_inputs = CmdInputs()
    cmd_inputs.deserialize(cmd_inputs_serialized)
    cmd_inputs.log_state('longtask deserialized:')

    return cmd_inputs
