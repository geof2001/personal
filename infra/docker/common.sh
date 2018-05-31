#!/usr/bin/env bash

SSH_KEY=~/.ssh/bakery.pem
USERNAME=ec2-user
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
if [ -n "$P4_CHANGELIST" ]; then
    CHANGELIST=${P4_CHANGELIST}
else
    CHANGELIST=`git log --pretty=format:'%h' -n 1`
fi
VERSION="${BRANCH}-${CHANGELIST}-$datestamp-$BUILD_NUMBER"

if [ -n "$EXTERNAL_BUILD_DNS" ]; then
    # clear up the known_hosts because the ssh host changes in ASG
    touch ~/.ssh/known_hosts
    ssh-keygen -f ~/.ssh/known_hosts -R $EXTERNAL_BUILD_DNS
fi

sshcmd() {
  ssh -t -t -C -o StrictHostKeyChecking=no -i ${SSH_KEY} ${USERNAME}@${EXTERNAL_BUILD_DNS} "$@"
}
scprcmd() {
  [ "$#" -gt 2 -o "$#" -lt 2 ] && echo "ERROR: scpcmd must have 2 arguments." && exit 1
  [ -n "$2" ] && remote_dest=$2 || remote_dest="~"
  scp -r -C -o StrictHostKeyChecking=no -i ${SSH_KEY} $1 ${USERNAME}@${EXTERNAL_BUILD_DNS}:${remote_dest}
}

build_remote() {
    if $(sshcmd test -e "/usr/bin/docker"); then
        tmp_docker_path="/tmp/docker.$SERVICE_NAME.$VERSION"
        scprcmd $LOCAL_DOCKER_PATH $tmp_docker_path
        sshcmd "\
            docker build $DOCKER_OPTS -t $DOCKER_REPO/$SERVICE_NAME:$VERSION $tmp_docker_path/ && \
            rm -rf $tmp_docker_path"
        if [ "$DEBUG" != 'true' -a \
             -n "$DOCKER_PUSH_TO_REPO" -a "$DOCKER_PUSH_TO_REPO" = 'true' ]; then
            sshcmd "time docker push $DOCKER_REPO/$SERVICE_NAME:$VERSION \
              || time docker push $DOCKER_REPO/$SERVICE_NAME:$VERSION \
              || time docker push $DOCKER_REPO/$SERVICE_NAME:$VERSION"
        fi
        if [ "$DEBUG" = 'true' ]; then
            sshcmd "docker rmi $DOCKER_REPO/$SERVICE_NAME:$VERSION"
        fi
        sshcmd "docker images | grep -v '^REPOSITORY' | sort"
        build_done=1
    fi
}

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

    # --- use EC2 machine when possible ---
    build_done=0
    if [ -n "$EXTERNAL_BUILD_DNS" ]; then
        build_remote
    fi
    # --- if EC2 is not available, use local Jenkins machine (slower due to network) ---
    if [ "$build_done" = 0 ]; then
        build_local
    fi
    echo "=== Successfully created $DOCKER_REPO/$SERVICE_NAME:$VERSION ==="
}