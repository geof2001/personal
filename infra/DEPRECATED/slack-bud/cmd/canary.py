"""Deploys a canary instance for services"""
from __future__ import print_function
from troposphere import Ref, Template

import boto3
import troposphere.ecs as ecs
import troposphere.ec2 as ec2
import troposphere.elasticloadbalancingv2 as elbv2
import os
import slack_ui_util


def handle_canary_deploy():
    """Create and deploy canary CF template as canary-service-buildnumber"""
    try:
        if os.path.isfile('./build_info.txt'):
            f = open('build_info.txt', 'r')
            file_text = f.read()
            return slack_ui_util.text_command_response(
                title='Version',
                text=file_text
            )
        else:
            return slack_ui_util.text_command_response(
                title='Version',
                text='No version information found.'
            )
    except IOError as ex:
        return slack_ui_util.error_response('%s' % ex.message)
