"""
These might be useful helper functions ported over from tools repo.
Some of this was back when using boto (i.e. pre boto3), so will move
the useful functions to the "aws_utils.py" if they are found to
have a use beyond tagging.
"""
import os
import ssl

import re
import boto3

ELB_CONN_DRAINING_TIMEOUT = 10
ELB_HEALTHCHECK_INTERVAL = 27
ELB_HEALTHCHECK_TIMEOUT = 5
ELB_HEALTHY_THERSHOLD = 2
ELB_UNHEALTHY_THERSHOLD = 2

# EC2
ADDRESSES = 'Addresses'
ALIAS_TARGET = 'AliasTarget'
AWS_ASG_NAME = 'aws:autoscaling:groupName'
CIDR_IP = 'CidrIp'
DESCRIPTION = 'Description'
DNS_NAME = 'DNSName'
FROM_PORT = 'FromPort'
GROUP_ID = 'GroupId'
GROUP_NAME = 'GroupName'
GROUPS = 'Groups'
HEALTH_CHECK = 'HealthCheck'
HEALTH_STATUS = 'HealthStatus'
HOSTED_ZONES = 'HostedZones'
ID = 'Id'
INSTANCE_ID = 'InstanceId'
INSTANCE_TYPE = 'InstanceType'
INSTANCES = 'Instances'
IMAGE_ID = 'ImageId'
IMAGE_LOCATION = 'ImageLocation'
IMAGES = 'Images'
INSTANCE_PORT = 'InstancePort'
IP_PROTOCOL = 'IpProtocol'
IP_RANGES = 'IpRanges'
KEY_NAME = 'KeyName'
LAUNCH_TIME = 'LaunchTime'
EC2_LIFECYCLE_STATE = 'LifecycleState'
LISTENER = 'Listener'
LISTENERS = 'Listeners'
LISTENER_DESCRIPTIONS = 'ListenerDescriptions'
LOAD_BALANCER_DESCRIPTIONS = 'LoadBalancerDescriptions'
LOAD_BALANCER_NAME = 'LoadBalancerName'
LOAD_BALANCER_PORT = 'LoadBalancerPort'
NAME = 'Name'
PLATFORM = 'Platform'
PRIVATE_DNS_NAME = 'PrivateDnsName'
PRIVATE_IP_ADDRESS = 'PrivateIpAddress'
PUBLIC_DNS_NAME = 'PublicDnsName'
PUBLIC_IP = 'PublicIp'
PUBLIC_IP_ADDRESS = 'PublicIpAddress'
RESERVATIONS = 'Reservations'
RESOURCE_RECORDS = 'ResourceRecords'
RESOURCE_RECORD_SETS = 'ResourceRecordSets'
SECURITY_GROUPS = 'SecurityGroups'
STATE = 'State'
TAGS = 'Tags'
TARGET = 'Target'
TO_PORT = 'ToPort'
TYPE = 'Type'
VALUE = 'Value'

# ASG
ASG = 'AutoScalingGroup'
ASGS = 'AutoScalingGroups'
ASG_ARN = 'AutoScalingGroupARN'
ASG_NAME = 'AutoScalingGroupName'
ASG_NAMES = 'AutoScalingGroupNames'
ASG_HEALTHCHECK_GRACEPERIOD = 'healthCheckGracePeriod'
ASG_COOLDOWN= 'DefaultCooldown'
ASG_MIN_SIZE = 'MinSize'
ASG_MAX_SIZE = 'MaxSize'
ASG_DESIRED_CAPACITY = 'DesiredCapacity'
#ASG_DESIRED_SIZE = 'DesiredSize'

AVAILABILITY_ZONES = 'AvailabilityZones'
ZONE_NAME = 'ZoneName'

SGS = 'SecurityGroups'

# Launch configuration
LC = 'LaunchConfiguration'
LCS = 'LaunchConfigurations'
LC_BLOCKDEVICEMAPPINGS = 'BlockDeviceMappings'
LC_IAM = 'IamInstanceProfile'
LC_IMAGE = 'ImageId'
LC_INSTANCETYPE = 'InstanceType'
LC_IAMINSTANCEPROFILE = 'IamInstanceProfile'
LC_EBSOPTIMIZED = 'EbsOptimized'
LC_KEYNAME = 'KeyName'
LC_NAME = 'LaunchConfigurationName'
LC_PUBLICIP = 'AssociatePublicIpAddress'
LC_USERDATA = 'UserData'
LC_VOLUMESIZE = 'VolumeSize'
LC_VOLUMETYPE = 'VolumeType'

