#!/usr/bin/env bash

# As administrator, go to the following and set your keys
# https://app.datadoghq.com/account/settings#api
#DD_API_KEY="89ea33787f048a6420e97bce5372cc7f"  # deprecated on 2016-07-09   -Kevin
# DD_API_KEY="7efc8c58cf88c9b3c2779506919aa1f4" # deprecate on 2017-04-26 migrating to team account -Jeff
DD_API_KEY="031f8da65c05878746bac9292d46dfe8"
[ -z "$TAG" ] && echo "Error: Please pass in env TAG" && exit 1
set -e
set -x

if [ `id -u` -ne 0 ]; then
    echo "ERROR: Must run as root(id=0)"
    exit 1
fi

# See the standard Datadog configs here:
# https://app.datadoghq.com/account/settings#agent/aws
if [ -e '/usr/bin/yum' ]; then
    if [ -e '/usr/local/bin/pkg/datadog.repo.cfg' ]; then
        # local Datadog RPM exists, use that
        yum --nogpgcheck -y -q localinstall /usr/local/bin/pkg/datadog-agent-*.x86_64.rpm
    else
        # TODO(kevin): remove this external get mechanism after Q3 2016
        # This is a Debian/AWS distribution
        cat > /etc/yum.repos.d/datadog.repo <<EOL
[datadog]
name = Datadog, Inc.
baseurl = https://yum.datadoghq.com/rpm/x86_64/
enabled=1
gpgcheck=0
gpgkey=https://yum.datadoghq.com/DATADOG_RPM_KEY.public
EOL
        # The key is derived from https://app.datadoghq.com/account/settings#agent/aws

        # Installation may accidentally start datadog-agent, therefore don't create an
        # actual config file yet...
        # Note that you may revert back to 1:5.1.1-546 because 1:5.2.0-1 has an unstable supervisord.
        # Peg the version and update when necessary: yum --showduplicates list datadog-agent
        mkdir -p /etc/dd-agent
        yum makecache
        yum install -y -q datadog-agent
    fi
else
    # assume this is Ubuntu
    echo 'deb http://apt.datadoghq.com/ stable main' > /etc/apt/sources.list.d/datadog.list
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys C7A7DA52
    apt-get update -y && sudo apt-get install -y datadog-agent
fi

#TAG="dockerbase,ecs:$ECS_BOOT_VERSION"
ddconfig="/etc/dd-agent/datadog.conf"
sed -e "s/api_key:.*/api_key: $DD_API_KEY/g" \
    -e "s/^# *tags:.*/tags: ${TAG}/g" \
    -e "s/^# *collect_ec2_tags:.*/collect_ec2_tags: yes/g" \
    -e "s/^# *collect_instance_metadata:.*/collect_instance_metadata: yes/g" \
    -e "s/^# *bind_host:.*/bind_host: 0.0.0.0/g" \
    $ddconfig.example > $ddconfig
#  sed -i 's/# *collect_images_stats:.*/collect_images_stats: true/g' $ddconfig &&\

# Datadog requires looking at /host/* path:
# https://github.com/tutumcloud/datadog-agent/issues/1
# Make sure to start docker(S20) BEFORE datadog(S85), or else warnings will occur.
if [[ "$TAG" =~ 'ecs' ]]; then
    #  sed -i 's/# *collect_container_size:.*/collect_container_size: true/g' $ddconfig
    dockerconfig="/etc/dd-agent/conf.d/docker_daemon.yaml"
    # Add dd-agent to the docker group in order to fetch statistics
    usermod -G docker dd-agent
    sed -e "s/# collect_labels_as_tags:.*/collect_labels_as_tags: [\"serviceName\", \"com.amazonaws.ecs.container-name\"]/g" $dockerconfig.example > $dockerconfig
    mkdir -p /host/proc/   && ln -s /proc/mounts   /host/proc/
    mkdir -p /host/sys/fs/ && ln -s /sys/fs/cgroup /host/sys/fs/
    mv /etc/rc2.d/S95docker /etc/rc2.d/S20docker
    mv /etc/rc3.d/S95docker /etc/rc3.d/S20docker
    mv /etc/rc4.d/S95docker /etc/rc4.d/S20docker
    mv /etc/rc5.d/S95docker /etc/rc5.d/S20docker
fi


# TODO(kevin): remove code below when all Dockerized
# Create Tomcat logging if enabled
if [ -n "$TOMCAT" -a "$TOMCAT" = 1 ]; then
    tcyaml="/etc/dd-agent/conf.d/tomcat.yaml"
    cp $tcyaml.example $tcyaml
    sed -i 's/^ *- *host:.*/  - host: localhost/g' $tcyaml
    sed -i 's/^ *port:.*/    port: 7199/g' $tcyaml
fi

# TODO: take care of cassandra username/password when it is required
case $TAG in
  *cassandra*)
    echo "Creating cassandra config (TAG=$TAG)"
    ddconfig="/etc/dd-agent/conf.d/cassandra.yaml"
    cassandra_name=`echo $TAG | sed -e 's/cassandra[_\-]*//'`
    cp $ddconfig.example $ddconfig
    sed -i 's/^ *- *host:.*/  - host: localhost/' $ddconfig
    sed -i 's/^ *port:.*/    port: 7199/' $ddconfig
    sed -i 's/^# *name: *cassandra_instance.*/    name: ${cassandra_name}/' $ddconfig
    ;;
  *haproxy*)
    ddconfig='/etc/dd-agent/conf.d/haproxy.yaml'
    # Note that the haproxy?stats convention (with the questionmark) is an old convention
    # used in Omega haproxy. Titan convention uses haproxy/stats convention (with slash).
    [ -z "$HAPROXY_STATS_URL" ] && HAPROXY_STATS_URL='http://localhost:8080/haproxy?stats'
    echo "Creating haproxy config (TAG=$TAG, HAPROXY_STATS_PORT=$HAPROXY_STATS_URL)"
    sed -e "s@^ .*url: http.*@  - url: $HAPROXY_STATS_URL@" $ddconfig.example > $ddconfig
    ;;
esac

if [ "$NO_START_DATADOG" != 1 ]; then
    /etc/init.d/datadog-agent start
fi
