"""Implements Untagged command by asnyder@ruku.com"""
from __future__ import print_function

import traceback
import time
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdUntagged(CmdInterface):

    def get_help_title(self):
        """
        Short one line description, for global help command.
        :return: short string describing this command
        """
        return "Find AWS resources without Spend_Category tags"

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud untagged <action> -e <env> -r <region>_\n"
        help_text += "*Example:* _/bud untagged report -e dev -r us-east-1 -t dynamo_\n\n"
        help_text += "*<report>* _Report shows all untagged AWS resources of the type specified._\n"
        help_text += "           _Look for resources without the *Spend_Category* tag_\n"
        help_text += "*<types>* _Shows all the valid types to use for *-t* param in report command_\n"
        help_text += "           _Look for resources that should have Spend_Category tags_\n"
        help_text += "*Examples:*                      \n"
        help_text += "           _/bud untagged types_                      \n"
        help_text += "           _/bud untagged report -e dev -r us-east-1 -t dynamo_\n"
        help_text += "           _/bud untagged report -e dev -r us-east-1 -t ec2_\n"
        help_text += "           _/bud untagged report -e dev -r us-east-1 -t s3_\n"

        help_title = self.get_help_title()
        return slack_ui_util.text_command_response(
            help_title, help_text, "#00b2ff"
        )

    def invoke_sub_command(self, sub_command, args, response_url=None, slack_channel=None):
        """
        Return help text for your command in slack format here.
        """
        try:
            if sub_command == 'help':
                return self.get_help_text()

            # slack_ui_util.loading_msg(response_url)

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))

            if sub_command == 'types':
                # You need to modify this
                return handle_types_command(args, response_url)

            # The types command doesn't need this, so check is here.
            if not args.envs or not args.regions:
                return slack_ui_util.error_response(
                    'Please specify an environment, and region (-e, -r)',
                    post=True,
                    response_url=response_url
                )

            if sub_command == 'report':
                # You need to modify this
                return handle_report_command(args, response_url)

            title = 'Untagged response'
            text = 'Unknown sub command {}. Use help.'.format(sub_command)
            return slack_ui_util.text_command_response(title, text)

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def invoke_confirm_command(self, params):
        """
        Return help text for your command in slack format here.
        """
        try:
            # This section is for working with confirm
            # ToDo: Provide a simple working example.
            return None

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return slack_ui_util.error_response(slack_error_message)

    def is_confirm_command(self, params):
        """
        Return help text for your command in slack format here.
        """
        try:
            fallback_str = self.get_fallback_string_from_payload(params)
            if fallback_str is None:
                return False
            elif fallback_str == self.__class__.__name__:
                return True
            return False

        except ShowSlackError as slack_error_message:
            print(type(slack_error_message))
            print(slack_error_message.args)
            print(slack_error_message)

            return False

    def invoke_longtask_command(self, event):
        """
        Put longtask command stuff here.
        :param event:
        :return:
        """
        # Temp just to not break build.
        return None

    def set_fallback_value(self):
        return self.__class__.__name__


def handle_report_command(args, response_url):
    """
    Placeholder for command
    :param response_url:
    :param args:
    :return: A Slack command response which is usually
    """
    start_time = time.time()

    env = args.envs[0]
    region = args.regions[0]
    type = get_type_from_args(args)

    session = aws_util.create_session(env)

    tagging_client = aws_util.get_tagging_client(session, region)

    text = "List of untagged resources\n"
    types_count = 0
    if 'autoscale' in type:
        types_count += 1
        text += check_for_untagged_autoscaling_groups(session, region, tagging_client)
    if 'cloudfront' in type:
        types_count += 1
        text += check_for_untagged_cloud_front_distributions(session, region, tagging_client)
    if 'dynamo' in type:
        types_count += 1
        text += check_for_untagged_dynamo_tables(session, region, tagging_client)
    if 'ec2' in type:
        types_count += 1
        text += check_for_untagged_ec2_instances(session, region, tagging_client)
    if 'elasticache' in type:
        types_count += 1
        text += check_for_untagged_elasticache_replication_groups(session, region, tagging_client)
    if 'elb' in type:
        types_count += 1
        text += check_for_untagged_load_balancers(session, region, tagging_client)
    if 'logs' in type:
        types_count += 1
        text += check_for_untagged_log_groups(session, region, tagging_client)
    if 'rds' in type:
        types_count += 1
        text += check_for_untagged_rds_instances(session, region, tagging_client)
    if 'rds-cluster' in type:
        types_count += 1
        text += check_for_untagged_rds_groups(session, region, tagging_client)
    if 's3' in type:
        types_count += 1
        text += check_for_untagged_s3_buckets(session, region, tagging_client)
