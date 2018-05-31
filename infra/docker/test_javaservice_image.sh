#!/bin/sh -e
#
# You must call this script from the main/components directory!
# This script in run inside Jenkins to create a new Docker Image

set -e
set -x
[ ! -e "jenkins/docker" ] && echo "Please run this from the root of the path!" && exit 1
. ./jenkins/docker/common.sh

# ALL CAPS variables are shared. All lower case variables are suppose
# to be local (even though they are not).

tmp_docker_path="/tmp/docker.$SERVICE_NAME.$VERSION"
LOCAL_DOCKER_PATH=$tmp_docker_path
rm -rf $LOCAL_DOCKER_PATH

service_path=`echo $SERVICE_INFO | grep -Po 'SERVICE_PATH=\K[^ ]+' || echo ''`

if [ "$service_path" = '' ]; then
    if [ -e "$SERVICE_NAME/server" ]; then
        service_path="$SERVICE_NAME/server"
    fi
fi

if [ "$DOCKER_PATH" = 'jenkins/docker/sparkserver' -o "$DOCKER_PATH" = 'jenkins/docker/gateway-server-haproxy' ]; then
    BUILD_TASK="installDist"
    BUILD_WAR=0
else
    BUILD_TASK="build"
    BUILD_WAR=1
    # strict validation, ensuring users always have these files
    for file in "$service_path/src/main/resources/app.properties" \
        "$service_path/src/main/webapp/WEB-INF/web.xml"; do
        [ ! -e "$file" ] && echo "ERROR: missing $file" && exit 1
    done
fi


echo "Building service..."
if [ $BUILD_WAR = 1 ]; then
    find $service_path -name '*.war' -exec rm -f {} \;
fi

#if [ -e "/usr/local/bin/node" -o -e "/usr/bin/node" ]; then
#    API_DOC_PATH="$service_path/src/main/resources/apiDoc"
#    if [ -e "$API_DOC_PATH/input" ]; then
#        apidoc -i $API_DOC_PATH/input/ -o $API_DOC_PATH/output/
#        apidoc-markdown -p $API_DOC_PATH/output/ -o $API_DOC_PATH/output/README.md
#    fi
#fi

sh -c "\
  cd $service_path && \
  $GRADLE_CMD \
    --no-daemon \
    --refresh-dependencies \
    -Ppublish.type=release -Ppublish.buildnumber=$BUILD_NUMBER \
    clean test $BUILD_TASK"

cp -a $DOCKER_PATH $LOCAL_DOCKER_PATH/

if [ $BUILD_WAR = 1 ]; then
    # TODO: remove this as Tomcat is no longer used
    warfile_with_path=`find $service_path -name '*.war'`
    warfile=`basename $warfile_with_path`
    [ -z "$warfile" ] && echo "ERROR: Unable to find $DOCKER_PATH/.../*.war" && exit 1
    mv $warfile_with_path $LOCAL_DOCKER_PATH/ROOT.war
    sed -e "s|\$SERVICE_NAME|$SERVICE_NAME|" $DOCKER_PATH/log4j2.xml.template > $LOCAL_DOCKER_PATH/log4j2.xml
else
    mkdir $LOCAL_DOCKER_PATH/dist
    cp -a $service_path/build/install/*/* $LOCAL_DOCKER_PATH/dist/
    rm -rf $LOCAL_DOCKER_PATH/dist/bin/*.bat #remove not needed batch files
    #rm -rf $LOCAL_DOCKER_PATH/dist/lib/tomcat* #remove not needed tomcat files. They're sneaking in because of logging lib. --manoj commented this out as it is breaking deduper tomcat jdbc connection pool factory
    if [ "$DOCKER_PATH" = 'jenkins/docker/gateway-server-haproxy' ]; then
        cp 'jenkins/betacerts/bundle.pem' $LOCAL_DOCKER_PATH/bundle.pem
    fi
fi

cp "jenkins/docker/usr.local.bin.rotate_logs_and_push_to_s3.py" $LOCAL_DOCKER_PATH/

sed -e "s|\$SERVICE_NAME|$SERVICE_NAME|" $DOCKER_PATH/log4j2.service.xml.template > $LOCAL_DOCKER_PATH/log4j2.service.xml

if [ -n "$P4_CHANGELIST" ]; then
    CHANGELIST=${P4_CHANGELIST}
else
    CHANGELIST=`git log --pretty=format:'%h' -n 1`
fi
DOCKER_OPTS="--build-arg SERVICE_NAME=$SERVICE_NAME \
             --build-arg P4_CHANGELIST=$CHANGELIST \
             --build-arg BRANCH=$BRANCH \
             --build-arg BUILD_NUMBER=$BUILD_NUMBER \
             --build-arg BUILD_URL=$BUILD_URL \
             --build-arg BUILD_TIMESTAMP=$BUILD_TIMESTAMP \
             --build-arg VERSION=$VERSION"

build_image
rm -rf $LOCAL_DOCKER_PATH
exit 0
