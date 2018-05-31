"""Command for creating a new SlackBud command"""
import glob
import os


def update_entry_point(cmd_lower_case, cmd):
    """
    Updates the entry point with needed import for new command.

    :param cmd_lower_case:
    :return: True if it succeeded.
    """
    # Open the entry point file for reading and writing.
    try:
        with open('../slack_bud/lambda_function.py', "r+") as f:
            original_file = f.read()

            # write the backup file.
            backup_fh = open('../slack_bud/lambda_function_backup.py', "w")
            backup_fh.writelines(original_file)
            backup_fh.close()

            # read the template files.
            import_fh = open('./create_slack_cmdimportline.txt', 'r')
            import_template = import_fh.read()
            switch_fh = open('./create_slack_cmdswitchline.txt', 'r')
            switch_template = switch_fh.read()
            confirm_fh = open('./create_slack_cmdconfirmsline.txt', 'r')
            confirm_template = confirm_fh.read()

            # modify entry point.
            import_template = import_template.replace('{cmdlowercase}', cmd_lower_case)
            import_template = import_template.replace('{cmd}', cmd)
            switch_template = switch_template.replace('{cmdlowercase}', cmd_lower_case)
            switch_template = switch_template.replace('{cmd}', cmd)
            confirm_template = confirm_template.replace('{cmdlowercase}', cmd_lower_case)
            confirm_template = confirm_template.replace('{cmd}', cmd)

            modified_file = original_file.replace('# {cmdimportline}', import_template)
            modified_file = modified_file.replace('# {cmdswitchline}', switch_template)
            modified_file = modified_file.replace('# {cmdconfirmsline}', confirm_template)

            f.seek(0)
            f.write(modified_file)
            f.truncate()
            f.close()
        return True
    except Exception as ex:
        print("Something went wrong.")
        print("Restore the original file from the backup. ")
        print("   slack_bud/lambda_function_backup.py")
        print()
        print("Error: {}".format(ex))
        return False


def update_longtask_entry_point(cmd_lower_case, cmd):
    try:
        print('...')
        with open('../slack_bud/lambda_longtasks.py', "r+") as f:
            original_file = f.read()

            # write the backup file.
            backup_fh = open('../slack_bud/lambda_longtasks_backup.py', "w")
            backup_fh.writelines(original_file)
            backup_fh.close()

            # read the template files.
            import_fh = open('./create_slack_cmdimportline.txt', 'r')
            import_template = import_fh.read()
            switch_fh = open('./create_slack_cmdlongtaskswitchline.txt', 'r')
            switch_template = switch_fh.read()
            confirm_fh = open('./create_slack_cmdconfirmsline.txt', 'r')
            confirm_template = confirm_fh.read()

            # modify entry point.
            import_template = import_template.replace('{cmdlowercase}', cmd_lower_case)
            import_template = import_template.replace('{cmd}', cmd)
            switch_template = switch_template.replace('{cmdlowercase}', cmd_lower_case)
            switch_template = switch_template.replace('{cmd}', cmd)
            confirm_template = confirm_template.replace('{cmdlowercase}', cmd_lower_case)
            confirm_template = confirm_template.replace('{cmd}', cmd)

            modified_file = original_file.replace('# {cmdimportline}', import_template)
            modified_file = modified_file.replace('# {cmdlongtaskswitchline}', switch_template)
            modified_file = modified_file.replace('# {cmdconfirmsline}', confirm_template)

            f.seek(0)
            f.write(modified_file)
            f.truncate()
            f.close()
        return True
    except Exception as ex:
        print("Something went wrong.")
        print("Restore the original file from the backup. ")
        print("   slack_bud/lambda_function_backup.py")
        print()
        print("Error: {}".format(ex))
        return False

def delete_backup_entry_point_files():
    """
    If everything goes well, delete the backup file.

    :return: None
    """
    os.remove('../slack_bud/lambda_function_backup.py')
    os.remove('../slack_bud/lambda_longtasks_backup.py')

def list_current_commands():
    """
    Looks in the cmds directory to figure out what the current
    list of commands are.

    :return: list of commands.
    """
    ret_val = []
    cmd_files = glob.glob('../slack_bud/cmds/cmds_*.py')
    for cmd_file in cmd_files:
        # print(cmd_file)
        parts = cmd_file.split('_')
        cmd_name = parts[len(parts) - 1].replace('.py', '')
        ret_val.append(cmd_name)

    ret_val.sort()
    return ret_val


def generate_sub_cmd_prop_entries(sub_command_list):
    """
    Create the replacement string for the dictionary in the
    get_cmd_properties method.

    It should be one line for each sub-command like:

            'props_create': self.get_create_properties(),
            'props_list': self.get_list_properties()
    # {#sub_command_prop_methods#}

    If the sub commands were ['create', 'list']

    :param sub_command_list:
    :return: str
    """
    ret_val = ''
    num_sub_commands = len(sub_command_list)
    index = 1
    for curr_sub_cmd in sub_command_list:
        ret_val += "            'props_{}': self.get_{}_properties()"\
            .format(curr_sub_cmd, curr_sub_cmd)
        if index < num_sub_commands:
            ret_val += ','
        ret_val += '\n'
        index += 1
    return ret_val


