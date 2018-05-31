#!/bin/sh
#
# This is intended to be run from Jenkins only.
# This script in run inside Jenkins to create a new Docker Image

set -e
set -x

[ ! -e "jenkins/docker" ] && echo "Please run this from the root of the path!" && exit 1

# Images will be pushed to these regions
DOCKER_REPOS="638782101961.dkr.ecr.us-west-2.amazonaws.com 638782101961.dkr.ecr.us-east-1.amazonaws.com"

# basic variable setup and checks
[ -z "$GRADLE_CMD" ] && GRADLE_CMD='gradle'
[ -z "$BRANCH" ] && echo "Please provide env variable BRANCH" && exit 1
[ -z "$BUILD_NUMBER" ] && echo "ERROR: Please set env variable BUILD_NUMBER" && exit 1
if [ -n "$SERVICE_INFO" ]; then
    SERVICE_NAME=`echo $SERVICE_INFO | grep -Po 'SERVICE_NAME=\K[^ ]+' || echo ''`
    DOCKER_PATH=`echo $SERVICE_INFO | grep -Po 'DOCKER_PATH=\K[^ ]+' || echo ''`
fi
echo "Docker repository: ${DOCKER_REPOS}"

datestamp=`date +%Y%m%d`

VERSION="${BRANCH}-${GIT_HASH}-$datestamp-$BUILD_NUMBER"

tmp_docker_path="/tmp/docker.$SERVICE_NAME.$VERSION"
LOCAL_DOCKER_PATH=$tmp_docker_path
rm -rf $LOCAL_DOCKER_PATH

# Run the gradle build including the unit tests

service_path=`echo $SERVICE_INFO | grep -Po 'SERVICE_PATH=\K[^ ]+' || echo ''`
gradle_version=`echo $SERVICE_INFO | grep -Po 'GRADLE_VERSION=\K[^ ]+' || echo ''`
if [ $gradle_version = "3.2.1" -o $gradle_version = "4.7" ]; then
    GRADLE_CMD="/usr/local/src/gradle-"$gradle_version"/bin/gradle"
    echo $GRADLE_CMD
fi

if [ "$service_path" = '' ]; then
    if [ -e "$SERVICE_NAME/server" ]; then
        service_path="$SERVICE_NAME/server"
    fi
fi

if [ "$DOCKER_PATH" = 'jenkins/docker/sparkserver' -o "$DOCKER_PATH" = 'jenkins/docker/gateway-server-haproxy' -o "$DOCKER_PATH" = 'jenkins/docker/beehive-apis' ]; then
    BUILD_TASK="installDist"
fi

sh -c "\
  cd $service_path && \
  $GRADLE_CMD \
    --no-daemon \
    --refresh-dependencies \
    -Ppublish.type=release -Ppublish.buildnumber=$BUILD_NUMBER \
    clean test $BUILD_TASK"

cp -a $DOCKER_PATH $LOCAL_DOCKER_PATH/

mkdir $LOCAL_DOCKER_PATH/dist
cp -a $service_path/build/install/*/* $LOCAL_DOCKER_PATH/dist/
rm -rf $LOCAL_DOCKER_PATH/dist/bin/*.bat #remove not needed batch files
if [ "$DOCKER_PATH" = 'jenkins/docker/gateway-server-haproxy' ]; then
    cp 'jenkins/betacerts/bundle.pem' $LOCAL_DOCKER_PATH/bundle.pem
fi

cp "jenkins/docker/usr.local.bin.rotate_logs_and_push_to_s3.py" $LOCAL_DOCKER_PATH/

sed -e "s|\$SERVICE_NAME|$SERVICE_NAME|" $DOCKER_PATH/log4j2.service.xml.template > $LOCAL_DOCKER_PATH/log4j2.service.xml

DOCKER_OPTS="--build-arg SERVICE_NAME=$SERVICE_NAME \
             --build-arg P4_CHANGELIST=$GIT_HASH \
             --build-arg BRANCH=$BRANCH \
             --build-arg BUILD_NUMBER=$BUILD_NUMBER \
             --build-arg BUILD_URL=$BUILD_URL \
             --build-arg BUILD_TIMESTAMP=$BUILD_TIMESTAMP \
             --build-arg VERSION=$VERSION"

# some basic validations
[ -z "$SERVICE_NAME" ] && echo "ERROR: Please specify SERVICE_NAME" && exit 1
[ -z "$GIT_HASH" ] && echo "ERROR: Please specify GIT_HASH" && exit 1
[ -z "$VERSION" ] && echo "ERROR: Please specify VERSION" && exit 1
[ -z "$DOCKER_PATH" ] && echo "ERROR: DOCKER_PATH is required" && exit 1
[ -z "$LOCAL_DOCKER_PATH" ] && echo "ERROR: Please specify LOCAL_DOCKER_PATH" && exit 1

# build and push the docker image for each region

for DOCKER_REPO in $DOCKER_REPOS ;do

    if [ `echo $DOCKER_REPO |grep -c us-east-1` -eq 1 ];then
        eval $(aws ecr get-login --no-include-email --registry-id 638782101961 --region us-east-1)
    else
        eval $(aws ecr get-login --no-include-email --registry-id 638782101961 --region us-west-2)
    fi

    cmd="docker build $DOCKER_OPTS -t $DOCKER_REPO/$SERVICE_NAME:$VERSION $LOCAL_DOCKER_PATH/"
    time $cmd
    # don't push the image if this is debug mode or if the push to repo button isn't selected
    if [ "$DEBUG" != 'true' -a -n "$DOCKER_PUSH_TO_REPO" -a "$DOCKER_PUSH_TO_REPO" = 'true' ]; then
        cmd="docker push $DOCKER_REPO/$SERVICE_NAME:$VERSION"
        $cmd || $cmd || $cmd
    fi
    # delete the built image if in debug mode
    if [ "$DEBUG" = 'true' ]; then
        docker rmi $DOCKER_REPO/$SERVICE_NAME:$VERSION
    fi
done

docker images | grep -v '^REPOSITORY' | sort
echo "=== Successfully created $DOCKER_REPO/$SERVICE_NAME:$VERSION ==="

rm -rf $LOCAL_DOCKER_PATH
exit 0
