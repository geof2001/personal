"""
It handles both standard and confirm commands. It reads
all inputs and determine what kind of command it is, provides
the information needed for validation, reads the properties of
the command and sub-command and then can serialize/deserialize
itself for transport across the wire to a different lambda
function or docker task or ssm script.
"""
import json
import shlex
import util.bud_helper_util as bud_helper_util
from util.bud_helper_util import squash_token_print


class CmdInputs:
    """
    Command Inputs
    """

    def __init__(self, params=None):
        """
        Read the params from the event and parses it for
        validation and command information.
        """
        # Initialize variables.
        self._response_url = None
        self._raw_cmd_line = None
        self._arg_list = []
        self._arg_dict = {}
        self._slack_bud_env = 'dev'
        self._slack_user_id = None
        self._slack_user_name = None
        self._cmd = None
        self._sub_cmd = None
        self._is_confirmation_cmd = False
        self._callback_value = None
        self._callback_id = None
        self._confirmation_params = {}
        self._is_ephemeral = True
        self._where_am_i = None  # We don't send this across the wire. It is set at entry point.
        self._cmd_specific_data = None  # We don't send this across the wire. It is set before invoke sub-command call.

        try:
            if params:
                #print('params = {}'.format(params))
                squash_token_print("params = ", params)
                # Parse the input.
                # Determine the environment.
                self._slack_bud_env = bud_helper_util.get_slack_bud_environment(params)
                self._is_confirmation_cmd = 'payload' in params
                if not self._is_confirmation_cmd:
                    # Parse the confirmation command
                    # print('(debug) Standard params: {}'.format(params))
                    self._slack_user_id = get_slack_user_id(params)
                    self._slack_user_name = params['user_name'][0]
                    self._raw_cmd_line = params['text'][0]
                    self._response_url = params['response_url'][0]
                    if self._raw_cmd_line:
                        self._arg_list = shlex.split(self._raw_cmd_line)
                        cmd = str(self.get_by_index(0))
                        self._cmd = cmd.lower()
                else:
                    # Parse the standard command
                    # print('(debug) CONFIRMATION params: {}'.format(params))
                    self._callback_id = get_callback_id(params)
                    self._callback_value = get_fallback_value(params)

            else:
                print('Not initialized in __init__. Must be deserialization')

        except Exception as ex:
            #print('Failed to parse params =  {}'.format(params))
            squash_token_print("Failed to parse parame = ", params)
            print(self.log_state('__init__ error:'))
            # log any exceptions.
            bud_helper_util.log_traceback_exception(ex)

    def __repr__(self):
        """
        toString for python
        :return:
        """
        to_string = 'CmdInput['
        to_string += 'is_confirmation_cmd={}, '.format(self._is_confirmation_cmd)
        if self._callback_value:
            to_string += 'callback_value={}, '.format(self._callback_value)
        if self._callback_id:
            to_string += 'callback_id={}, '.format(self._callback_id)
        if self._confirmation_params:
            to_string += 'confirmation_params={}, '.format(self._confirmation_params)
        if self._cmd:
            to_string += 'cmd={}, '.format(self._cmd)
        if self._sub_cmd:
            to_string += 'sub_cmd={}, '.format(self._sub_cmd)
        if self._raw_cmd_line:
            to_string += 'raw_cmd_line={}, '.format(self._raw_cmd_line)
        if len(self._arg_list) > 0:
            to_string += 'arg_list={}, '.format(self._arg_list)
        if bool(self._arg_dict):
            to_string += 'arg_dict={}, '.format(self._arg_dict)
        if self._slack_bud_env:
            to_string += 'slack_bud_env={}, '.format(self._slack_bud_env)
        if self._slack_user_name:
            to_string += 'slack_user_name={}, '.format(self._slack_user_name)
        if self._response_url:
            to_string += 'response_url={}'.format(self._response_url)
        to_string += ']'

        return to_string

    def set_where_am_i(self, exec_location):
        """
        Use this to inform the custom code about where it is being
        executed. It should be set by the response handler (lambda or docker)
        right after the inputs are deserialized.

        This is needed since "shorttask" might just return while
        "longtask" (lambda) will POST to url_response, and docker will (TBD?)...
        :param exec_location:
        :return: str 'shorttask' | 'longtask' | 'docker'
        """
        # Verify input. (It is important to get this right)
        valid_inputs = ['shorttask', 'longtask', 'docker']
        if exec_location not in valid_inputs:
            err_msg = 'Invalid setting for "where_am_i". Expected: {}. Was: {}'\
                .format(valid_inputs, exec_location)
            print('ERROR: {}'.format(err_msg))
            raise ValueError(err_msg)

        self._where_am_i = exec_location

    def get_where_am_i(self):
        """
        Command write code calls this function to get information
        about where it is being executed.

        Depending on location code can use different channels to
        send responses.
        :return: str 'shorttask' | 'longtask' | 'docker'
        """
        if not self._where_am_i:
            raise ValueError('"where_am_i" param must be set by entry point')

        return self._where_am_i

    def contains_property(self, property_name):
        """
        All property names must be double dashed. Return True if found otherwise False.
        :param property_name: ex. "show" will look for property "--show"
        :return: bool  True | False
        """
        property_string = '--'+property_name
        if property_string in self._arg_list:
            return True
        return False

    def set_cmd_specific_data(self, data_dict):
        """
        Set data that is specific to this command. It is added
        during the entry point before the invoke_* call.

        The user set what the keys are.

        :param data_dict:
        :return: None
        """
        self._cmd_specific_data = data_dict

    def get_cmd_specific_data(self):
        """
        Get the data specific to the command.
        :return:
        """
        return self._cmd_specific_data

    def is_confirmation_cmd(self):
        """
        True if this is a confirmation command, otherwise false.
        :return:
        """
        return self._is_confirmation_cmd

    def get_callback_value(self):
        """
        The command this is a confimation command for.
        :return: str like: 'CmdProps'
        """
        return self._callback_value

    def get_callback_id(self):
        """
        If available this returns the confirmation_id from the
        input parameters. If this isn't available, like for a standard
        command, this returns None.
        :return: str like: confirm_restore
        """
        return self._callback_id

    def set_confirmation_params(self, params_dict):
        """

        :param params_dict:
        :return:
        """
        # Verify this a dictionary.
        print('CmdInputs.set_confirmation_params() type(params_dict)={}'.format(str(type(params_dict))))
        print('params_dict={}'.format(params_dict))
        if isinstance(params_dict, dict):
            self._confirmation_params = params_dict
        elif isinstance(params_dict, str) or isinstance(params_dict, unicode):
            print('WARN. convert params_dict from string. {}'.format(params_dict))
            self._confirmation_params = dict(params_dict)

    def get_confirmation_params(self):
        """
        Return params dictionary.
        :return:
        """
        return self._confirmation_params

    def get_response_url(self):
        """
        Get response_url
        :return:
        """
        return self._response_url

    def get_slack_user_name(self):
        """
        Return the slack user name. ex. asnyder
        :return: string
        """
        return self._slack_user_name

    def get_slack_bud_env(self):
        """
        Is this slack_bud in 'dev' or 'prod'?
        :return: str 'dev' | 'prod'
        """
        return self._slack_bud_env

    def get_command(self):
        """
        Returns the command.
        :return: str like: CmdProps
        """
        if self._cmd:
            return self._cmd
        self.convert_fallback_value_to_command()
        return self._cmd

    def get_sub_command(self):
        """
        If the command has a sub-command, this will return
        what it is. A few commands like CmdHelp and CmdVersion
        don't have a sub command. In those cases it returns
        None
        :return: str like: list
        """
        if self._sub_cmd:
            return self._sub_cmd
        # if confirm command, get from callback_id
        elif self.is_confirmation_cmd():
            self.convert_callback_id_to_sub_command()
            return self._sub_cmd
        # Help and Version don't have sub_commands

    def set_default_sub_command(self):
        """
        Signify a 'default' sub-command (mixed with other sub_commands) by
        inserting '_default_' into the index for the sub_command in the list
        before the normal parsing occurs.
        :return:
        """
        self._arg_list.insert(1, '_default_')

    def has_valid_slack_token(self):
        """
        Returns if it has a valid slack token
        :return: True | False
        """
        return True # temporary

    def is_user_authorized(self):
        """
        Is the user authorized to run this command?
        :return: True | False
        """
        return True

    def get_by_index(self, index):
        """
        If a standard command get the parameter at a certain index
        :param index: position in command line
        :return: str
        """
        if len(self._arg_list) >= index:
            return self._arg_list[index]
        else:
            return None

    def set_key_value_map(self, key_value_map):
        """
        Setter for key/value map.
        :param key_value_map:
        :return:
        """
        self._arg_dict = key_value_map

    def get_by_key(self, key):
        """
        Get an element from the command line by either it's
        swith (-r) or by key (region)
        :param key:
        :return:
        """
        if not self._arg_dict:
            return None

        # We don't store keys with dashes, but in case they forget.
        if key.startswith('-'):
            key = key.replace('-','')

        return self._arg_dict.get(key)

    def get_raw_inputs(self):
        """
        Return the raw command line, as typed by user.
        :return: String
        """
        return self._raw_cmd_line

    def set_cmd_inputs_value(self, key, value):
        """

        :param key:
        :param value:
        :return: None
        """
        self._arg_dict[key] = value

    def set_slack_ui_is_public_response(self):
        """
        By default responses are ephemeral. This is called when the
        (--show) switch is on the command line. It makes the response
        visible.
        :return: None, just change state.
        """
        self._is_ephemeral = False

    def is_public_response(self):
        """
        Commands results are by default 'ephemeral' or
        invisible to other people in the channel.

        This is set to False if something should be shown to
        others in the channel.
        :return: False when shown to others in channel otherwise True
        """
        return not self._is_ephemeral

    def convert_fallback_value_to_command(self):
        """
        When is a confirmation command, the fallback_value is a proxy
        for the command. Convert that value, to populate the command, for
        flow control.
        :return: None, but internal state is changed.
        """
        print('convert_fallback_value_to_command()'
              ' fallback_value={}'.format(self._callback_value))

        fallback_value = self._callback_value
        if fallback_value.startswith('Cmd'):
            cmd = fallback_value.replace('Cmd', '')
        else:
            # Throw error for unexpected value.
            raise ValueError('Unexpected fallback_value={}'.format(fallback_value))
        cmd = cmd.lower()

        if self._cmd is not None:
            print('WARN: replacing command: {} for {}'.format(self._cmd, cmd))
        self._cmd = cmd

    def convert_callback_id_to_sub_command(self):
        """
        By naming convention all callback_ids need to be in the format:
          callback_<sub-cmd-name>_<anything>.
        Here we are using that naming convention to get the subcommand
        for a confirmation response from the callback_id, since the
        raw_command_line information isn't in this response.
        :return: str - sub-command-name from callback_id.
        """
        if self._callback_id:
            callback_id = self._callback_id
            print('convert_callback_id_to_sub_command: "{}"'.format(callback_id))
            if not callback_id.startswith('callback_'):
                raise ValueError('Invalid callback_id. Must start with: '
                                 '"callback_<sub-cmd-name>_*" was: {}'.format(callback_id))
            parts = callback_id.split('_')
            sub_cmd_from_callback_id = parts[1]
            if sub_cmd_from_callback_id == 'default':
                sub_cmd_from_callback_id = '_default_'
            print('confirmation command sub_command is: {}'.format(sub_cmd_from_callback_id))
            self._sub_cmd = sub_cmd_from_callback_id

    def serialize(self):
        """
        Serialize this class state for sending across the wire to a different lambda function,
        or docker or ssm script.
        :return:
        """
        ret_val = {
            'response_url': none_to_empty_str(self._response_url),
            'raw_cmd_line': none_to_empty_str(self._raw_cmd_line),
            'arg_list': self._arg_list,
            'is_ephemeral': self._is_ephemeral,
            'arg_dict': self._arg_dict,
            'slack_bud_env': self._slack_bud_env,
            'slack_user_id': none_to_empty_str(self._slack_user_id),
            'slack_user_name': none_to_empty_str(self._slack_user_name),
            'cmd': self._cmd,
            'sub_cmd': none_to_empty_str(self._sub_cmd),
            'is_confirmation_cmd': self._is_confirmation_cmd,
            'callback_value': none_to_empty_str(self._callback_value),
            'callback_id': none_to_empty_str(self._callback_id),
            'confirmation_params': self._confirmation_params
        }

        return ret_val

    def deserialize(self, cmd_inputs_dict):
        """
        Deserialize this class.
        :param cmd_inputs_dict: JSON string from wire is turned into python dictionary first
        :return:
        """
        self._response_url = empty_str_to_none(cmd_inputs_dict['response_url'])
        self._raw_cmd_line = empty_str_to_none(cmd_inputs_dict['raw_cmd_line'])
        self._arg_list = cmd_inputs_dict['arg_list']
        self._is_ephemeral = cmd_inputs_dict['is_ephemeral']
        self._arg_dict = cmd_inputs_dict['arg_dict']
        self._slack_bud_env = cmd_inputs_dict['slack_bud_env']
        self._slack_user_id = empty_str_to_none(cmd_inputs_dict['slack_user_id'])
        self._slack_user_name = empty_str_to_none(cmd_inputs_dict['slack_user_name'])
        self._cmd = cmd_inputs_dict['cmd']
        self._sub_cmd = empty_str_to_none(cmd_inputs_dict['sub_cmd'])
        self._is_confirmation_cmd = cmd_inputs_dict['is_confirmation_cmd']
        self._callback_value = empty_str_to_none(cmd_inputs_dict['callback_value'])
        self._callback_id = empty_str_to_none(cmd_inputs_dict['callback_id'])
        self._confirmation_params = cmd_inputs_dict['confirmation_params']

        self.log_state('def deserialize:')

    def log_state(self, prefix):
        """
        Use this command for debugging to log the state of this command.
        :type prefix: str - to id in log. like '__init__' or 'deserialized'
        :return: None
        """
        print('{} CmdInput: response_url = {}'.format(prefix, self._response_url))
        print('{} CmdInput: raw_cmd_line = _{}_'.format(prefix, self._raw_cmd_line))
        print('{} CmdInput: arg_list = {}'.format(prefix, self._arg_list))
        print('{} CmdInput: is_ephemeral = {}'.format(prefix, self._is_ephemeral))
        print('{} CmdInput: arg_dict = {}'.format(prefix, self._arg_dict))
        print('{} CmdInput: slack_bud_env = {}'.format(prefix, self._slack_bud_env))
        print('{} CmdInput: slack_user_id = {}'.format(prefix, self._slack_user_id))
        print('{} CmdInput: slack_user_name = {}'.format(prefix, self._slack_user_name))
        print('{} CmdInput: cmd = {}'.format(prefix, self._cmd))
        print('{} CmdInput: sub_cmd = {}'.format(prefix, self._sub_cmd))
        print('{} CmdInput: is_confirmation_cmd = {}'.format(prefix, self._is_confirmation_cmd))
        print('{} CmdInput: callback_value = {}'.format(prefix, self._callback_value))
        print('{} CmdInput: callback_id = {}'.format(prefix, self._callback_id))
        print('{} CmdInput: confirmation_params = {}'.format(prefix, self._confirmation_params))
        print('{} CmdInput: self._cmd_specific_data = {}'.format(prefix, self._cmd_specific_data))