# sqs
# route53

    if types_count == 0:
        text += 'unknown type(s): {}\n'.format(type)

    end_time = time.time()
    run_time = end_time - start_time
    text += 'run time: {} sec'.format(run_time)

    title = 'AWS Tag report'
    return slack_ui_util.text_command_response(title, text,
                                               post=True, response_url=response_url)


def handle_types_command(args, response_url):
    """
    List the types option
    :param args:
    :param response_url:
    :return:
    """
    text = 'Types of resources supported\n'
    text += '   *autoscale*   AutoScaling Groups\n'
    text += '   *cloudfront*  CloudFront distributions\n'
    text += '   *dynamo*      DynamoDB Tables\n'
    text += '   *ec2*         EC2 Instances\n'
    text += '   *elasticache* ElastiCache Replication Groups\n'
    text += '   *elb*         LoadBalancers (classic)\n'
    text += '   *logs*        CloudWatch Log Groups\n'
    # text += '   *rds*         RDS Instances\n'
    # text += '   *rds-cluster* RDS Clusters\n'
    text += '   *s3*          S3 Buckets\n'

    title = 'Untagged types response'
    return slack_ui_util.text_command_response(title, text,
                                               post=True, response_url=response_url)


def check_for_untagged_autoscaling_groups(session, region, tagging_client):
    """
    List all untagged AutoScaling Groups resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    autoscaling_client = aws_util.get_boto3_client_by_name('autoscaling', session, region)
    response = autoscaling_client.describe_auto_scaling_groups()
    all_groups_list = response['AutoScalingGroups']
    all_group_arns_list = []
    for curr_group in all_groups_list:
        curr_arn = curr_group['AutoScalingGroupARN']
        all_group_arns_list.append(curr_arn)
    all_groups_len = len(all_group_arns_list)

    arn_list = get_tagged_resource_list(tagging_client, 'autoscaling:autoScalingGroup')
    arn_list_len = len(arn_list)
    ret_val = 'AutoScaling found {} tagged of {} total groups\n'.format(arn_list_len, all_groups_len)

    tagged_arn_set = set(arn_list)
    untagged_set = set(all_group_arns_list).difference(tagged_arn_set)
    untagged_set_len = len(untagged_set)

    if untagged_set_len > 0:
        ret_val = 'AutoScaling found {} untagged of {} total groups\n'.format(untagged_set_len, all_groups_len)
        sorted_untagged_table_list = sorted(untagged_set)
        index = 0
        for curr_name in sorted_untagged_table_list:
            index += 1
            ret_val += '    {}) {}\n'.format(index, curr_name)
    else:
        ret_val = 'All {} Autoscaling groups tagged.\n'.format(all_groups_len)

    return ret_val


def check_for_untagged_cloud_front_distributions(session, region, tagging_client):
    """
    List all untagged CloudFront Distributions resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """

    cfront_client = aws_util.get_boto3_client_by_name('cloudfront', session, region)
    response = cfront_client.list_distributions()
    all_cfront_distros = response['DistributionList']['Items']
    all_cf_distro_arns = []
    for curr_cfront_distro in all_cfront_distros:
        curr_arn = curr_cfront_distro['ARN']
        all_cf_distro_arns.append(curr_arn)
    all_cf_distros_len = len(all_cf_distro_arns)

    arn_list = get_tagged_resource_list(tagging_client, 'cloudfront:distribution')
    arn_list_len = len(arn_list)
    # ret_val = 'CloudFront found {} tagged distribution\n'.format(arn_list_len)

    tagged_arn_set = set(arn_list)
    untagged_set = set(all_cf_distro_arns).difference(tagged_arn_set)
    untagged_set_len = len(untagged_set)

    if untagged_set_len > 0:
        ret_val = 'CloudFront found {} untagged of {} total distributions\n'.format(untagged_set_len, all_cf_distros_len)
        sorted_untagged_table_list = sorted(untagged_set)
        index = 0
        for curr_name in sorted_untagged_table_list:
            index += 1
            ret_val += '    {}) {}\n'.format(index, curr_name)
    else:
        ret_val = 'All {} CloudFront distributions tagged.\n'.format(all_cf_distros_len)

    return ret_val


def check_for_untagged_dynamo_tables(session, region, tagging_client):
    """
    List all untagged DynamoDB table resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """

    dynamodb = aws_util.get_dynamo_resource(session, region, client=True)
    response = dynamodb.list_tables()
    table_names = response['TableNames']

    table_names_len = len(table_names)
    print('Dynamo found {} tables: /n{}'.format(table_names_len, table_names))

    arn_list = get_tagged_resource_list(tagging_client, 'dynamodb:table')
    arn_list_len = len(arn_list)
    # print('Dynamo search found {} table and {} were tagged'
    #       .format(table_names_len, arn_list_len))
    # print('List of tagged tables: {}'.format(arn_list))

    normalized_arn_list = normalize_arn_list(arn_list)
    tagged_arn_set = set(normalized_arn_list)

    print('tagged_arn_set:\n{}'.format(tagged_arn_set))
    untagged_set = set(table_names).difference(tagged_arn_set)

    print('This should be the set of untagged DynamoDB tables\n{}'.format(untagged_set))

    untagged_set_len = len(untagged_set)
    if untagged_set_len > 0:
        ret_val = 'Found {} untagged of {} total tables\n'.format(untagged_set_len, table_names_len)
        sorted_untagged_table_list = sorted(untagged_set)
        index = 0
        for curr_name in sorted_untagged_table_list:
            index += 1
            ret_val += '    {}) {}\n'.format(index, curr_name)
    else:
        ret_val = 'All {} DynamoDB tables tagged.\n'.format(table_names_len)

    return ret_val


def check_for_untagged_ec2_instances(session, region, tagging_client):
    """
    List all untagged EC2 Instances resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    try:
        ec2_client = aws_util.get_ec2_resource(session, region, client=True)
        response = ec2_client.describe_instances()
        all_ec2_instance_list = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance['InstanceId']
                all_ec2_instance_list.append(instance_id)
        all_ec2_instance_len = len(all_ec2_instance_list)

        arn_list = get_tagged_resource_list(tagging_client, 'ec2:instance')
        arn_list_len = len(arn_list)
        ret_val = 'EC2 found {} tagged of {} total instances\n'.format(arn_list_len, all_ec2_instance_len)

        return ret_val

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during EC2 phase. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

        return 'Error during EC2 phase. Check logs\n'