VPCS = 'Vpcs'
VPC_ID = 'VpcId'

# ECS
ECS_CLUSTER = 'cluster'
ECS_CLUSTERS = 'clusters'
ECS_CLUSTER_ARNS = 'clusterArns'
ECS_CLUSTER_NAME = 'clusterName'
#CONTAINERS = 'containers'
ECS_CONTAINER_DEF = 'containerDefinitions'
ECS_CONTAINER_INSTANCES = 'containerInstances'
ECS_CONTAINER_INSTANCE_ARN = 'containerInstanceArn'
ECS_CONTAINER_INSTANCE_ARNS = 'containerInstanceArns'
ECS_INSTANCE_ID = 'ec2InstanceId'
ECS_EVENTS = 'events'
ECS_EVENT_CREATED_AT = 'createdAt'
ECS_SERVICES = 'services'
ECS_SERVICE_NAME = 'serviceName'
ECS_SERVICE_ARN = 'serviceArn'
ECS_SERVICE_ARNS = 'serviceArns'
ECS_STATUS = 'status'
ECS_TASK_ARNS = 'taskArns'
ECS_TASK_DEF = 'taskDefinition'
ECS_TASK_DEF_ARN = 'taskDefinitionArn'
ECS_TASK_DEF_ARNS = 'taskDefinitionArns'
ECS_TASKS_RUNNING_COUNT = 'runningTasksCount'

ECS_PENDING_COUNT = 'pendingCount'
ECS_DESIRED_COUNT = 'desiredCount'
ECS_RUNNING_COUNT = 'runningCount'
ECS_MESSAGE = 'message'

#TASKS = 'tasks'
ECS_VOLUMES = 'volumes'

# Misc
NEXTTOKEN = 'NextToken'


def clean_name(name):
    """ Return an identifier for Graphviz """
    name = name.replace('-', '_').replace('.', '__')
    return re.sub('\W', '', name)


def get_tag_from_taglist(taglist, keyname, default=None):
    """
    Utility for boto3 style tag list
    """
    if not taglist:
        return default

    if type(taglist) != list:
        print "WARNING: get_tag_from_taglist needs a list (got %s)" % taglist
        return default

    for tag_dict in taglist:
        if tag_dict.get('Key', None) == keyname:
            return tag_dict['Value']
    return default


def get_tagdict_from_boto3_tags(taglist):
    if taglist is None:
        return {}
    return dict((t['Key'], t['Value']) for t in taglist)


