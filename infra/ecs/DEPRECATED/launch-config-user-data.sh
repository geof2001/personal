#!/bin/sh
# This initialization script exists in jenkins/ecs/... path.
# Make sure to sync it with jenkins/deploy/ecs_asg.py
set -x
echo ECS_CLUSTER=ECS-Service-Cluster >> /etc/ecs/ecs.config
export CLOUD_APP=ecs
yum install -y aws-cli
export ECS_BOOT_VERSION=`aws s3 ls s3://roku-ecs-boot/ | grep 'jenkins\-[0-9]*' | tail -1 | awk '{print $2}' | sed -e 's#/##g'`
aws s3 cp --quiet --recursive s3://roku-ecs-boot/$ECS_BOOT_VERSION/  /usr/local/bin/
chmod u+rx /usr/local/bin/*.sh /usr/local/bin/*.py
/usr/local/bin/initialize_ecs_at_startup.sh 2>&1 >> /var/log/initialize_ecs_at_startup.log