def check_for_untagged_elasticache_replication_groups(session, region, tagging_client):
    """
    List all untagged ElastiCache Clusters resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    elasticache_client = aws_util.get_boto3_client_by_name('elasticache', session, region)
    response = elasticache_client.describe_replication_groups()

    all_rep_groups = response['ReplicationGroups']
    all_rep_group_list = []
    for curr_rep_group in all_rep_groups:
        curr_rep_group_id = curr_rep_group['ReplicationGroupId']
        all_rep_group_list.append(curr_rep_group_id)

    total_rep_groups = len(all_rep_group_list)

    arn_list = get_tagged_resource_list(tagging_client, 'elasticache:cluster')
    arn_list_len = len(arn_list)
    ret_val = 'ElastiCache found {} tagged of {} total clusters\n'.format(arn_list_len, total_rep_groups)

    # # ToDo: Figure out of arn_list need normalizing before.
    # print('All elasticache regroup ids:\n{}'.format(all_rep_group_list))
    # print('ElastiCache tagged ARN list:\n{}'.format(arn_list))

    normalized_arn_list = normalize_elasticache_list(arn_list)

    # print('Normalized ARN list:\n{}'.format(normalized_arn_list))

    untagged_set = set(all_rep_group_list).difference(set(normalized_arn_list))

    ret_val = write_untagged_items(untagged_set, total_rep_groups, 'ElastiCache Groups')

    return ret_val


def check_for_untagged_load_balancers(session, region, tagging_client):
    """
    List all untagged Load Balancers resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    elb_client = aws_util.get_boto3_client_by_name('elb',session, region)
    response = elb_client.describe_load_balancers()

    all_load_balancers = response['LoadBalancerDescriptions']
    all_lb_name_list = []
    for curr_load_balancer in all_load_balancers:
        curr_lb_name = curr_load_balancer['LoadBalancerName']
        all_lb_name_list.append(curr_lb_name)
    total_lb_count = len(all_lb_name_list)

    arn_list = get_tagged_resource_list(tagging_client, 'elasticloadbalancing:loadbalancer')
    arn_list_len = len(arn_list)
    ret_val = 'ELB found {} tagged of {} total load balancers\n'.format(arn_list_len, total_lb_count)

    try:
        # print('All ELB names:\n{}'.format(all_lb_name_list))
        # print('Tagged (un-normalized) ELBs:\n{}'.format(arn_list))

        normalized_arn_list = normalize_arn_list(arn_list)
        tagged_arn_set = set(normalized_arn_list)
        untagged_set = set(all_lb_name_list).difference(tagged_arn_set)

        untagged_set_len = len(untagged_set)
        if untagged_set_len > 0:
            ret_val = 'Found {} untagged of {} total (classic)ELB\n'.format(untagged_set_len, total_lb_count)
            sorted_untagged_table_list = sorted(untagged_set)
            index = 0
            for curr_name in sorted_untagged_table_list:
                index += 1
                ret_val += '    {}) {}\n'.format(index, curr_name)
        else:
            ret_val = 'All {} ELBs (classic) tagged.\n'.format(total_lb_count)

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during ELB phase. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))
        ret_val += '  ELB had an error processing results. Check logs.'

    return ret_val