def generate_sub_command_prop_methods(new_cmd_lower_case, sub_command_list):
    """
    Create the property settings methods for each sub-command.

    These are initial settings that the developer should update.

    :param sub_command_list:
    :return: str with properties methods.
    """
    ret_val = ''
    for curr_sub_cmd in sub_command_list:
        ret_val += '\n'
        ret_val += '    def get_{}_properties(self):\n'.format(curr_sub_cmd)
        ret_val += '        """\n'
        ret_val += '        The properties for the "{}" sub-command\n'.format(curr_sub_cmd)
        ret_val += '        Modify the values as needed, but leave keys alone.\n'
        ret_val += "        Valid 'run-type' values are ['shorttask, 'longtask, 'docker']\n"
        ret_val += "        The 'confirmation' section is and advanced feature and commented out.\n"
        ret_val += "        Remove it unless you plan on using confirmation responses.\n"
        ret_val += "        'help_text' needs a short one line description\n"
        ret_val += "        'help_examples' is a python list.\n"
        ret_val += "              Modify add remove examples (one per line) as needed.\n"
        ret_val += "        'switch-templates' contains common switchs (-e, -d, -s)\n"
        ret_val += "              remove the ones not need. Leave an empty list if needed.\n"
        ret_val += "              use 'region-optional' and 'service-optional' if param not required."
        ret_val += "        See 'switch-z' as an example custom parameter definition.\n"
        ret_val += "            valid 'types' are string | int | property\n"
        ret_val += "        Copy-paste that section as needed.\n"
        ret_val += "        Then delete the 'switch-z' section.\n"
        ret_val += "        \n"
        ret_val += "        When done reduce the DocString to a description of the \n"
        ret_val += "            sub-commands properties.\n"
        ret_val += '        :return: python dictionary\n'
        ret_val += '        """\n'
        ret_val += '        props = {\n'
        ret_val += "            'run-type': 'shorttask',\n"
        ret_val += "            'help_text': '`<{}>` description here.',\n".format(curr_sub_cmd)
        ret_val += "            'help_examples': [\n"
        ret_val += "                '/bud {} {} -e dev -r us-east-1 -s devnull',\n".format(
            new_cmd_lower_case, curr_sub_cmd)
        ret_val += "                '/bud {} {} -e dev -r us-west-2 -s devnull -t 30'\n".format(
            new_cmd_lower_case, curr_sub_cmd)
        ret_val += "            ],\n"
        ret_val += "            'switch-templates': ['env', 'service', 'region-optional'],\n"
        ret_val += "            'switch-c': {\n"
        ret_val += "                'aliases': ['c', 'changeme'],\n"
        ret_val += "                'type': 'string',\n"
        ret_val += "                'required': False,\n"
        ret_val += "                'lower_case': True,\n"
        ret_val += "                'help_text': 'Change this help string for switch'\n"
        ret_val += "            }\n"
        ret_val += '        }\n'
        ret_val += '        return props\n'
        ret_val += '\n'
        ret_val += '    def invoke_{}(self, cmd_inputs):\n'.format(curr_sub_cmd)
        ret_val += '        """\n'
        ret_val += '        Placeholder for "{}" sub-command\n'.format(curr_sub_cmd)
        ret_val += '        :param cmd_inputs: class with input values.\n'
        ret_val += '        :return:\n'
        ret_val += '        """\n'
        ret_val += '        try:\n'
        ret_val += '            print("invoke_{}")\n'.format(curr_sub_cmd)
        ret_val += "            arg_region = cmd_inputs.get_by_key('region')  # remove if not used\n"
        ret_val += "            arg_env = cmd_inputs.get_by_key('env')  # remove if not used\n"
        ret_val += "            arg_service = cmd_inputs.get_by_key('service')  # remove if not used\n"
        ret_val += '            response_url = cmd_inputs.get_response_url()\n'
        ret_val += '        \n'
        ret_val += '            # Start {} code section #### output to "text" & "title".\n'.format(curr_sub_cmd.title())
        ret_val += '        \n'
        ret_val += '            # End {} code section. ####\n'.format(curr_sub_cmd.title())
        ret_val += '        \n'
        ret_val += '            # Standard response below. Change title and text for output.\n'
        ret_val += '            title = "{} title"\n'.format(curr_sub_cmd.title())
        ret_val += '            text = "{} response. Fill in here"\n'.format(curr_sub_cmd.title())
        ret_val += '            return self.slack_ui_standard_response(title, text)\n'
        ret_val += '        except ShowSlackError:\n'
        ret_val += '            raise\n'
        ret_val += '        except Exception as ex:\n'
        ret_val += '            bud_helper_util.log_traceback_exception(ex)\n'
        ret_val += '            raise ShowSlackError("Invalid request. See log for details.")\n'
    return ret_val