def get_aws_credentials(profile=None, region=None):
    _region = region if region else os.environ.get('AWS_REGION', 'us-east-1')
    os.environ['AWS_DEFAULT_REGION'] = _region

    if not profile:
        if 'AWS_DEFAULT_PROFILE' in os.environ:
            profile = os.environ['AWS_DEFAULT_PROFILE']
        elif 'AWS_PROFILE' in os.environ:
            profile = os.environ['AWS_PROFILE']

    key, secret, config_profile = None, None, None
    if profile:
        _home_dir = os.environ.get('HOME', os.path.expanduser('~'))
        with open("%s/.aws/credentials" % _home_dir) as fd:
            get_access = False
            for line in fd:
                line = re.sub('\s+#.*', '', line)
                if re.match('^\s*$', line):
                    continue
                m = re.search('^\\s*\\[(profile\\s+)?([\d\w\-]+)\\]',
                              line, re.I)
                if m:
                    if get_access:
                        break
                    acct_alias = m.group(2)
                    if acct_alias == profile:
                        get_access = True
                    continue
                if get_access:
                    m = re.search('^\\s*aws_access_key_id\\s*=\\s*(.+)$',
                                  line, re.I)
                    if m:
                        key = m.group(1)
                    m = re.search('^\\s*aws_secret_access_key\\s*=\\s*(.+)$',
                                  line, re.I)
                    if m:
                        secret = m.group(1)

        if not key or not secret:
            if os.path.exists('%s/.aws/config' % _home_dir):
                with open('%s/.aws/config' % _home_dir) as fd:
                    for line in fd:
                        if re.match('^\s*\[profile\s+%s\]' % profile, line, re.I):
                            config_profile = profile
                            print "Using profile %s in ~/.aws/config" % profile
                            os.environ['AWS_PROFILE'] = profile
                            os.environ['AWS_DEFAULT_PROFILE'] = profile
                            for key in ('AWS_ACCESS_KEY_ID',
                                        'AWS_ACCESS_KEY',
                                        'AWS_SECRET_ACCESS_KEY',
                                        'AWS_SECRET_KEY'):
                                try:
                                    del os.environ[key]
                                except KeyError:
                                    pass
            if not config_profile:
                raise ValueError('Unable to find profile %s' % profile)
            _access = {'aws_profile': profile}

        else:
            print "Using profile %s in ~/.aws/credentials" % profile
            os.environ.update({
                'AWS_ACCESS_KEY_ID': key,
                'AWS_ACCESS_KEY': key,
                'AWS_SECRET_ACCESS_KEY': secret,
                'AWS_SECRET_KEY': secret
            })
            try:
                del os.environ['AWS_DEFAULT_PROFILE']
            except KeyError:
                pass
            _access = {'aws_access_key_id': key, 'aws_secret_access_key': secret}
        #iam_acct_num = \
        #    int(boto3.resource('iam').User('readonly').arn.split(':')[4])
        iam_acct_num = profile
    else:
        key, secret = (os.environ.get('AWS_ACCESS_KEY_ID',
                                      os.environ.get('AWS_ACCESS_KEY', None)),
                       os.environ.get('AWS_SECRET_ACCESS_KEY',
                                      os.environ.get('AWS_SECRET_KEY', None)))
        if not key or not secret:
            raise ValueError('Please specify acct_num and region')
        _access = {'aws_access_key_id': key, 'aws_secret_access_key': secret}
        iam_acct_num = fetch_ec2_iam_info(_access)

    return iam_acct_num, _region, _access


def get_all_without_token(func, list_key, *args):
    my_list = []
    next_token = None
    while True:
        if next_token:
            _list = func(*args, NextToken=next_token)
        else:
            _list = func(*args)
        my_list.extend(_list[list_key])
        next_token = _list.get(NEXTTOKEN, None)
        if not next_token:
            break
    return my_list


def get_all_asgs(asg_client, asg_names=None):
    if asg_names and type(asg_names) != list:
        raise ValueError("Please only pass in a list of asg_names")

    asg_list = []
    next_token = None
    while True:
        args = {}
        if asg_names:
            args[ASG_NAMES] = asg_names
        if next_token:
            args[NEXTTOKEN] = next_token
        _list = asg_client.describe_auto_scaling_groups(**args)
        asg_list.extend(_list[ASGS])
        next_token = _list.get(NEXTTOKEN, None)
        if not next_token:
            break
    return asg_list


def get_all_launch_configurations(asg_client):
    lc_list = []
    next_token = None
    while True:
        if next_token:
            _list = asg_client.describe_launch_configurations(
                NextToken=next_token)
        else:
            _list = asg_client.describe_launch_configurations()
        lc_list.extend(_list[LCS])
        next_token = _list.get(NEXTTOKEN, None)
        if not next_token:
            break
    return lc_list


def get_image_info(instance, IMAGEID2IMAGE):
    return '%s [%s]' % (
        instance[IMAGE_ID],
        (IMAGEID2IMAGE[instance[IMAGE_ID]][NAME]
         if instance[IMAGE_ID] in IMAGEID2IMAGE else 'UNKNOWN'))


def fetch_route53_records(region, access):

    recordsets = []

    client3 = boto3.client('route53')
    for domain in client3.list_hosted_zones()[HOSTED_ZONES]:
        #print domain
        rr_set = client3.list_resource_record_sets(
                HostedZoneId=domain[ID])[RESOURCE_RECORD_SETS]
        for record in rr_set:
            #print "\t%s" % record
            if record[TYPE] == 'A' or record[TYPE] == 'CNAME':
                recordsets.append(record)
    return recordsets


def fetch_ec2_iam_info(access):
    """
    :param access:
    :return:
    """
    # ToDo: (alan) Make a boto3 version of this.

    # conn_iam = boto.connect_iam(**access)
    # try:
    #     return conn_iam.get_user()['get_user_response']['get_user_result']['user']['arn'].split(':')[4]
    # except ClientError, e:
    #     print "ERROR: %s" % e
    #     return None


