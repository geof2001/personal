#!/bin/sh
#
# This is intended to be run from Jenkins only.
# This script in run inside Jenkins to create a new Slack_bud Docker Image

set -e
set -x

[ ! -e "docker" ] && echo "Please run this from the root of the path!" && exit 1

# Images will be pushed to these regions
DOCKER_REPOS="661796028321.dkr.ecr.us-west-2.amazonaws.com"

# basic variable setup and checks
[ -z "$GRADLE_CMD" ] && GRADLE_CMD='gradle'
[ -z "$BRANCH" ] && echo "Please provide env variable BRANCH" && exit 1
[ -z "$BUILD_NUMBER" ] && echo "ERROR: Please set env variable BUILD_NUMBER" && exit 1

echo "Docker repository: ${DOCKER_REPOS}"

datestamp=`date +%Y%m%d`

VERSION="${BRANCH}-${GIT_HASH}-$datestamp-$BUILD_NUMBER"

tmp_docker_path="/tmp/docker.$SERVICE_NAME.$VERSION"
LOCAL_DOCKER_PATH=$tmp_docker_path
rm -rf $LOCAL_DOCKER_PATH

# Run the gradle build including the unit tests

service_path=`echo $SERVICE_INFO | grep -Po 'SERVICE_PATH=\K[^ ]+' || echo ''`

if [ "$service_path" = '' ]; then
    if [ -e "$SERVICE_NAME/server" ]; then
        service_path="$SERVICE_NAME/server"
    fi
fi

DOCKER_PATH="docker/slackbud"
SERVICE_NAME="slackbuddocker"

cp -a $DOCKER_PATH $LOCAL_DOCKER_PATH/

mkdir $LOCAL_DOCKER_PATH/dist

cp "docker/usr.local.bin.rotate_logs_and_push_to_s3.py" $LOCAL_DOCKER_PATH/

#DOCKER_OPTS="--build-arg SERVICE_NAME=$SERVICE_NAME \
#             --build-arg GIT_HASH=$GIT_HASH \
#             --build-arg BRANCH=$BRANCH \
#             --build-arg BUILD_NUMBER=$BUILD_NUMBER \
#             --build-arg BUILD_URL=$BUILD_URL \
#             --build-arg BUILD_TIMESTAMP=$BUILD_TIMESTAMP \
#             --build-arg VERSION=$VERSION"

# some basic validations
[ -z "$SERVICE_NAME" ] && echo "ERROR: Please specify SERVICE_NAME" && exit 1
[ -z "$GIT_HASH" ] && echo "ERROR: Please specify GIT_HASH" && exit 1
[ -z "$VERSION" ] && echo "ERROR: Please specify VERSION" && exit 1
[ -z "$DOCKER_PATH" ] && echo "ERROR: DOCKER_PATH is required" && exit 1
[ -z "$LOCAL_DOCKER_PATH" ] && echo "ERROR: Please specify LOCAL_DOCKER_PATH" && exit 1

# build and push the docker image for each region

for DOCKER_REPO in $DOCKER_REPOS ;do

    if [ `echo $DOCKER_REPO |grep -c us-east-1` -eq 1 ];then
        eval $(aws ecr get-login --registry-id 661796028321 --region us-east-1)
    else
        eval $(aws ecr get-login --registry-id 661796028321 --region us-west-2)
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
