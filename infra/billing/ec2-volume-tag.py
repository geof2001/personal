#!/usr/bin/env python

import boto3

ec2 = boto3.client('ec2')


def get_instance_id(vol):
    instance = None
    if 'Attachments' in vol:
        for attachment in vol['Attachments']:
            if 'InstanceId' in attachment:
                if not instance:
                    instance = attachment['InstanceId']
                elif instance != attachment['InstanceId']:
                    return None
    return instance


def get_tags(instance):
    tag_keys = {'Name', 'Spend_Category', 'Department'}
    resp = ec2.describe_tags(
        Filters=[
            {
                'Name': 'resource-id',
                'Values': [
                    instance,
                ]
            }
        ])
    if 'Tags' in resp:
        instance_tags = resp['Tags']
        pruned_tags = []
        for tag in instance_tags:
            if tag['Key'] in tag_keys:
                del tag['ResourceType']
                del tag['ResourceId']
                pruned_tags.append(tag)
        if len(pruned_tags) > 0:
            return pruned_tags
    return None


if __name__ == '__main__':

    # TAG EIP addresses
    response = ec2.describe_addresses()
    count = 0
    print ("Found {} EIPs".format(len(response['Addresses'])))

    for address in response['Addresses']:
        if 'Tags' not in address:
            if 'InstanceId' in address:
                tags = get_tags(address['InstanceId'])
                if tags:
                    print("Updating EIP {} with tags {}".format(address['PublicIp'], tags))
                    ec2.create_tags(
                        Resources=[address['AllocationId']],
                        Tags=tags
                    )
                    count += 1

    print ("Updated tags for {} EIPs".format(count))

    # TAG Volumes
    response = ec2.describe_volumes(
        Filters=[
            {
                'Name': 'attachment.status',
                'Values': [
                    'attached',
                ]
            },
            {
                'Name': 'status',
                'Values': [
                    'in-use'
                ]
            }
        ]
    )
    volumes = response['Volumes']
    print ("Found {} volumes".format(len(volumes)))
    count = 0
    for volume in volumes:
        # Only set tags if the volume has NO tags at all
        # Conservative so we don't mess with tags other systems have already set
        if 'Tags' not in volume:
            instance_id = get_instance_id(volume)
            if instance_id:
                tags = get_tags(instance_id)
                if tags:
                    print("Updating volume {} with tags {}".format(volume['VolumeId'], tags))
                    ec2.create_tags(
                        Resources=[volume['VolumeId']],
                        Tags=tags
                    )
                    count += 1
    print ("Updated tags for {} volumes".format(count))
