#!/usr/bin/env python
#
# This script adds the tag 'Name' to blank EC2 instances, for better
# debuggability via Datadog and EC2 console.
#
# WARNING: There is a limit of 10 tags per instance. Therefore, please
#          add tags judiciously.
from aws_utils import *

use_boto3()


def update_tags(remove_tags, add_tags):
    if remove_tags:
        _rtags = list(({'Key': k} for k in remove_tags))
        print "%s deleting %s" % (inst_id, _rtags)
        try:
            inst.delete_tags(Tags=_rtags)
        except AttributeError, e:
            print 'WARNING: %s' % e
    if add_tags:
        _atags = list(({'Key': k, 'Value': v}
                            for k, v in add_tags.iteritems()))
        print "%s creating %s" % (inst_id, _atags)
        inst.create_tags(inst_id, Tags=_atags)


if __name__ == '__main__':

    iam_acct_num, region, access = get_aws_credentials()
    print "Fetching using AWS_KEY:%s, AWS_DEFAULT_PROFILE:%s, Region:%s..." % (
        access.get('aws_access_key_id', None),
        os.environ.get('AWS_DEFAULT_PROFILE', None),
        region)

    instid2eip, instance_dict, sgroup_dict, imageId2image = \
        fetch_ec2_info(region, access)
    ec2 = boto3.resource('ec2', region_name=region)
    for inst in ec2.instances.all():  #instance_dict.itervalues():
        inst_id = inst.id
        inst_tags = get_tagdict_from_boto3_tags(inst.tags)
        add_tags = {}
        remove_tags = set()

        if 'Account' in inst_tags:
            inst.remove_tag('Account')

        image = imageId2image.get(inst.image_id, None)
        if image:
            #print "**** %s" % image
            image_tags = get_tagdict_from_boto3_tags(image.get(TAGS, {}))

            image_info = '%s, %s' % (
                image.get(IMAGE_LOCATION, ''),
                image.get(DESCRIPTION, ''))
            if ('ImageDescription' not in inst_tags or
                    image_info != inst_tags.get('ImageDescription', '')):
                # remove deprecated tags
                if 'ImageLocation' in inst_tags:
                    remove_tags.add('ImageLocation')
                add_tags['ImageDescription'] = image_info

            # these fields are propagated from Omega's Jenkins script
            # jenkins/bake_ami_create_image.sh
            ami_str = ', '.join(
                [image_tags.get(tag)
                 for tag in ('BASE_AMI', 'BASE_AMI_LOCATION',
                             'BASE_AMI_DESCRIPTION')
                 if image_tags.get(tag, None)])
            if ami_str == '':
                ami_str = inst.image_id
            if ('BASE_AMI' not in inst_tags or
                        ami_str != inst_tags.get('BASE_AMI', None)):
                # remove deprecated tags
                if 'BASE_AMI_DESCRIPTION' in inst_tags:
                    remove_tags.add('BASE_AMI_DESCRIPTION')
                if 'BASE_AMI_LOCATION' in inst_tags:
                    remove_tags.add('BASE_AMI_LOCATION')
                add_tags['BASE_AMI'] = ami_str

            if 'ImageBUILD_URL' not in inst_tags and 'BUILD_URL' in image_tags:
                add_tags['ImageBUILD_URL'] = image_tags['BUILD_URL']
            if 'ImageBUILD_ID' not in inst_tags and 'BUILD_ID' in image_tags:
                add_tags['ImageBUILD_ID'] = image_tags['BUILD_ID']

            if 'Platform' not in inst_tags:
                value = ('windows' if inst_tags.get(PLATFORM, '') == 'windows'
                         else 'linux')
                add_tags['Platform'] = value

        else:
            if 'ImageLocation' not in inst_tags:
                add_tags['ImageLocation'] = 'unknown(removed?)'

        # Asgard specific tags
        if AWS_ASG_NAME not in inst_tags:
            update_tags(remove_tags, add_tags)
            continue
        asg = inst_tags[AWS_ASG_NAME]

        if 'Name' not in inst_tags:  # or re.search(asg, tags.get('Name', '')):
            new_name = "%s %s" % (asg, inst.id)
            add_tags['Name'] = new_name

        if 'App' not in inst_tags:
            app_name = asg.split('-')[0]
            add_tags['App'] = app_name

        update_tags(remove_tags, add_tags)
