#!/usr/bin/env bash

set -e
set -x

#update sysctl.conf
/tmp/updatesysctl.sh

# install redis
/tmp/redis-install-script.sh

#install data-dog
/tmp/install-datadog.sh

#add access to the machines
BINPATH='/usr/local/bin'
LOGPATH='/var/log/ec2-boot'
mkdir -p $LOGPATH
# parallelize long running tasks with by backgrounding with nohup
nohup sh -c "$BINPATH/update_ssh_authorized_keys.sh" 2&>1 >> $LOGPATH/update_ssh_authorized_keys.log &
# add logon to the machines created from these amis
CRONTMP="/tmp/tmp.cron.$$"
cat > $CRONTMP <<EOL
*/10 * * * * /usr/local/bin/update_ssh_authorized_keys.sh
EOL
crontab $CRONTMP
rm $CRONTMP
