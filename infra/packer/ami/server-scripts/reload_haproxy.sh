#!/usr/bin/env bash
STAGE_FILE=/etc/haproxy/haproxy.stg
PRELOAD_FILE=/etc/haproxy/haproxy.new
CONFIG_FILE=/etc/haproxy/haproxy.cfg
HAPROXY=/usr/sbin/haproxy
HAPROXY_INIT=/etc/init.d/haproxy

if [ -f $STAGE_FILE ]; then
	mv -f $STAGE_FILE $PRELOAD_FILE
	DIFF=$(diff -q $PRELOAD_FILE $CONFIG_FILE)
    if [ -n "$DIFF" ]; then
        echo "New configuration file is different from previous one. Will now check whether config is valid"
		$HAPROXY -c -f $PRELOAD_FILE
		if [ $? -eq 0 ]; then
		    echo 'Reloading HA Proxy'
			cp -f $PRELOAD_FILE $CONFIG_FILE
			$HAPROXY_INIT reload
        else
            echo 'Configuration check failed - will not reload HA Proxy'
		fi
    else
        echo "New configuration is identical to previous configuration. Will take no action."
	fi
    rm -f $PRELOAD_FILE
fi

