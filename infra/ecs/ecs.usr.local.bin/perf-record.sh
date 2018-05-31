#!/bin/bash
echo "Looking for PID for $1"
PID=$(docker inspect --format '{{.State.Pid}}' $1)
echo Recording perf data on $PID
perf record -F 99 -g -p $PID -- sleep $2
echo Getting JVM symbol table from $1
docker cp /util/perf-map-agent $1:/util
docker exec $1 /util/perf-map-agent/bin/create-java-perf-map.sh 1
JDK_DIR=$(docker exec $1 ls /opt | grep jdk)
mkdir -p /opt/$JDK_DIR/jre/lib/amd64/server
docker cp $1:/tmp/perf-1.map /tmp/perf-$PID.map
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/server/libjvm.so /opt/$JDK_DIR/jre/lib/amd64/server/libjvm.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libzip.so /opt/$JDK_DIR/jre/lib/amd64/libzip.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libverify.so /opt/$JDK_DIR/jre/lib/amd64/libverify.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libjava.so /opt/$JDK_DIR/jre/lib/amd64/libjava.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libnio.so /opt/$JDK_DIR/jre/lib/amd64/libnio.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libnet.so /opt/$JDK_DIR/jre/lib/amd64/libnet.so
docker cp $1:/opt/$JDK_DIR/jre/lib/amd64/libsunec.so /opt/$JDK_DIR/jre/lib/amd64/libsunec.so
perf script | /usr/local/flamegraph/stackcollapse-perf.pl --kernel | /usr/local/flamegraph/flamegraph.pl --color=java --hash > perf-$PID.svg
rm /tmp/perf-$PID.map
rm perf.data