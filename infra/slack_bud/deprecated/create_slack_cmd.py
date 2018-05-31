"""Command for creating a new SlackBud command"""
import argparse
import glob
import os

PARSER = argparse.ArgumentParser(description='Add a new SlackBud command')
PARSER.add_argument('--command', '--cmd', '-c', metavar='', default=None, nargs=1, help='Command name like: deploy')
PARSER.add_argument('--author', '--auth', '-a', metavar='', default=None, nargs=1, help='Author email like: asnyder@roku.com')


def update_entry_point(cmd_lower_case, cmd):
    """
    Updates the entry point with needed import for new command.

    :param cmd_lower_case:
    :return: True if it succeeded.
    """
    # Open the entry point file for reading and writing.
    try:
        with open('../slack_bud/cmds_lambda_function.py', "r+") as f:
            original_file = f.read()

            # write the backup file.
            backup_fh = open('../slack_bud/cmds_lambda_function_backup.py', "w")
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
        print("   slack_bud/cmds_lambda_function_backup.py")
        print()
        print("Error: {}".format(ex))
        return False


def delete_backup_entry_point_file():
    """
    If everything goes well, delete the backup file.

    :return: None
    """
    os.remove('../slack_bud/cmds_lambda_function_backup.py')


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


def main():
    """
    Entry point for this module.

    This takes just one parameter which is then name of the
    new command you want to create.

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
    for curr_cmd in command_list:
        print('  %s' % curr_cmd)


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
    help_title.replace("'",'"')
    if help_title:
        if len(help_title) < 100:
            is_valid_help_title = True

    if not is_valid_help_title:
        help_title = new_cmd + ' help title'
        print('Invalid help title. Will use this instead: \n'.format(help_title))
        print('You can modify the "get_help_title() method to update."')

    new_cmd_title = new_cmd.title()
    new_cmd_lower_case = new_cmd.lower()

    # Add template in cmds directory.
    f = open('./create_slack_cmd_template.txt', 'r')
    template_string = f.read()

    template_string = template_string.replace('{help_title}', help_title)
    template_string = template_string.replace('{cmdlowercase}', new_cmd_lower_case)
    template_string = template_string.replace('{cmd}', new_cmd_title)
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
        print("Commit new files to git.")
        print("Check /buddev in a few minutes for new command.")
        delete_backup_entry_point_file()
    else:
        print("Don't commit new files to git.")
        print("Restore backup file.")


if __name__ == '__main__':
    main()