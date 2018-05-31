"""Doing some quick tests to replace pytz with pendulum"""
from datetime import datetime
import pytz
import pendulum

### pytz methods to replace here ###


def get_prop_table_time_format():
    """Get timestamp in format used in prop dynamo tables.

    Example: January 19, 2018 - 09:55:48
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%B %d, %Y - %H:%M:%S")
    return time


def get_dynamo_backup_name_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%Y-%b-%d-%H%M")
    return time


def get_build_info_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = datetime.now(
        tz=pytz.utc
    ).astimezone(
        pytz.timezone('US/Pacific')
    ).strftime("%Y%m%d")
    return time

### pendulum equivalent here ###

def pendulum_prop_table_time_format():
    """Get timestamp in format used in prop dynamo tables.

    Example: January 19, 2018 - 09:55:48
    """
    time = pendulum.now('US/Pacific').strftime("%B %d, %Y - %H:%M:%S")
    return time


def pendulum_dynamo_backup_name_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = pendulum.now('US/Pacific').strftime("%Y-%b-%d-%H%M")
    return time


def pendulum_build_info_time_format():
    """Get timestamp in format for dynamo table backups.
    The name is restricted to regular expression pattern: [a-zA-Z0-9_.-]+

    Will be in this format: 2018-jan-19-0955
    """
    time = pendulum.now('US/Pacific').strftime("%Y%m%d")
    return time


def test_pendulum_vs_pytz():

    print('## prop_table_time_format ##')
    pyt1 = get_prop_table_time_format()
    pen1 = pendulum_prop_table_time_format()

    print('pytz: {}\npend: {}'.format(pyt1,pen1))

    print('## prop_table_time_format ##')
    pyt2 = get_dynamo_backup_name_time_format()
    pen2 = pendulum_dynamo_backup_name_time_format()

    print('pytz: {}\npend: {}'.format(pyt2, pen2))

    print('## prop_table_time_format ##')
    pyt3 = get_build_info_time_format()
    pen3 = pendulum_build_info_time_format()

    print('pytz: {}\npend: {}'.format(pyt3, pen3))


if __name__ == '__main__':
    test_pendulum_vs_pytz()




