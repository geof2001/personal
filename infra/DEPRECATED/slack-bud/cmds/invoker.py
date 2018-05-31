"""Singleton class the stores all command names in call invoke on them."""
import os
import cmds_backup as backup
import cmds_props as props
import cmds_version as version
import slack_ui_util


class Invoker:
    # _cmd_map = None
    #
    # @staticmethod
    # def invoke_command(self, cmd_name):
    #     """
    #     Loads all possible commands from directory and then invokes it.
    #     :param cmd_name:
    #     :return:
    #     """
    #     if _cmd_map is None:
    #         _cmd_map = []
    @staticmethod
    def invoke_sub_command(self, cmd, sub_command, args):

        # This is just for testing. Want reflection-type loading into a Singelton.
        cmd_map = ['backup', 'props', 'version']

        # Test a reflection type load.
        if cmd in cmd_map:
            if cmd == 'backup':
                return getattr(backup, 'invoke_sub_command')(sub_command, args)
            elif cmd == 'props':
                return getattr(props, 'invoke_sub_command')(sub_command, args)
            elif cmd == 'version':
                return getattr(version, 'invoke_sub_command')(sub_command, args)
            else:
                # unknown command
                return slack_ui_util.error_response('Unknown command: %s' % sub_command)

        else:
            error_text = 'Failed to find: %s' % cmd
            return slack_ui_util.error_response(error_text)


# some local testing
if __name__ == '__main__':
    try:
        Invoker.invoke_sub_command('version', 'version', None)

        print('SUCCESS: Smoke tests finished')
    except Exception as ex:
        error_log = 'Failed with: %s -> %s' % (type(ex), ex)
        print(error_log)
        print('Exception args: %s' % ex.args)
        print('/nFAIL: Smoke tests failed.')