def fetch_ec2_info(region, access):
    # TODO: ecs API when it is stabilized
    #conn2 = boto.ec2containerservice.connect_to_region(region, **access)
    #ecs_clusters = conn2.list_clusters()
    #ecs_instances = conn2.list_container_instances()
    instanceid2eip = {}

    conn3 = boto3.client('ec2', region_name=region)
    for info in conn3.describe_addresses()[ADDRESSES]:
        if INSTANCE_ID in info:
            inst_id = info[INSTANCE_ID]
            eip = info[PUBLIC_IP]
            instanceid2eip[inst_id] = eip
        else:
            print("WARNING: EIP %s is not associated with any instance" %
                  info[PUBLIC_IP])

    # AMI ids
    imageids = set()
    instid2inst = {}
    try:
        reservations_dict = conn3.describe_instances()[RESERVATIONS]
    except ssl.SSLError, e:
        reservations_dict = {}
        print "WARNING: %s" % e

    for reservation_dict in reservations_dict:
        for inst_dict in reservation_dict[INSTANCES]:
            #print inst_dict.keys()
            #print inst_dict
            inst_id = inst_dict[INSTANCE_ID]
            image_id = inst_dict[IMAGE_ID]
            imageids.add(image_id)
            instid2inst[inst_id] = inst_dict

    sgroupid2sgroup = {}
    if len(imageids) > 0:
        images = conn3.describe_images(ImageIds=list(imageids))[IMAGES]
        imageid2image = dict((image[IMAGE_ID], image) for image in images)
        sgroups = conn3.describe_security_groups()[SECURITY_GROUPS]
        #print sgroups
        for sgroup in sgroups:
            sgroupid2sgroup[sgroup[GROUP_ID]] = sgroup
    else:
        imageid2image = {}

    return instanceid2eip, instid2inst, sgroupid2sgroup, imageid2image


def fetch_elb(region, access=None):
    elbdnsname2elb = {}
    elb_conn = boto3.client('elb', region_name=region)
    elbs = elb_conn.describe_load_balancers()[LOAD_BALANCER_DESCRIPTIONS]
    for elb in elbs:
        dns_name = elb[DNS_NAME]
        elbdnsname2elb[dns_name] = elb
    return elbdnsname2elb


# ============== Getters ================

# TODO(kevin): clean up names

def get_elbs(region_name, elbname):
    elb_client = boto3.client('elb', region_name=region_name)
    try:
        elbs = elb_client.describe_load_balancers(
            LoadBalancerNames=[elbname])[LOAD_BALANCER_DESCRIPTIONS]
    except botocore.exceptions.ClientError:
        return []
    return [e[LOAD_BALANCER_NAME] for e in elbs]


def get_all_availability_zones(region_name):
    ec2_client = boto3.client('ec2', region_name=region_name)
    zones = ec2_client.describe_availability_zones()[AVAILABILITY_ZONES]
    return [z[ZONE_NAME] for z in zones if z[STATE] == 'available']


def get_subnet_ids(vpc_name, region_name):
    ec2_client = boto3.resource('ec2', region_name=region_name)
    vpcs = list(ec2_client.vpcs.filter(Filters=[{'Name': 'tag:Name', 'Values': [vpc_name]}]))
    if len(vpcs) != 1:
        raise RuntimeError("There needs to be ONE VPC named %s" % vpc_name)
    vpc = vpcs[0]
    subnet_ids = [s.id for s in vpc.subnets.all()]
    return subnet_ids


# ================ Docker + ECS ==================


def get_all_ecs_services_in_cluster(ecs_client, cluster_name, load_events=False):
    service_list = []
    next_token = None
    while True:
        args = {ECS_CLUSTER: cluster_name}
        if next_token:
            args[NEXTTOKEN] = next_token
        _list = ecs_client.list_services(**args)

        service_list.extend(_list[ECS_SERVICE_ARNS])
        next_token = _list.get(NEXTTOKEN, None)
        if not next_token:
            break

    services = ecs_client.describe_services(
        cluster=cluster_name, services=service_list)[ECS_SERVICES]
    if not load_events:
        _services = []
        for service in services:
            try:
                del service[ECS_EVENTS]
            except KeyError:
                pass
            _services.append(service)
        return _services

    return services


