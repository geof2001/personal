#!/usr/bin/env bash

set -e
set -x

HAPROXY_TGZ='http://www.haproxy.org/download/1.6/src/haproxy-1.6.10.tar.gz'

# Install haproxy if it doesn't already exit
if [ -e /usr/sbin/haproxy ]; then
    echo "WARNING: /usr/sbin/haproxy already exists, skip custom installation..."
else
    mkdir -p haproxy-installation
    cd haproxy-installation
    if [ -e "/usr/local/bin/pkg/haproxy.tar.gz" ]; then
        # if the package already exists, no need to curl
        tar -xzf /usr/local/bin/pkg/haproxy.tar.gz
    else
        # TODO(kevin): remove this external get mechanism after Q3 2016
        curl -o /tmp/haproxy.tar.gz $HAPROXY_TGZ
        tar -xzf /tmp/haproxy.tar.gz
        rm -f /tmp/haproxy.tar.gz
    fi
    # the '*' wildcard below is universal for any versioned pathname
    cd haproxy-*
    make TARGET=linux2628 USE_OPENSSL=yes USE_ZLIB=yes
    cp haproxy /usr/sbin/haproxy
    cp examples/haproxy.init /etc/init.d/haproxy
    # get out of haproxy-installation/haproxy-1.x.y/
    cd ../..
    rm -rf haproxy-installation

    chmod a+x /etc/init.d/haproxy
    mkdir -p /etc/haproxy

    cat <<EOT >> /etc/haproxy/haproxy.cfg
#uninitialized
frontend http-in
timeout client 50000
    mode http
    bind *:9000
    stats enable
    stats uri /haproxy/stats
EOT
fi

chkconfig --add haproxy
chkconfig --level 345 haproxy on


RSYSLOG_CFG=/etc/rsyslog.conf
if [ -z "$(grep -i '#$ModLoad imudp' $RSYSLOG_CFG)" ]; then
    echo '$ModLoad imudp' >> $RSYSLOG_CFG
else
    sed -i 's/#$ModLoad imudp/$ModLoad imudp/' $RSYSLOG_CFG
fi

if [ -z "$(grep -i '#$UDPServerRun 514' $RSYSLOG_CFG)" ]; then
    echo '$UDPServerRun 514' >> $RSYSLOG_CFG
else
    sed -i 's/#$UDPServerRun 514/$UDPServerRun 514/' $RSYSLOG_CFG
fi

sed -i 's/\*.info;mail.none;authpriv.none;cron.none/\*.info;local2.!=info;mail.none;authpriv.none;cron.none/' $RSYSLOG_CFG

echo '$UDPServerAddress 127.0.0.1' >> $RSYSLOG_CFG
echo 'local2.* /var/log/haproxy' >> $RSYSLOG_CFG


# logrotate for haproxy
LOGROTATE_CONF=/etc/logrotate.conf
cp $LOGROTATE_CONF "$LOGROTATE_CONF.bak"
sed -e 's/^weekly/daily/' \
    -e 's/^#compress/compress/' \
    -e 's/^rotate 4/rotate 14/' \
    "$LOGROTATE_CONF.bak" > $LOGROTATE_CONF
#sed -i 's/\/var\/log\/messages/\/var\/log\/messages\n\/var\/log\/haproxy/' /etc/logrotate.d/syslog

LOGROTATE_D_HAPROXY='/etc/logrotate.d/haproxy'
cat <<EOT > $LOGROTATE_D_HAPROXY
/var/log/haproxy {
    size 250M
    rotate 99
    missingok
    notifempty
    daily
    create 0644 root root
    compress
    postrotate
        /bin/kill -HUP \`cat /var/run/syslogd.pid 2> /dev/null\` 2> /dev/null || true
    endscript
}
EOT

cat <<EOT > /etc/cron.hourly/haproxy
#!/bin/sh
# This is automatically generated from install_local_haproxy.sh
/usr/sbin/logrotate $LOGROTATE_D_HAPROXY --force >/dev/null 2>&1
EXITVALUE=\$?
if [ \$EXITVALUE != 0 ]; then
    /usr/bin/logger -t logrotate "ALERT exited abnormally with [\$EXITVALUE]"
fi
exit 0
EOT
chmod 0755 /etc/cron.hourly/haproxy

/etc/init.d/rsyslog restart
/etc/init.d/haproxy start