# End class functions
# ###################################
# Start static helper methods sections


def none_to_empty_str(value):
    """
    Helper method for converting Python dictionary into JSON string.
    :param value: str
    :return: If None return an empty string
    """
    if value:
        return value.strip()
    return ''


def empty_str_to_none(str_value):
    """
    Helper method for converting JSON back into python dictionary
    :param str_value:
    :return: if empty string return None, otherwise str_value
    """
    if str_value == '':
        return None
    return str_value.strip()


def get_fallback_value(params):
    """
    The fallback value is the same as the class name as defined
    by the abstract base class.

    NOTE: 'in_channel' and 'ephemeral' responses have a different structure.
    If we don't find the value in the 'in_channel' format then we fallback to looking
    for it in the 'ephemeral' format. That format has the fallback value in the
    3rd position of the 'callback_id'.

    :param params:
    :return: string fallback value.
    """
    # ToDo: Reverse order of 'in_channel' vs. 'ephemeral' check, if ephemeral is default mode.
    try:
        in_channel_fallback_value = json.loads(params['payload'][0])['original_message']['attachments'][0]['fallback']
        if in_channel_fallback_value:
            print('Found callback_id in "in_channel" format: callback_id = {}'.format(in_channel_fallback_value))
            return in_channel_fallback_value
    except:
        # Being pythonic.
        print('This appears to be ephemeral mode.')

    try:
        # Ephemeral responses, have a different structure, since 'original_message' isn't passed.
        # Instead we pull it from the 3rd position in the callback_id.
        print("Didn't find fallback_value. Falling back to ephemeral format.")
        ephemeral_callback_id = get_callback_id(params)
        if ephemeral_callback_id:
            # We pull the value out of the third position, since
            print('Found callback_id in "ephemeral" format: callback_id = {}'.format(ephemeral_callback_id))
            ephemeral_fallback_value = convert_callback_id_to_fallback_for_ephemeral_response(ephemeral_callback_id)
            return ephemeral_fallback_value

        # Didn't find it in either format.
        raise ValueError("Failed to find 'callback_id'! params = {}".format(params))
    except Exception as ex:
        print('ERROR: Failed to find fallback value. params={}'.format(params))
        raise ValueError('Failed to find fallback value. Reason: {}'.format(ex.message))