def get_all_ecs_instances_in_cluster(ecs_client, cluster_name):
    instance_arns = []
    next_token = None
    while True:
        args = {ECS_CLUSTER: cluster_name}
        if next_token:
            args[NEXTTOKEN] = next_token
        _list = ecs_client.list_container_instances(**args)
        instance_arns.extend(_list[ECS_CONTAINER_INSTANCE_ARNS])
        next_token = _list.get(NEXTTOKEN, None)
        if not next_token:
            break
    if len(instance_arns) == 0:
        return []

    instances = ecs_client.describe_container_instances(
        cluster=cluster_name,
        containerInstances=instance_arns)[ECS_CONTAINER_INSTANCES]

    return instances


def get_docker_containers_info_list(instid, shell_buffer):
    mapping_start = {}  # mapping of key to start-end index
    mapping_end = {}  # mapping of key to start-end index

    def _extract_key(key, line):
        if key not in mapping_start:
            print("ERROR: get_docker_containers_info_list"
                  " unable to find key '%s' in line:%s" % (key, line))
            return None
        start_idx = mapping_start[key]
        end_idx = mapping_end[key] if key in mapping_end else len(line)
        return line[start_idx:end_idx].rstrip('\n').rstrip(' ').lstrip(' ')

    class ContainerInfo(object):
        def __init__(self, instance_id):
            self.instance_id = instance_id
            self.container_id = None
            self.image = None
            self.status = None
            self.portstr = ''
            self.names = None

        def __repr__(self):
            return "%s[%s#%s]" % (self.names, self.instance_id, self.portstr)

        @property
        def id(self):
            return clean_name("%s_%s" % (self.instance_id, self.names))

        @property
        def name(self):
            if self.names is None:
                return None
            if self.names == 'ecs-agent':
                return self.names
            m = re.search('^ecs\-(.+)', self.names)
            if m:
                # ecs-linearapi-etl-4-linearapi-etl-feb8f69b97acb8db8301
                return re.sub('\-\d+\-.+$', '', m.group(1))
            return self.names

        @property
        def version(self):
            if self.names is None:
                return None
            m = re.search('\-(\d+)\-', self.names)
            if m:
                # ecs-linearapi-etl-4-linearapi-etl-feb8f69b97acb8db8301
                return m.group(1)
            return ''

        @property
        def ecs_launched(self):
            return re.search('^ecs\-', self.names)

        def get_ports(self):
            hostport2containerport = {}
            containerport2hostport = {}
            for port_info in re.split(',\s*', self.portstr):
                m = re.search('(\d+)\->(\d+)', port_info)
                if m:
                    host_port, container_port = m.group(1, 2)
                    host_port, container_port = \
                        int(host_port), int(container_port)
                    hostport2containerport[host_port] = container_port
                    containerport2hostport[container_port] = host_port
            return hostport2containerport, containerport2hostport

    containers_info = []
    for line in shell_buffer:
        line = line.rstrip('\n')
        if 'CONTAINER ID' in line:
            prev_key = None
            for key in re.split('\s\s+', line):
                curr_key_idx = line.index(key)
                mapping_start[key] = curr_key_idx
                if prev_key is not None:
                    mapping_end[prev_key] = curr_key_idx
                prev_key = key
        elif _extract_key('NAMES', line) != '':
            container_id = _extract_key('CONTAINER ID', line)
            if container_id is None:
                continue
            container = ContainerInfo(instid)
            container.container_id = container_id
            container.image = _extract_key('IMAGE', line)
            container.status = _extract_key('STATUS', line)
            container.portstr = _extract_key('PORTS', line)
            container.names = _extract_key('NAMES', line)
            containers_info.append(container)

    return containers_info


def get_sorted_docker_container_ids(containers_info):
    containername2id = {}
    basecontainername2id = {}
    for container_info in containers_info:
        if ('registry' in container_info.name or
                'ecs-agent' in container_info.name):
            basecontainername2id[container_info.name] = container_info.id
        else:
            containername2id[container_info.name] = container_info.id

    ids = [id for name, id in sorted(containername2id.iteritems())]
    ids.extend([id for name, id in sorted(basecontainername2id.iteritems())])
    return ids
