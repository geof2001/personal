#!/usr/bin/env bash

set -e

AWS_URL='http://169.254.169.254/latest'
# { "Code" : "Success", "LastUpdated" : "2014-12-22T19:36:04Z",
#   "InstanceProfileArn" : "arn:aws:iam::181133766305:instance-profile/alpha-haproxy-iam",
#   "InstanceProfileId" : "AIPAabcdefg..." }
_iam_info=$(curl -m 2 -sf $AWS_URL/meta-data/iam/info || true)

# us-east-1d, us-west-1a, ...
_availability_zone=$(curl -m 2 -sf $AWS_URL/meta-data/placement/availability-zone || true)

# useful variables below
ACCOUNT_NUM=$(echo $_iam_info | sed -e 's/.*arn:aws:iam:://' -e 's/:instance-profile.*//')
ACCOUNT_ALIAS=$(echo $ACCOUNT_NUM | sed -e 's/.*\([0-9][0-9][0-9]\)$/x\1/')  # x305, x498, ...
IAM_ROLE=$(echo $_iam_info | sed -e 's|.*instance-profile/||' -e 's|".*||')
REGION=$(echo $_availability_zone | sed -e 's/[a-zA-Z]$//')  # us-east-1, us-west-2, ...
HOSTNAME=$(curl -m 2 -sf $AWS_URL/meta-data/public-hostname || true)
PRIVIP=$(curl -m 2 -sf $AWS_URL/meta-data/local-ipv4 || true)
INSTANCE_ID=$(curl -m 2 -sf $AWS_URL/meta-data/instance-id || true)
INSTANCE_TYPE=$(curl -m 2 -sf $AWS_URL/meta-data/instance-type || true)
STACK_NAME=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" "Name=key,Values=aws:cloudformation:stack-name" --region $REGION --output=text | cut -f5)

cat <<EOT >> /tmp/aws.config
STACK_NAME=$STACK_NAME
ACCOUNT_NUM=$ACCOUNT_NUM
ACCOUNT_ALIAS=$ACCOUNT_ALIAS
IAM_ROLE=$IAM_ROLE
REGION=$REGION
HOSTNAME=$HOSTNAME
PRIVIP=$PRIVIP
INSTANCE_ID=$INSTANCE_ID
INSTANCE_TYPE=$INSTANCE_TYPE
EOT

# Output for debugging
cat /tmp/aws.config

# ========== Update bash prompt to be more intuitive ==========
if [ -f ~ec2-user/.bash_profile ]; then
    bashrc=~ec2-user/.bash_profile
fi
if [ -f ~ubuntu/.bashrc ]; then
    bashrc=~ubuntu/.bashrc
fi
if [ -n "$bashrc" ]; then
    sed -i "s/^PS1=.*//" $bashrc
    echo "#Upgrading bash prompt to include more info..."
    echo "PS1='[$ACCOUNT_ALIAS:$REGION:$STACK_NAME $INSTANCE_ID=$INSTANCE_TYPE,$IAM_ROLE  $HOSTNAME]" \
        "\n[\\u@$PRIVIP:/\W]\\\$ '" >> $bashrc
fi
echo "#Done executing setup_environments.sh"
