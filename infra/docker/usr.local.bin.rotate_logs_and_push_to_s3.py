#!/usr/bin/env python
#
# This script rotates "live" continuous log files by doing
# 1) copy
# 2) truncate
#
# It then moves the file into S3 bucket. This will also deal with
# wildcard log files, and never touching the latest wildcard log files.

import datetime
import glob
from optparse import OptionParser
import os
import re
import socket
import subprocess
import sys
import time
import urllib2


PARSER = OptionParser()
PARSER.add_option('--maximum-file-size', dest='max_file_size',
                  default=1000000,
                  type='int',
                  help='The size of file needs to be before rotating')
PARSER.add_option('--wait-seconds', dest='wait_seconds',
                  default=60,
                  type='int',
                  help='How many seconds to wait between rotate')
PARSER.add_option('--force-wait-seconds', dest='force_wait_seconds',
                  default=600,
                  type='int',
                  help='How many seconds to wait between rotate')
PARSER.add_option('--debug', dest='debug',
                  default=False,
                  action="store_true",
                  help='Debug mode (more verbose)')


S3_BUCKET_PREFIX = 's3://roku-sr-logs'

socket.setdefaulttimeout(5)  # timeout is in seconds
AWS_URL='http://169.254.169.254/latest'
_iam_info = urllib2.urlopen(
    AWS_URL + '/meta-data/iam/info').read().replace('\n', ' ')
ACCOUNT_NUM = re.sub('.*arn:aws:iam::', '',
                     re.sub(':instance\-profile.*', '', _iam_info))
EC2_INSTANCE_ID = urllib2.urlopen(AWS_URL + '/meta-data/instance-id').read()
AZ = urllib2.urlopen(AWS_URL + '/meta-data/placement/availability-zone').read()
REGION = re.sub('[a-z]+$', '', AZ, flags=re.I)

LAST_PROCESSED_TIME = {}
SERVER_NAME = os.environ.get('SERVER_NAME', os.environ.get('SERVICE_NAME', ''))


def _process(fname):
    file_size = os.path.getsize(fname)
    if file_size == 0:
        return

    dt = datetime.datetime.now()
    datestr = dt.strftime("%Y%m%d_%H%M%S")
    s3str = dt.strftime("%Y/%m/%d/%H")
    
    dirfname = os.path.dirname(fname)
    basefname = os.path.basename(fname)

    fullfname = (
        dirfname + '/' +
        (SERVER_NAME + '.' if SERVER_NAME else '') +
        datestr +
        '.' + EC2_INSTANCE_ID +
        '.' + basefname)
    cmds = (
        'cp {fname} {fullfname}'
        '; truncate -s0 {fname}'
        '; gzip -2 {fullfname}'
        '; aws s3 mv --quiet'
        ' {fullfname}.gz'
        ' {S3_BUCKET_PREFIX}-{account_num}-{region}/{s3str}/'.format(
            fname=fname,
            fullfname=fullfname,
            datestr=datestr,
            account_num=ACCOUNT_NUM,
            region=REGION,
            s3str=s3str,
            S3_BUCKET_PREFIX=S3_BUCKET_PREFIX
        ))

    for cmd in cmds.split(';'):
        ret_code = subprocess.call(cmd, shell=True)
        if ret_code != 0:
            print "ERROR: Unable to execute %s" % cmd

    LAST_PROCESSED_TIME[fname] = time.time()


def process(options, file_or_wildcardfile):
    if '*' in file_or_wildcardfile:
        files = glob.glob(file_or_wildcardfile)
        latest_file = None
        latest_file_timestamp = 0
        for fname in files:
            t = time.ctime(os.path.getmtime(fname))
            if t > latest_file_timestamp:
                latest_file_timestamp = t
                latest_file = fname
        for fname in files:
            if fname == latest_file:
                continue
            if options.debug:
                print "Processing %s(%s)" % (file_or_wildcardfile, fname)
            _process(fname)
            os.remove(fname)

    else:
        if not os.path.exists(file_or_wildcardfile):
            return
        file_size = os.path.getsize(file_or_wildcardfile)
        if options.debug:
            print("Checking for size and time stamp %d/%d" %
                  (time.time(), LAST_PROCESSED_TIME[file_or_wildcardfile]))
        if (file_size > options.max_file_size or
                (time.time() >
                 LAST_PROCESSED_TIME[file_or_wildcardfile] +
                 options.force_wait_seconds)):
            if options.debug:
                print "Processing %s" % file_or_wildcardfile
            _process(file_or_wildcardfile)


if __name__ == '__main__':
    (options, files) = PARSER.parse_args()

    ps = subprocess.Popen(
        "ps auxwww|grep rotate_logs_and_push_to_s3|grep -v grep",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    ps = ps.communicate()[0].rstrip().split('\n')
    if len(ps) >= 2:
        if options.debug:
            print "Another process is already running, exiting..."
        sys.exit(1)

    if len(files) == 0:
        print "ERROR: Please specify 1 or more log files to rotate"
        sys.exit(1)
    if options.debug:
        print "Checking for files %s" % files
    for fname in files:
        LAST_PROCESSED_TIME[fname] = time.time()
    while True:
        for fname in files:
            process(options, fname)
        time.sleep(options.wait_seconds)
        if options.debug:
            print "Sleeping..."