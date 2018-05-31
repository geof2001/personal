#!/usr/bin/env python
import os
import sys
import re

AWS_ACCESS_KEY_ID = None
AWS_SECRET_ACCESS_KEY = None
ROLE_ARN = None
SOURCE_PROFILE = None


def get_aws_key_and_secret(fd):
    global AWS_SECRET_ACCESS_KEY
    global AWS_ACCESS_KEY_ID
    global ROLE_ARN
    global SOURCE_PROFILE
    set_now = False

    for line in fd:
        if re.search(r'^\s*#', line):
            continue

        if acct is None:
            # just list options available
            m = re.search(r'\[(profile\s+)?(\w+)\]', line, re.IGNORECASE)
            if m:
                print '# ' + m.group(2)
            continue

        if re.search(r'\[(profile\s+)?%s\]' % acct, line, re.IGNORECASE):
            set_now = True

        if (AWS_SECRET_ACCESS_KEY is not None and
                AWS_ACCESS_KEY_ID is not None):
            return  # done, return
        if set_now:
            m = re.search(r'^\s*aws_access_key_id\s*=\s*(.+)', line, re.I)
            if m:
                AWS_ACCESS_KEY_ID = m.group(1)
            m = re.search(r'^\s*aws_secret_access_key\s*=\s*(.+)', line, re.I)
            if m:
                AWS_SECRET_ACCESS_KEY = m.group(1)
            m = re.search(r'^\s*role_arn\s*=\s*(.+)', line, re.I)
            if m:
                ROLE_ARN = m.group(1)
            m = re.search(r'^\s*source_profile\s*=\s*(.+)', line, re.I)
            if m:
                SOURCE_PROFILE = m.group(1)


if __name__ == '__main__':
    acct = sys.argv[1] if len(sys.argv) == 2 else None
    cred_file = "%s/.aws/credentials" % os.environ['HOME']
    if os.path.exists(cred_file):
        with open(cred_file) as fd:
            get_aws_key_and_secret(fd)

    conf_file = "%s/.aws/config" % os.environ['HOME']
    if AWS_ACCESS_KEY_ID is None or AWS_SECRET_ACCESS_KEY is None:
        if os.path.exists(conf_file):
            with open(conf_file) as fd:
                get_aws_key_and_secret(fd)

    if acct is not None:
        if ROLE_ARN and SOURCE_PROFILE:
            print """export AWS_DEFAULT_PROFILE={acct}
unset AWS_ACCESS_KEY_ID
unset AWS_ACCESS_KEY
unset AWS_SECRET_ACCESS_KEY
unset AWS_SECRET_KEY""".format(acct=acct)
        else:
            print """export AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_ID}
export AWS_ACCESS_KEY={AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY={AWS_SECRET_ACCESS_KEY}
export AWS_SECRET_KEY={AWS_SECRET_ACCESS_KEY}
unset AWS_DEFAULT_PROFILE""".format(
                AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID,
                AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY)
        if not acct:
            print "unset AWS_DEFAULT_PROFILE"
