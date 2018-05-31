#!/usr/bin/env bash

# As administrator, go to the following and set your keys
# https://app.datadoghq.com/account/settings#api
#DD_API_KEY="89ea33787f048a6420e97bce5372cc7f"  # deprecated on 2016-07-09   -Kevin
# DD_API_KEY="7efc8c58cf88c9b3c2779506919aa1f4" # deprecate on 2017-04-26 migrating to team account -Jeff
DD_API_KEY="031f8da65c05878746bac9292d46dfe8"
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

ddconfig="/etc/dd-agent/datadog.conf"
sed -e "s/api_key:.*/api_key: $DD_API_KEY/g" \
    -e "s/^# *collect_ec2_tags:.*/collect_ec2_tags: yes/g" \
    -e "s/^# *collect_instance_metadata:.*/collect_instance_metadata: yes/g" \
    -e "s/^# *bind_host:.*/bind_host: 0.0.0.0/g" \
    $ddconfig.example > $ddconfig

# install redis plugin
ddconfig='/etc/dd-agent/conf.d/redisdb.yaml'
# expecting redis to be installed at localhost and 6379
cat $ddconfig.example > $ddconfig

if [ "$NO_START_DATADOG" != 1 ]; then
    /etc/init.d/datadog-agent start
fi