def main():
    """
    Entry point for creating new SlackBud commands.

    This command does not take any parameters, instead it
    asks question about creating a new command. 

    It then add the code where needed, and create a class with
    several methods that you need to fill out.
    :return:
    """
    current_dir = os.getcwd()
    # print('working dir: {}'.format(current_dir))

    # List the current known commands.
    print('\n\n\n')
    print("SlackBud Command Creator\n")
    print('Below are the current commands.')

    command_list = list_current_commands()
    for curr_sub_cmd in command_list:
        print('  {}'.format(curr_sub_cmd))


    print('\n')
    yes = raw_input('Do you want to create a new command?\n (y/n): ')
    if yes != 'y':
        print('\nResponse was: {}'.format(yes))
        print('You elected to not create a new command.')
        print('Have a nice day\n')
        return

    print("Creating a new command.")
    # Let's ask for inputs instead.
    new_cmd = raw_input('command name: ')
    if '-' in new_cmd:
        new_cmd = new_cmd.replace('-','_')
        print("The character '-' not valid in python. Replacing with '_'.\ncmd: {}".format(new_cmd))
    cmd_author = raw_input('email [name]@roku.com): ')
    print("cmd: {}\nauthor: {}".format(new_cmd, cmd_author))

    print("Short description of command.")
    help_title = raw_input('Short (100 character) summary of command: \n')

    is_valid_help_title = False
    help_title.replace("'", '"')
    if help_title:
        if len(help_title) < 100:
            is_valid_help_title = True

    if not is_valid_help_title:
        help_title = new_cmd + ' help title'
        print('Invalid help title. Will use this instead: \n'.format(help_title))
        print('You can modify the "help_title" property in the "get_cmd_properties" method to update.')

    new_cmd_title = new_cmd.title()
    new_cmd_lower_case = new_cmd.lower()

    print("Specify initial sub-commands. Use comma delimited format like: 'create, list'")
    sub_commands_line = raw_input('Sub-command name(s): \n')

    is_valid_sub_command_line = False
    if sub_commands_line:
        try:
            sub_commands_line = sub_commands_line.lower()
            sub_command_list = sub_commands_line.split(',')
            sub_command_list = [x.strip() for x in sub_command_list]
            print('Sub-commands: {}'.format(sub_command_list))
            for curr_sub_cmd in sub_command_list:
                # Verify each word is less than 10 characters, and is only alpha numeric, or _default_
                if curr_sub_cmd == '_default_':
                    continue
                if not curr_sub_cmd.isalnum():
                    print('WARNING: "{}"\n All sub-commands must be alpha-numeric.'.format(curr_sub_cmd))
                    print("Please try again.")
                    return
                if len(curr_sub_cmd) > 9:
                    print('WARNING: "{}"\n All sub-commands must be less than 10 characters.'.format(curr_sub_cmd))
                    print("Please try again.")
                    return
        except Exception as ex:
            print('WARNING: Script could not parse response.\n{}'.format(sub_commands_line))
            print('Please try again.')
            return
    else:
        print('Only "help" & "version" should have no sub-commands.')
        print('You are about to create a command without sub-commands')
        verify_no_sub_cmds = raw_input("Are you sure?")
        sub_command_list = []

    # Add template in cmds directory.
    f = open('./create_slack_cmd_template.txt', 'r')
    template_string = f.read()

    template_string = template_string.replace('{help_title}', help_title) # we might remove this.
    template_string = template_string.replace('{#help_title#}', help_title)
    template_string = template_string.replace('{cmdlowercase}', new_cmd_lower_case)
    template_string = template_string.replace('{cmd}', new_cmd_title)
    sub_cmd_str = str(sub_command_list)
    template_string = template_string.replace('{#sub_command_list#}', sub_cmd_str)
    sub_cmd_prop_entries = generate_sub_cmd_prop_entries(sub_command_list)
    template_string = template_string.replace('# {#sub_command_prop_methods#}', sub_cmd_prop_entries)
    sub_command_prop_methods = generate_sub_command_prop_methods(new_cmd_lower_case, sub_command_list)
    template_string = template_string.replace('# {#sub_command_prop_method_def#}', sub_command_prop_methods)
    new_cmd_file = template_string.replace('{auth}', cmd_author)

    print('\n==========\n')
    print('This file will be added into the slack_bud repository.')
    print('../slack_bud/cmds/cmds_{}.py\n'.format(new_cmd))
    print(new_cmd_file)

    print()
    yes = raw_input('Do you want to add this file?\n (y/n): ')
    if yes != 'y':
        print('\nResponse was: {}'.format(yes))
        print('You elected to not add the file.')
        print('Try again later.\n')
        return

    # Add the file.
    new_file_path = '../slack_bud/cmds/cmds_{}.py'.format(new_cmd)
    print(new_file_path)
    fh = open(new_file_path, "w")
    fh.writelines(new_cmd_file)
    fh.close()

    # update the entry point.
    success = update_entry_point(new_cmd_lower_case, new_cmd_title)
    if success:
        success = update_longtask_entry_point(new_cmd_lower_case, new_cmd_title)
        if success:
            print("Commit new files to git.")
            print("Check /buddev in a few minutes for new command.")
            delete_backup_entry_point_files()
    else:
        print("Don't commit new files to git.")
        print("Restore backup file.")


if __name__ == '__main__':
    main()
