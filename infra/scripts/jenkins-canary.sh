#!/usr/bin/env bash

#echo $StackName, $AWS_ACCOUNTS, $AWS_REGIONS, $prefix

for AWS_ACCOUNT in `echo $AWS_ACCOUNTS | sed 's/,/ /g'`; do
   echo checking account $AWS_ACCOUNT
   if [ "$AWS_ACCOUNT" = "886239521314" ]
   then
       echo found prod account
       if [ $ProdPush = "false" ]
       then
          echo Not pushing to production.  Click on ProdPush to really deploy to prod.
          exit 1
       fi
   fi
done

echo "GIT_AUTHOR: `git log -1 --pretty=format:"%aN"`"

set -x
set -e

#./validate-configs.sh

Color=""
if [ -n "$STACK_NAME" ]
then
	Color="$STACK_NAME"
fi

echo "Accounts: ", $AWS_ACCOUNTS
echo "Regions: ", $AWS_REGIONS
echo "ServiceName: ", $SERVICE_NAME
echo "ImageVersion: ", $IMAGE_VERSION
echo "Branch: ", $BRANCH
echo "DesiredCount: ", $DESIRED_COUNT
echo "StackName: ", $Color
echo "ProdPush: ", $ProdPush
echo "create change set: ", $CreateChangeSet
echo "UserName: ", $TAGS

# for AWS_ACCOUNT in `echo $AWS_ACCOUNTS | sed 's/,/ /g'`; do
#  for AWS_REGION in `echo $AWS_REGIONS | sed 's/,/ /g'`; do
#    for StackPath in `echo $StackPaths | sed 's/,/ /g'`; do
#      cd $WORKSPACE
#      echo "Running $StackPath with profile $AWS_ACCOUNT in region $AWS_REGION"
#      StackName=${StackPath##*/}
#      repository=`echo $StackPath |cut -f 1 -d"/"`
#      ServiceStack=`echo $StackPath |cut -f 2 -d"/"`
#      echo $repository
#      rm -rf infra/*
#      git archive --remote=git@gitlab.eng.roku.com:SR/${repository}.git $BRANCH infra | tar -x
#      cd infra
#       if [ -f "$ServiceStack-datapipeline.template.yaml" ]
#       then
#       	aws s3 cp ./$ServiceStack-datapipeline.template.yaml \
#         s3://cf-clusters-$AWS_ACCOUNT-$AWS_REGION/$ServiceStack-datapipeline.template.yaml \
#         --profile $AWS_ACCOUNT
#       fi
#       if [ -f "$ServiceStack.batch.template.yaml" ]
#       then
#       	aws s3 cp ./$ServiceStack.batch.template.yaml \
#         s3://cf-clusters-$AWS_ACCOUNT-$AWS_REGION/$ServiceStack.batch.template.yaml \
#         --profile $AWS_ACCOUNT
#       fi
#       cp $WORKSPACE/scripts/deploy_stack.py .
#       ./deploy_stack.py \
#         --service $ServiceStack \
#         --changeset=$CreateChangeSet \
#         -s $Color$StackName \
#         -r $AWS_REGION \
#         -p $AWS_ACCOUNT \
#         -t=$UsePreviousTemplate \
#         -g $repository \
#         -b $BUILD_NUMBER
#     done    
#   done
# done


# # Wait for stack to finish deploying before exiting.

# cd $WORKSPACE
# for AWS_ACCOUNT in `echo $AWS_ACCOUNTS | sed 's/,/ /g'`; do
#   for AWS_REGION in `echo $AWS_REGIONS | sed 's/,/ /g'`; do
#     for StackPath in `echo $StackPaths | sed 's/,/ /g'`; do
#       StackName=${StackPath##*/}
#       echo "Waiting for CF to complete in account $AWS_ACCOUNT in region $AWS_REGION on stack $StackName"
#       ./scripts/cf_waiter.py -p $AWS_ACCOUNT -r $AWS_REGION -s $StackName -t 3600
#     done    
#   done
# done

# ls infra