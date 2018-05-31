#!/usr/bin/env bash
#
# ECS initialization script, this is run only once.
#
set -e
set -x

BINPATH='/usr/local/bin'
LOGPATH='/var/log/ecs-boot/'

mkdir -p $LOGPATH

# parallelize long running tasks with by backgrounding with nohup
nohup sh -c "$BINPATH/update_ssh_authorized_keys.sh" 2&>1 >> $LOGPATH/update_ssh_authorized_keys.log &

# Blocking installation as they are critical for later scripts
# bc is needed for add_swap.sh
# java is needed for datadog
yum install -y bc java-1.8.0-openjdk gcc aws-cfn-bootstrap perf

#install flamegraph tool if included
if [ -e "/usr/local/bin/pkg/flamegraph.tar.gz" ]; then
        # if the package already exists, no need to curl
        tar -C /usr/local -xzf /usr/local/bin/pkg/flamegraph.tar.gz
fi

#install glibc compat library that is included in the alpine docker containers
#this is needed for perf analysis so symbol tables are accessible to perf and flamegraph tool
curl -Ls https://s3.amazonaws.com/sr-load-test-resources/glibc-bin-2.25.tar.gz > /tmp/glibc-bin-2.25.tar.gz
tar -C / -xzf /tmp/glibc-bin-2.25.tar.gz
curl -Ls https://s3.amazonaws.com/sr-load-test-resources/glibc-bin-2.21.tar.gz > /tmp/glibc-bin-2.21.tar.gz
tar -C / -xzf /tmp/glibc-bin-2.21.tar.gz
rm -f /tmp/glibc-bin-2.25.tar.gz
rm -f /tmp/glibc-bin-2.21.tar.gz
curl -Ls https://s3.amazonaws.com/sr-load-test-resources/perf-map-agent.tar.gz > /tmp/perf-map-agent.tar.gz
mkdir /util
tar -C /util -xzf /tmp/perf-map-agent.tar.gz
rm -f /tmp/perf-map-agent.tar.gz

echo "
# Speed up ssh by turning off DNS lookup into the machine
UseDNS=no" >> /etc/ssh/sshd_config && /etc/init.d/sshd restart

nohup sh -c "$BINPATH/install_local_haproxy.sh" 2&>1 >> $LOGPATH/install_local_haproxy.log &
# bash shell update, etc...
nohup sh -c "$BINPATH/setup_environments.sh" 2&>1 >> $LOGPATH/setup_environments.log &

# below binaries are extremely useful for debugging, please leave it for now:
nohup sh -c "sleep 10; yum install -y tmux htop telnet" 2&>1 >> $LOGPATH/ecs-install.log &
nohup sh -c "sleep 60; $BINPATH/add_swap.sh" 2&>1 >> $LOGPATH/add_swap.log &

# Periodically update datadog-agent when new JMX services are available
CRONTMP="/tmp/tmp.cron.$$"
cat > $CRONTMP <<EOL
30 2 * * * /usr/local/bin/periodic_cleanup.py
*/10 * * * * /usr/local/bin/update_ssh_authorized_keys.sh
* * * * * for i in 0 1 2; do /usr/local/bin/reload_haproxy.sh & sleep 14; done; /usr/local/bin/reload_haproxy.sh
EOL
if [ "$EXTERNAL_HA_PROXY" != "true" ]; then
cat >> $CRONTMP <<EOL
# Automatically build entries on /etc/dd-agent/conf.d/*.yaml to monitor containers (haproxy, jmx, ...)
* * * * * /usr/local/bin/update_datadog_on_ecs.py
EOL
fi
crontab $CRONTMP
rm $CRONTMP

if [ -n "$EFS_ID" ]; then
mkdir /efs-rsync
echo "$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone).${EFS_ID}.efs.${AWS_REGION}.amazonaws.com:/ /efs-rsync nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 0 0" >> /etc/fstab
mount -a -t nfs4
fi

