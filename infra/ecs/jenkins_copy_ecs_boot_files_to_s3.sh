#!/usr/bin/env bash
# Copy ECS initialization scripts to S3
set -e
set -x

HAPROXY_TGZ='http://www.haproxy.org/download/1.6/src/haproxy-1.6.10.tar.gz'

ECS_BIN='ecs/ecs.usr.local.bin'
ECS_SCRIPTS='ecs/scripts'
[ ! -e 'keys' -a ! -e $ECS_BIN ] && echo "Please run this from the jenkins/ directory" && exit 1

S3_PATH='s3://roku-ecs-boot'  # make sure this is in sync with update_ssh_authorized_keys.sh
if [ -n "$1" ]; then
    DATE_PATH=$1
else
    if [ -n "$BUILD_NUMBER" ]; then
        DATE_PATH=`date +'%Y%m%d'`-jenkins-$BUILD_NUMBER
    else
        DATE_PATH=`date +'%Y%m%d_%H%M'`
    fi
fi

# all machines will pick up the latest ssh_authorized_keys
KEY_FILE=/tmp/ssh_authorized_keys.$$
grep -v '^#' keys/ssh_public_keys > $KEY_FILE
aws s3 cp $KEY_FILE $S3_PATH/ssh_authorized_keys || \
    (echo "Error in: s3 cp..." && rm -f $KEY_FILE && exit 1)
rm -f $KEY_FILE
find /tmp -type f -name 'ssh_authorized_keys.*' -mtime 2 -exec rm -f {} \; || true

DEST="$S3_PATH/$DATE_PATH"

# TODO: remove this after images are updated
aws s3 cp $ECS_BIN/initialize_ecs_at_startup.sh $DEST/run.sh

for file in \
  $ECS_SCRIPTS/disable_sudo.sh \
  $ECS_SCRIPTS/update_ssh_authorized_keys.sh \
  $ECS_SCRIPTS/setup_environments.sh \
  $ECS_SCRIPTS/add_swap.sh \
  $ECS_SCRIPTS/install_datadog.sh \
  $ECS_BIN/ec2_healthcheck_web_server.py \
  $ECS_BIN/initialize_ecs_at_startup.sh \
  $ECS_BIN/install_local_haproxy.sh \
  $ECS_BIN/perf-record.sh \
  $ECS_BIN/periodic_cleanup.py \
  $ECS_BIN/reload_haproxy.sh \
  $ECS_BIN/secure_machine.sh \
  $ECS_BIN/update_datadog_on_ecs.py; do

  fname=`basename $file`
  aws s3 cp $file $DEST/$fname || (echo "ERROR" && exit 1)
done

# download Haproxy binary
tmp="/tmp/haproxy.tar.gz.$$"
curl -o $tmp $HAPROXY_TGZ
aws s3 cp $tmp $DEST/pkg/haproxy.tar.gz
rm -f $tmp

# download FlameGraph repo and dump into S3
tmp="flamegraph"
git clone https://github.com/brendangregg/FlameGraph.git /tmp/$tmp
tar -C /tmp -czf /tmp/flamegraph.tar.gz $tmp
aws s3 cp /tmp/flamegraph.tar.gz $DEST/pkg/flamegraph.tar.gz
rm -rf /tmp/$tmp
rm -f /tmp/flamegraph.tar.gz

# download dependencies locally, dump into S3
YUMDOWNLADER=/usr/bin/yumdownloader
if [ -e $YUMDOWNLADER ]; then
    tmp="/tmp/datadog.yum.repo.$$"
    mkdir -p $tmp
    cat > $tmp/datadog.repo.cfg <<EOL
[datadog]
name = Datadog, Inc.
baseurl = https://yum.datadoghq.com/rpm/x86_64/
enabled=1
gpgcheck=0
gpgkey=https://yum.datadoghq.com/DATADOG_RPM_KEY.public
EOL
    # below downloads datadog-agent-*.x86_64.rpm and datadog-agent-*.noarch.rpm
    $YUMDOWNLADER --destdir=$tmp --config=$tmp/datadog.repo.cfg datadog-agent
    aws s3 cp --recursive $tmp/ $DEST/pkg/
    \rm -rf $tmp
else
    echo "NOTE: It is *highly* recommended that you install yumdownloader so that"
    echo "      RPM packages can be downloaded and dumped to S3 for higher reliability."
fi