def check_for_untagged_log_groups(session, region, tagging_client):
    """
    List all untagged Log Groups
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    log_client = aws_util.get_boto3_client_by_name('logs',session, region)
    response = log_client.describe_log_groups()
    all_log_groups = response['logGroups']
    total_log_groups = len(all_log_groups)
    log_group_list = []
    for curr_log_group in all_log_groups:
        log_group_arn = curr_log_group['arn']
        log_group_list.append(log_group_arn)

    arn_list = get_tagged_resource_list(tagging_client, 'logs:log-group')
    arn_list_len = len(arn_list)
    ret_val = 'CloudWatch Logs found {} tagged log groups\n'.format(arn_list_len)

    try:
        # Note we don't need to normalize this list since we seem to have the ARN.
        untagged_set = set(log_group_list).difference(set(arn_list))

        untagged_set_len = len(untagged_set)
        if untagged_set_len > 0:
            ret_val = 'Found {} untagged of {} total log groups\n'.format(untagged_set_len, total_log_groups)
            sorted_untagged_table_list = sorted(untagged_set)
            index = 0
            for curr_name in sorted_untagged_table_list:
                index += 1
                ret_val += '    {}) {}\n'.format(index, curr_name)
        else:
            ret_val = 'All {} Log Groups tagged.\n'.format(total_log_groups)

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during Log Group phase. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))
        ret_val += '  Log Group had an error processing results. Check logs.'

    return ret_val


def check_for_untagged_rds_instances(session, region, tagging_client):
    """
    List all untagged RDS Instances resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """

    arn_list = get_tagged_resource_list(tagging_client, 'rds:db')
    arn_list_len = len(arn_list)
    ret_val = 'RDS found {} tagged Instances\n'.format(arn_list_len)

    return ret_val


def check_for_untagged_rds_groups(session, region, tagging_client):
    """
    List all untagged RDS Groups resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    arn_list = get_tagged_resource_list(tagging_client, 'rds:cluster')
    arn_list_len = len(arn_list)
    ret_val = 'RDS Groups found {} tagged clusters\n'.format(arn_list_len)

    return ret_val


