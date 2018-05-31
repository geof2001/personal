#!/bin/sh

set -x

for region in "us-east-1" "us-west-2"
do

    count=`aws ecr describe-repositories --registry-id 638782101961 --repository-name $1 --profile 638782101961 --region $region 2>&1 |grep -c registryId`

    if [ $count -lt '1' ]
    then
        echo "no repo - creating"
        aws ecr create-repository --repository-name $1 --profile 638782101961 --region $region
        aws ecr set-repository-policy --registry-id 638782101961 --repository-name $1 --policy-text file://repo-permissions.json --profile 638782101961 --region $region
    else
        echo "ECR repo exists for region $region"
    fi
done
