#!/usr/bin/env bash

set -e

# Notes:
# By default, the Java application needs to bind to port 8080
# and to expose 7199 as the JMX port
JMX_PORT=7199

AWS_URL='http://169.254.169.254/latest'
_iam_info=$(curl -m 2 -sf $AWS_URL/meta-data/iam/info || true)
_availability_zone=$(curl -m 2 -sf $AWS_URL/meta-data/placement/availability-zone || true)
export ACCOUNT_NUM=$(echo $_iam_info | sed -e 's/.*arn:aws:iam:://' -e 's/:instance-profile.*//')
export REGION=$(echo $_availability_zone | sed -e 's/[a-zA-Z]$//')  # us-east-1, us-west-2, ...
IAM_ROLE=$(echo $_iam_info | sed -e 's|.*instance-profile/||' -e 's|".*||')
REGION=$(echo $_availability_zone | sed -e 's/[a-zA-Z]$//')  # us-east-1, us-west-2, ...
# override default HOSTNAME inside Docker (because Docker hostname is not very useful)
HOSTNAME=$(curl -m 2 -sf $AWS_URL/meta-data/public-hostname || true)
PRIVIP=$(curl -m 2 -sf $AWS_URL/meta-data/local-ipv4 || true)
INSTANCE_ID=$(curl -m 2 -sf $AWS_URL/meta-data/instance-id || true)
INSTANCE_TYPE=$(curl -m 2 -sf $AWS_URL/meta-data/instance-type || true)

# Get machine information to generate JAVA_OPTS
if [ -n "$JAVA_MAX_MB" ]; then
  total_mb=`echo $JAVA_MAX_MB | sed -e 's/mb*//i'`
  jvm_mem="-Xmx`echo $(($total_mb * 95 / 100))`m"
  stack_mem="-Xms`echo $(($total_mb / 3))`m"
else
  total_mb=`cat /proc/meminfo | grep MemTotal | sed -e 's/MemTotal: *\([0-9]*\) kB/\1/i'`
  total_mb=`echo $(($total_mb / 1000))`
  jvm_mem=''
  stack_mem=''
fi

gc_logs="/var/log/gc.log"
# create dir to store gc logs
if [ $BRANCH = "mount-efs" ]; then
  container_id=$( hostname )
  echo "MONITOR_SERVICE_NAME is $MONITOR_SERVICE_NAME"
  echo "container is $container_id"
  efs_path="/efs/$SERVICE_NAME/$MONITOR_SERVICE_NAME/$container_id"
  mkdir -p $efs_path

  export EFS_DIR=$efs_path
  gc_logs="$efs_path/gc.log"


  # docker0 ip for introspection
  DOCKER0_IP=$(ip route|head -n 1|sed -r 's/default via ([0-9.]+).*$/\1/')
  export DOCKER0_IP="$DOCKER0_IP"
fi

JAVA_OPTS=`echo $JAVA_OPTS | sed -e 's/\"/\\\"/g'`
JAVA_OPTS="$jvm_mem $stack_mem -Dlog4j.configurationFile=$CATALINA_BASE/log4j2.xml -XX:+PreserveFramePointer -XX:+HeapDumpOnOutOfMemoryError -XX:+ExitOnOutOfMemoryError -XX:-OmitStackTraceInFastThrow -verbose:gc -Xloggc:$gc_logs -XX:+UseGCLogFileRotation -XX:NumberOfGCLogFiles=2 -XX:GCLogFileSize=100M -XX:+PrintGCDetails -XX:+PrintGCDateStamps $JAVA_OPTS"
JAVA_OPTS="-Djava.awt.headless=true -Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=$JMX_PORT -Dcom.sun.management.jmxremote.ssl=false -Dcom.sun.management.jmxremote.authenticate=false -Dfile.encoding=UTF-8 $JAVA_OPTS"

# Assume every Docker host has a statsd running
if [ -z "$STATSD_HOST" ]; then
  STATSD_HOST=`netstat -nr | grep '^0\.0\.0\.0' | awk '{print $2}'`
fi
AWS_XRAY_DAEMON_ADDRESS=${STATSD_HOST}:2000

webapps_path="$CATALINA_BASE/webapps"
mkdir -p $CATALINA_BASE/webapps

cat <<EOT >> $webapps_path/build.txt
Checkin: $P4_CHANGELIST
SERVER_NAME: $SERVICE_NAME
SERVICE_NAME: $SERVICE_NAME
BRANCH: $BRANCH
BUILD_NUMBER: $BUILD_NUMBER
BUILD_URL: $BUILD_URL
BUILD_TIMESTAMP: $BUILD_TIMESTAMP
VERSION: $VERSION
EOT

# create an expanded info.txt
tmp_env="/tmp/env.txt"
sed -e 's/: /=/' $webapps_path/build.txt > $tmp_env
cat <<EOT >> $tmp_env
INSTANCE_ID=$INSTANCE_ID
INSTANCE_TYPE=$INSTANCE_TYPE
ACCOUNT_NUM=$ACCOUNT_NUM
REGION=$REGION
IAM_ROLE=$IAM_ROLE
REGION=$REGION
HOSTNAME=$HOSTNAME
PRIVIP=$PRIVIP
CATALINA_OPTS="$CATALINA_OPTS"
STATSD_HOST=$STATSD_HOST
AWS_XRAY_DAEMON_ADDRESS: $AWS_XRAY_DAEMON_ADDRESS
EOT

env | egrep '^(SERVICE|JAVA)' >> $tmp_env
sort $tmp_env | uniq > $webapps_path/info.txt
rm -f $tmp_env

# output to stdout for debugging
cat $webapps_path/info.txt

echo "Starting rotate_logs_and_push_to_s3.py (SERVICE_NAME=$SERVICE_NAME)..."
/usr/local/bin/rotate_logs_and_push_to_s3.py /var/log/gc.log.1 2>&1 > /dev/null &

# this requires "Privileged: true" to work for container
#if [ $SERVICE_NAME = "datafetcher" ]; then
#    sysctl -w net.ipv4.tcp_keepalive_time=200 net.ipv4.tcp_keepalive_intvl=200 net.ipv4.tcp_keepalive_probes=5
#fi

echo "Starting SparkJava with ${jvm_mem} (out of ${total_mb}MB). JAVA_HOME=$JAVA_HOME"

set -a
# Variables below are needed for Java program
export SERVER_NAME="$SERVICE_NAME"
export SERVICE_NAME="$SERVICE_NAME"
export SERVICE_VERSION="$VERSION"
export VERSION="$VERSION"
export JAVA_OPTS="$JAVA_OPTS"
export CATALINA_OPTS="$CATALINA_OPTS"
export STATSD_HOST="$STATSD_HOST"
export AWS_XRAY_DAEMON_ADDRESS="$AWS_XRAY_DAEMON_ADDRESS"

env | sort > /tmp/debug_env.log  # this is extremely useful, please do not remove
if [ -e "/usr/$SERVICE_NAME/bin/" ]; then
    exec $(find /usr/$SERVICE_NAME/bin/ -type f -name "*")
else
    echo "ERROR: Fatal warning, unable to find /usr/$SERVICE_NAME/bin/"
    exit 1
fi
