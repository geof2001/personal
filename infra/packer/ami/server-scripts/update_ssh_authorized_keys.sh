#!/usr/bin/env bash
#
# This script updates the ~/.ssh/authorized_keys
#
set -e

if [ `id -u` != 0 ]; then
    echo "ERROR: Must run this script as root(id=0)"
    exit 1
fi

S3_PATH='s3://roku-ecs-boot'  # make sure this is in sync with copy_ecs_boot_files_to_s3.sh
aws s3 cp --quiet $S3_PATH/ssh_authorized_keys /tmp/authorized_keys
if [ ! -e /tmp/authorized_keys ]; then
    exit 1
fi

if [ -e '/home/ec2-user' ]; then
    AUTHORIZED_KEYS_FILE=~ec2-user/.ssh/authorized_keys
    USERNAME='ec2-user'
else
    AUTHORIZED_KEYS_FILE=~ubuntu/.ssh/authorized_keys
    USERNAME='ubuntu'
fi

TMP_AUTH_FILE="/tmp/.authorized_keys.$$"
rm -f /tmp/.authorized_keys.*
head -1 $AUTHORIZED_KEYS_FILE >> $TMP_AUTH_FILE
cat /tmp/authorized_keys >> $TMP_AUTH_FILE
rm /tmp/authorized_keys
chown $USERNAME.$USERNAME $TMP_AUTH_FILE
chmod 0600 $TMP_AUTH_FILE
mv $TMP_AUTH_FILE $AUTHORIZED_KEYS_FILE