def convert_callback_id_to_fallback_for_ephemeral_response(callback_id):
    """
    The naming convention for callback_ids need to be in the format:
      callback_<sub-cmd-name>_<fallback>_<anything>

    Parse out the fallback value and return just that.
    :param callback_id:
    :return:
    """
    if not callback_id.startswith('callback_'):
        raise ValueError('Invalid callback_id. Must start with: '
                         '"callback_<sub-cmd-name>_<fallback>*" was: {}'.format(callback_id))
    parts = callback_id.split('_')
    fallback_value = parts[2]

    print('confirmation fallback value (ephemeral mode) is: {}'.format(fallback_value))
    return fallback_value


def get_callback_id(params):
    """
    This is a confirmation command, so 'params' should have the 'payload' key.
    Get the callback_id
    :param params:
    :return: str - callback_id from the payload section of params
    """
    try:
        data = json.loads(params['payload'][0])
        callback_id = data['callback_id']
        return callback_id.strip()
    except Exception as ex:
        raise ValueError('Failed to find callback_id. Reason: {}'.format(ex.message))


def get_slack_user_id(params):
    """
    Just get the use_id from the call.
    :param params: params
    :return: return user name. If not found return None.
    """
    return params['user_id'][0]

# End static helper methods
# #########################
# Star unit-test section. All test function must start with "test_..."


def test_serialize_deserialize_main():
    """
    Test serializing/deserializing this class.
    :return: True if no exception fail if an exception
    """
    try:
        param_case_1 = get_params_case_1()
        input_case_1 = CmdInputs(param_case_1)
        input_case_1.log_state('case1')
        ser1 = input_case_1.serialize()
        print('ser1 = {}'.format(ser1))
        input_case_1_lt = CmdInputs(None)
        input_case_1_lt.log_state('case1-lt')
        # Simulate transfer to lambda function.
        ser1_dict = dict(ser1)
        input_case_1_lt.deserialize(ser1_dict)

        return True

    except Exception as ex:
        bud_helper_util.log_traceback_exception(ex)
        return False


def get_params_case_1():
    return None  # temporary


if __name__ == '__main__':
    #  from AWS CodeBuild during build stage
    test_serialize_deserialize_main()