def check_for_untagged_s3_buckets(session, region, tagging_client):
    """
    List all untagged S3 resources
    and estimate percent tagged resource of this type.
    :param session:  session to the AWS account.
    :param region: AWS Region:  us-east-1
    :param tagging_client: boto3 client for reading tags
    :return: text in SlackUI format with report values.
    """
    ret_val = "S3 check ..."
    try:
        s3_client = aws_util.get_s3_client(session, region)
        s3_bucket_name_list = []

        response = s3_client.list_buckets()
        all_s3_buckets = response['Buckets']
        for curr_bucket in all_s3_buckets:
            s3_bucket_name_list.append(curr_bucket['Name'])

        total_s3_buckets = len(s3_bucket_name_list)

        arn_list = get_tagged_resource_list_globally(session, 's3')
        normalize_s3_arn_list = normalize_s3_list(arn_list)
        arn_list_len = len(normalize_s3_arn_list)
        ret_val = 'S3 found {} tagged of {} total buckets\n'.format(arn_list_len, total_s3_buckets)

        untagged_set = set(s3_bucket_name_list).difference(set(normalize_s3_arn_list))

        untagged_set_len = len(untagged_set)
        if untagged_set_len > 0:
            ret_val = 'Found S3 {} untagged of {} total buckets\n'.format(untagged_set_len, total_s3_buckets)
            sorted_untagged_table_list = sorted(untagged_set)
            index = 0
            for curr_name in sorted_untagged_table_list:
                index += 1
                ret_val += '    {}) {}\n'.format(index, curr_name)
        else:
            ret_val = 'All {} S3 buckets tagged.\n'.format(total_s3_buckets)

        return ret_val
    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during S3 phase. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))
        ret_val += 'Error during S3 phase. Check logs\n'

    return ret_val


def get_tagged_resource_list_globally(session, resource_type):
    """
    S3 is a global-ish service and needs to be treated differently.
    We need to get the tags for all the (likely) regions.
    :param session:
    :param resource_type:
    :return:
    """
    # Get tagging clients from several regions.
    tagging_client_us_east_1 = aws_util.get_tagging_client(session, 'us-east-1')
    tagging_client_us_east_2 = aws_util.get_tagging_client(session, 'us-east-2')
    tagging_client_us_west_2 = aws_util.get_tagging_client(session, 'us-west-2')
    tagging_client_us_west_1 = aws_util.get_tagging_client(session, 'us-west-1')
    tagging_client_ap_southeast_2 = aws_util.get_tagging_client(session, 'ap-southeast-2')
    tagging_client_eu_west_1 = aws_util.get_tagging_client(session, 'eu-west-1')

    arn_list_us_east_1 = get_tagged_resource_list(tagging_client_us_east_1, resource_type)
    arn_list_us_east_2 = get_tagged_resource_list(tagging_client_us_east_2, resource_type)
    arn_list_us_west_2 = get_tagged_resource_list(tagging_client_us_west_2, resource_type)
    arn_list_us_west_1 = get_tagged_resource_list(tagging_client_us_west_1, resource_type)
    arn_list_ap_southeast_2 = get_tagged_resource_list(tagging_client_ap_southeast_2, resource_type)
    arn_list_eu_west_1 = get_tagged_resource_list(tagging_client_eu_west_1, resource_type)

    arn_list = []
    arn_list.extend(arn_list_us_east_1)
    arn_list.extend(arn_list_us_east_2)
    arn_list.extend(arn_list_us_west_2)
    arn_list.extend(arn_list_us_west_1)
    arn_list.extend(arn_list_ap_southeast_2)
    arn_list.extend(arn_list_eu_west_1)

    print('{} found the following number of tagged items.\n'
          'us-east-1 {}, us-east-2 {}, us-west-2 {}, us-west-1 {},'
          'ap-southeast-2 {}, eu-west-1 {}'.format(resource_type, len(arn_list_us_east_1),
                                                   len(arn_list_us_east_2), len(arn_list_us_west_2),
                                                   len(arn_list_us_west_1), len(arn_list_ap_southeast_2),
                                                   len(arn_list_eu_west_1)))

    return arn_list


