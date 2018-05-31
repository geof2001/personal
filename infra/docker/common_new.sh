#!/usr/bin/env bash

if [ -z "$DOCKER_REPO" ]; then
    DOCKER_REPO="638782101961.dkr.ecr.us-east-1.amazonaws.com"
fi

[ -z "$GRADLE_CMD" ] && GRADLE_CMD='gradle'
[ -z "$BRANCH" ] && echo "Please provide env variable BRANCH" && exit 1
[ -z "$BUILD_NUMBER" ] && echo "ERROR: Please set env variable BUILD_NUMBER" && exit 1
if [ -n "$SERVICE_INFO" ]; then
    SERVICE_NAME=`echo $SERVICE_INFO | grep -Po 'SERVICE_NAME=\K[^ ]+' || echo ''`
    DOCKER_PATH=`echo $SERVICE_INFO | grep -Po 'DOCKER_PATH=\K[^ ]+' || echo ''`
    DOCKER_REPO_OVERRIDE=`echo $SERVICE_INFO | grep -Po 'DOCKER_REPO=\K[^ ]+' || echo ''`
    if [ -n "$DOCKER_REPO_OVERRIDE" ]; then
        DOCKER_REPO=$DOCKER_REPO_OVERRIDE
    fi
fi
echo "Docker repository: ${DOCKER_REPO}"

[ -z "$SERVICE_NAME" ] && echo "ERROR: SERVICE_NAME is required" && exit 1
[ -z "$DOCKER_PATH" ] && echo "ERROR: DOCKER_PATH is required" && exit 1
datestamp=`date +%Y%m%d`
if [ -n "GIT_HASH" ]; then
    CHANGELIST=${GIT_HASH}
else
    CHANGELIST=`git log --pretty=format:'%h' -n 1 | cut -c1-10`
fi
VERSION="${BRANCH}-${CHANGELIST}-$datestamp-$BUILD_NUMBER"

build_local() {
    cmd="docker build $DOCKER_OPTS -t $DOCKER_REPO/$SERVICE_NAME:$VERSION $LOCAL_DOCKER_PATH/"
    time $cmd
    if [ "$DEBUG" != 'true' -a \
         -n "$DOCKER_PUSH_TO_REPO" -a "$DOCKER_PUSH_TO_REPO" = 'true' ]; then
        cmd="docker push $DOCKER_REPO/$SERVICE_NAME:$VERSION"
        # retry 3 times if failed
        $cmd || $cmd || $cmd
    fi
    if [ "$DEBUG" = 'true' ]; then
        docker rmi $DOCKER_REPO/$SERVICE_NAME:$VERSION
    fi
    docker images | grep -v '^REPOSITORY' | sort
}

build_image() {
    # basic validations
    [ -z "$SERVICE_NAME" ] && echo "ERROR: Please specify SERVICE_NAME" && exit 1
    [ -z "$DOCKER_REPO" ] && echo "ERROR: Please specify DOCKER_REPO" && exit 1
    [ -z "$VERSION" ] && echo "ERROR: Please specify VERSION" && exit 1
    [ -z "$LOCAL_DOCKER_PATH" ] && echo "ERROR: Please specify LOCAL_DOCKER_PATH" && exit 1

    build_local
    echo "=== Successfully created $DOCKER_REPO/$SERVICE_NAME:$VERSION ==="
}