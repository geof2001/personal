# TODO (manoj) verify and use - currently not used

#!/usr/bin/env bash
#
# Bastion initialization script, this is run only once.
#
set -e
set -x

BINPATH='/usr/local/bin'
LOGPATH='/var/log/ecs-boot/'

mkdir -p $LOGPATH

# parallelize long running tasks with by backgrounding with nohup
nohup sh -c "$BINPATH/update_ssh_authorized_keys.sh" 2&>1 >> $LOGPATH/update_ssh_authorized_keys.log &