blocking_pull() {
    IMG_PULLED=0
    while [ ${IMG_PULLED} -eq 0 ]; do
        exit_code=0
        docker pull $1 || exit_code=$?
        if [ ${exit_code} -eq 0 ]; then
            IMG_PULLED=1
            echo "Successfully pulled $1"
        else
            echo "Couldn't pull $1. Sleeping 1 second and trying again..." && sleep 1
        fi
    done
}

# Restart docker 1) because it's needed for EFS in batch cluster and 2) to minimize race condition changes with docker pull
service docker restart
sleep 1

eval $(aws ecr get-login --registry-id 638782101961 --region us-east-1 --no-include-email)

if [ -n "$XRAY_IMG" ]; then
    docker run --name xray \
        -p 2000:2000/udp \
        --log-driver=awslogs --log-opt awslogs-group=/svc/xray \
        -d --restart=always \
        ${XRAY_IMG} &> $LOGPATH/x-ray.log
fi

blocking_pull $GATEWAY_IMG
# At this point, registry on port 9002 should be up and running already
if [ "$EXTERNAL_HA_PROXY" = "true" ]; then
    # datadog automatically convert all tags into lower case (HAProxy=haproxy):
    nohup sh -c "TAG='servicename:exthaproxy,version:$ECS_BOOT_VERSION' \
        HAPROXY_STATS_URL='http://localhost:8442/haproxy/stats' \
        $BINPATH/install_datadog.sh" 2&>1 >> $LOGPATH/install_datadog.log &

    docker run --name gateway \
        --env HTTP_PORT=8442 --env HTTPS_PORT=8443 --env HTTPS_PROXY_PORT=9443 \
        --env HAPROXY_CONFIG=externalha \
        --env HTTPS_VISIBLE_TAG=httpsVisible \
        --env SSL_CONFIG_KEY=$SSL_CONFIG_KEY \
        --env EMBEDDED_HAPROXY=false \
        --env INVISIBLE_TAG=jwtTokenSecurity \
        --env SERVICE_DISCOVERY_TABLE=$SERVICE_DISCOVERY_TABLE \
        --env SERVICE_DISCOVERY_COUNTER_TABLE=$SERVICE_DISCOVERY_COUNTER_TABLE \
        --log-driver=awslogs --log-opt awslogs-group=/svc/ext-gateway \
        -d --restart=always \
        -v /etc/haproxy:/tmp/haproxy ${GATEWAY_IMG} &> $LOGPATH/run-gateway.log
else
    # make sure you pass in "ecs" tag so the script will create a specific docker config
    nohup sh -c "TAG='dockerbase,ecs:$ECS_BOOT_VERSION' \
        $BINPATH/install_datadog.sh" 2&>1 >> $LOGPATH/install_datadog.log &

    blocking_pull $REGISTRAR_IMG
    docker run --name registrar \
        --env SERVICE_HIDDEN=true \
        --env SERVICE_DISCOVERY_TABLE=$SERVICE_DISCOVERY_TABLE \
        --env SERVICE_DISCOVERY_COUNTER_TABLE=$SERVICE_DISCOVERY_COUNTER_TABLE \
        -d --restart=always \
        -v /var/run/docker.sock:/tmp/docker.sock ${REGISTRAR_IMG} &> $LOGPATH/run-registrar.log
    docker run --name gateway \
        --env SERVICE_HIDDEN=true \
        --env EMBEDDED_HAPROXY=false \
        --env INVISIBLE_TAG=jwtTokenSecurity \
        --env SERVICE_DISCOVERY_TABLE=$SERVICE_DISCOVERY_TABLE \
        --env SERVICE_DISCOVERY_COUNTER_TABLE=$SERVICE_DISCOVERY_COUNTER_TABLE \
        --log-driver=awslogs --log-opt awslogs-group=/svc/int-gateway \
        -d --restart=always \
        -v /etc/haproxy:/tmp/haproxy ${GATEWAY_IMG} &> $LOGPATH/run-gateway.log
    echo "nohup /usr/local/bin/ec2_healthcheck_web_server.py > /var/log/healthcheck.log &" >> /etc/rc.local
fi

#sleep 20; $BINPATH/secure_machine.sh
#sleep 20; $BINPATH/disable_sudo.sh