def get_tagged_resource_list(tagging_client, resource_type, get_more_list=None, pagination_token=None):
    """
    Use boto3 tagging client to get list of all resources that
    have the Spend_Category tag.
    :param tagging_client:
    :param resource_type: sting like: 'dynamodb:table'
    :param get_more_list: list passed only during pagination to hold current results.
    :param pagination_token: sting passed for recursive call only if previous result had pagination_token.
    :return: list of results.
    """
    if pagination_token is not None:
        list_len = len(get_more_list)
        print('PaginationToken={}'.format(pagination_token))
        print('Recursive call already has {} items in list'.format(list_len))
        arn_list = get_more_list
    else:
        arn_list = []

    try:
        if pagination_token:
            tagged_response = tagging_client.get_resources(
                PaginationToken=pagination_token,
                TagFilters=[{'Key': 'Spend_Category'}],
                ResourceTypeFilters=[resource_type]
            )
        else:
            tagged_response = tagging_client.get_resources(
                TagFilters=[{'Key': 'Spend_Category'}],
                ResourceTypeFilters=[resource_type]
            )

        resource_tag_mapping_list = tagged_response['ResourceTagMappingList']

        for curr_resource in resource_tag_mapping_list:
            curr_arn = curr_resource['ResourceARN']
            arn_list.append(curr_arn)

        if 'PaginationToken' in tagged_response:
            pagination_token = tagged_response['PaginationToken']
            if pagination_token:
                print('WARN tagging_client.get_resources() has more results: PaginationToken={}'.format(pagination_token))
                arn_list = get_tagged_resource_list(tagging_client, resource_type, arn_list, pagination_token)

    except Exception as ex:
        # Report back an error to the user, but ask to check logs.
        template = 'Failed during get_tagged_resource_list. type {0} occurred. Arguments:\n{1!r}'
        print(template.format(type(ex).__name__, ex.args))
        traceback_str = traceback.format_exc()
        print('Error traceback \n{}'.format(traceback_str))

    return arn_list


def normalize_arn_list(arn_list):
    """
    Given a list of ARNs normalize the list by removing everything before the '\'
    :param arn_list: list or ARNs in the format 'arn:aws:dynamodb:us-east-1:638782101961:table/FeedGroups'
    :return: list normalized to look like 'FeedGroups'
    """
    normalize_list = []
    for curr_arn in arn_list:
        if '/' in curr_arn:
            curr_arn = curr_arn.split('/')[1]
        normalize_list.append(curr_arn)

    return normalize_list


def write_untagged_items(untagged_items_set, total_items_len, description):
    """
    Method to list all untagged items.
    :param untagged_items_set:
    :param total_items_len:
    :param description:
    :return:
    """
    ret_val = ''
    untagged_set_len = len(untagged_items_set)
    if untagged_set_len > 0:
        ret_val = 'Found {} untagged of {} total {}\n'\
            .format(untagged_set_len, total_items_len, description)
        sorted_untagged_table_list = sorted(untagged_items_set)
        index = 0
        for curr_name in sorted_untagged_table_list:
            index += 1
            ret_val += '    {}) {}\n'.format(index, curr_name)
    else:
        ret_val = 'All {} {} tagged.\n'.format(total_items_len, description)

    return ret_val


def normalize_elasticache_list(elasticache_list):
    """
    Need to convert this:
    arn:aws:elasticache:us-east-1:638782101961:cluster:recsys-b-20170525-0001-001
    into:
    recsys-b-20170525
    and eliminate duplicates.


    :param elasticache_list: Raw ARN with duplicates.
    :return: deduplicated list like: recsys-b-20170525
    """
    trimmed_list = []
    for curr_arn in elasticache_list:
        post_fix = curr_arn.rpartition(':')[2]
        element = post_fix.rpartition('-')[0]
        element = element.rpartition('-')[0]
        trimmed_list.append(element)
    ret_val = list(set(trimmed_list))
    return ret_val


def normalize_s3_list(s3_arn_list):
    """
    Need to convert:
    arn:aws:s3:::roku-downloader-638782101961
    into:
    roku-downloader-638782101961
    :param s3_arn_list:
    :return:
    """
    ret_val_list = []
    for curr_arn in s3_arn_list:
        post_fix = curr_arn.rpartition(':')[2]
        ret_val_list.append(post_fix)
    return ret_val_list


def get_type_from_args(args):
    """
    Parse the args parameters and return of string of types
    :param args:
    :return:
    """
    print('get_type_from_args() args={}'.format(args))
    if args.table is not None:
        return args.table
    return ''
