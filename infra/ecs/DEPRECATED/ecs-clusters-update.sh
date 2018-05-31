#!/usr/bin/env bash

if [ -z "$1" -o -z "$2" -o -z "$3" -o -z "$4" ]; then
    echo "Usage: $0 STACK_NAME CF_TEMPLATE_.json PROFILE REGION"
    exit 1
fi

aws cloudformation describe-stacks --stack-name $1 --profile $3 --region $4
if [ $? -eq 0 ]; then
    echo "Stack $1 already exists, updating it..."
    aws cloudformation update-stack --capabilities CAPABILITY_IAM --stack-name $1 --template-body file://$2 --profile $3 --region $4
    if [ $? -eq 0 ]; then
        echo "Update submitted successfully"
    else
        echo "Update failed. Usually this is because nothing was changed and CF did not apply the change. Please see StackStatus above for more info."
    fi
else
    echo "Creating a new stack $1 using $2..."
    aws cloudformation create-stack --capabilities CAPABILITY_IAM --stack-name $1 --template-body file://$2 --profile $3 --region $4
fi

if [ $? -ne 0 ]; then
    echo "Latest status:"
    aws cloudformation describe-stacks --stack-name $1 --profile $3 --region $4
fi
