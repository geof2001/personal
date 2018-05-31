"""Implements Flamegraph command by asnyder"""
from __future__ import print_function
import json
import traceback
import boto3
import botocore
import time
import datetime
from boto3.dynamodb.conditions import Key, Attr
import util.slack_ui_util as slack_ui_util
from util.slack_ui_util import ShowSlackError
import util.aws_util as aws_util
import util.bud_helper_util as bud_helper_util
from cmd_interface import CmdInterface


class CmdFlamegraph(CmdInterface):

    def get_help_title(self):
        """
        Ruturn short description used in global help summary
        and title of commands help page
        """
        return 'Create flamegraphs for docker service running in ECR Cluster'

    def get_help_text(self):
        """
        Return help text for your command in slack format here.
        """
        help_text = "*Format:* _/bud flamegraph <action> -e <env> -r <region> -s <service> -t <run_time>_\n"
        help_text += "*Example:* _/bud flamegraph create -e dev -r us-east-1 -s content -t 30_\n\n"
        help_text += "*<Create>* _Create_ make a flamegraph\n"
        help_text += "           _Profiles docker service running in ECR_\n"
        help_text += "           _*-s* is name of service_\n"
        help_text += "           _*-t* is how long to run the profiler_\n"

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

            if response_url:
                self.set_response_url(response_url)

            # Call aws_util or bud_help_util method

            print("%s invokes %s" % (self.__class__.__name__, sub_command))
            if sub_command == 'create':
                # Create
                return self.handle_create_command(args)
            if sub_command == 'debug':
                # You need to modify this
                return self.handle_debug_command(args)
            title = 'Flamegraph unkown subcommand'
            text = 'Unknown sub-command: {}'.format(sub_command)
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
        try:
            start = datetime.datetime.now()

            args_dict = event.get('args')
            response_url = event.get('response_url')
            custom_data = event.get('custom_data')

            # debug section verify the data makes it accross as expected.
            print('args={}'.format(args_dict))
            print('response_url={}'.format(response_url))
            print('custom_data={}'.format(custom_data))

            region = args_dict['regions'][0]
            env = args_dict['envs'][0]
            service = args_dict['services'][0]

            run_time_in_sec = 20
            if args_dict['table']:
                run_time_in_sec = args_dict['table']

            bud_helper_util.print_delta_time(start, 'init parms passed to longtask')

            print('(debug) env={}, region={}, service={}'.format(env, region, service))
            print('(debug) runtime(-t): {}'.format(run_time_in_sec))
            run_time_in_sec = validate_run_time_value(run_time_in_sec)
            print('(debug) run_time after validation: {}'.format(run_time_in_sec))
            session = aws_util.create_session(env)

            # Find the ServiceDiscovery table for env/region.
            bud_helper_util.print_delta_time(start, 'create_session')

            service_discovery_table_name = get_service_discovery_table_name(session, region)
            bud_helper_util.print_delta_time(start, 'get_service_discovery_table_name ')

            print('Found ServiceDiscoveryTable: {}'.format(service_discovery_table_name))

            host_info = get_info_from_service_discovery_table(
                session, region, service_discovery_table_name, service
            )
            bud_helper_util.print_delta_time(start, 'get_info_from_service_discovery_table')

            instance_id = host_info['hostInstanceId']
            host_url = host_info['externalHost']

            docker_id = run_docker_ps_on_host(session, region, host_info)
            bud_helper_util.print_delta_time(start, 'run_docker_ps_on_host')

            print('Found Container Id: {}'.format(docker_id))
            # Let user know we found the container.
            title = "Flamegraph find docker container"
            text = 'docker container: {}\n instance id: {}\nhost: {}'\
                .format(docker_id, instance_id, host_url)
            slack_ui_util.text_command_response(
                title, text, post=True, response_url=response_url)
            bud_helper_util.print_delta_time(start, 'slack-ui docker container')

            command_id = start_flamegraph_script_on_host(session, region, host_info, docker_id, run_time_in_sec)
            bud_helper_util.print_delta_time(start, 'start_flamegraph_script_on_host')

            # Let user know we have started the script after a few second delay.
            time.sleep(5)
            title = 'Flamegraph start profile script'
            text = 'runtime: {}\nid: {}'\
                .format(run_time_in_sec, command_id)
            slack_ui_util.text_command_response(
                title, text, post=True, response_url=response_url)

            # Now wait and look for the result as waiting, so see how
            # how that feels on Slack UI.

            wait_time_in_sec = 0
            SLEEP_INTERVAL = 3 # seconds
            ssm_client = aws_util.get_boto3_client_by_name('ssm', session, region)
            while wait_time_in_sec < run_time_in_sec+30:
                time.sleep(SLEEP_INTERVAL)
                wait_time_in_sec += SLEEP_INTERVAL
                # Get the output from the command invocation
                invocation_response = ssm_client.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=host_info['hostInstanceId']
                )

                print('SSM: invocation ({}) response: {}'
                      .format(wait_time_in_sec, invocation_response))
                status = invocation_response['Status']
                print("Status = {}".format(status))
                if 'Success' == status:
                    print("SSM 'docker ps' call took {} sec."
                          .format(wait_time_in_sec))
                    break
                if 'Failed' == status:
                    print('Failed after {} sec.'.format(wait_time_in_sec))
                    break

            script_stage_txt = '{} script'.format(status)
            bud_helper_util.print_delta_time(start, script_stage_txt)

            # ToDo: We are going to replace with a check for a new
            # svg file with the proper pid.
            if status != 'Success' and status != 'Failed':
                # TEMPORARY below to test transfers.
                dest_file_location = transfer_svg_file_to_s3_bucket(ssm_client, instance_id, invocation_response, region, response_url) # remove after testing.

                title = 'Flamegraph error'
                text = 'Flamegraph not created. See logs. status={}'.format(status)
                slack_ui_util.text_command_response(
                    title, text, post=True, response_url=response_url)
                return
            else:
                # success look for file and transfer it to S3 bucket.
                dest_file_location = transfer_svg_file_to_s3_bucket(ssm_client, instance_id, invocation_response, region, response_url)

            bud_helper_util.print_delta_time(start,'transfer_svg_file_to_s3_bucket')

            # Confirm SVG file in S3 bucket and return S3 link if found.
            print('This is the step where we would look for S3 file in destination bucket.')
            s3_link_to_svg_file = verify_link_to_svg_file(dest_file_location)

            bud_helper_util.print_delta_time(start, 'verify_link_to_svg_file')

            if s3_link_to_svg_file:
                title = 'Flamegraph link'
                text = 'Link below:\n{}'.format(s3_link_to_svg_file)
                return slack_ui_util.text_command_response(
                    title, text, post=True, response_url=response_url)
            else:
                title = 'Flamegraph transfer error'
                text = 'Flamegraph created, but not transferred. See logs. status={}'.format(status)
                return slack_ui_util.text_command_response(
                title, text, post = True, response_url = response_url)

        except ShowSlackError as sse:
            slack_error_message = str(sse)
            return slack_ui_util.error_response(
                slack_error_message, post=True, response_url=response_url)
        except Exception as ex:
            # Report back an error to the user, but ask to check logs.
            template = 'Failed during execution. type {0} occurred. Arguments:\n{1!r}'
            print(template.format(type(ex).__name__, ex.args))
            traceback_str = traceback.format_exc()
            print('Error traceback \n{}'.format(traceback_str))

            slack_error_message = 'An error occurred (lt). Please check logs.'
            return slack_ui_util.error_response(
                slack_error_message, post=True, response_url=response_url)

    def handle_create_command(self, args):
        """
        Handler to create a flamegraph based on a service name.
        :param args:
        :return:
        """
        start = datetime.datetime.now()

        region = args.regions[0]
        env = args.envs[0]
        service = args.services[0]

        if service:

            print('looking for service: {}'.format(service))

            # Placeholder(reminder) in case we need to pass something for real.
            # Make part of the longtask refactor.
            custom_data = {
                'key1': 'value1',
                'key2': 'value2'
            }

            # Push to lambda function.
            payload = self.create_longtask_payload(args, custom_data)
            lambda_function = boto3.client('lambda')
            response = lambda_function.invoke(
                FunctionName="slackbud-longtasks",
                InvocationType="Event",
                Payload=json.dumps(dict(payload))
            )
            bud_helper_util.print_delta_time(start, 'Invoke longtasks lambda function')
            print('Invoke longtasks lambda function response:\n{}'.format(response))

            bud_helper_util.print_delta_time(start, 'Total time flamegraph handle_create_command')
            return slack_ui_util.text_command_response('_Processing..._', '')
        else:
            # user failed to specify a service.
            print('raise SlackError')
            raise ShowSlackError("Need to specify a service[-s] attribute")

    def handle_create_command_longtask(self, args, response_url):
        """
        If we have a long version of the method this is it.
        :param args:
        :return:
        """

    def handle_debug_command(self, args):
        """
        Placeholder for command
        :param args:
        :return:
        """
        # some test with the new longtasks framework.
        title = 'Flamegraph response'
        text = "Debug sub-command"
        return slack_ui_util.text_command_response(title, text)

    def handle_debug_command_longtask(self, args, response_url):
        """
        Longtask version of the debug command.
        :param args:
        :return:
        """


def get_service_discovery_table_name(session, region):
    """
    The the service discovery table env and region.
    :param env: environment
    :param region: AWS region
    :return: String with name of service discovery table.
    """
    cf_client = aws_util.get_cloudformation_client(session, region)
    response = cf_client.list_exports()

    if response:
        # Look for the export: 'sr-blue-ServiceDiscoveryTable'
        cf_exports = response['Exports']
        for curr_export in cf_exports:
            if 'sr-blue-ServiceDiscoveryTable' in curr_export['Name']:
                return curr_export['Value']

    print('get_service_discovery_table_name failed to find sr-blue-ServiceDiscoveryTable')
    return None


def get_info_from_service_discovery_table(session, region,
                                          service_discovery_table_name, service):
    """
    Get a dictionary with information about which host this runs on.
    :param session:
    :param region:
    :param service_discovery_table_name:
    :param service: name of the service to look for
    :return: dictionary with host and service information.
    """
    dynamo = aws_util.get_dynamo_resource(session, region)
    table = dynamo.Table(service_discovery_table_name)

    response = table.query(
        KeyConditionExpression=Key('serviceName').eq(service)
    )

    items = response['Items']
    print('queries items=\n{}'.format(items))
    # Just get what we need from the first element
    count = response['Count']
    if count > 0:
        first_item = items[0]

        ret_val = {
            'hostInstanceId': first_item['hostInstanceId'],
            'externalHost': first_item['externalHost'],
            'internalHost': first_item['internalHost'],
            'version': first_item['version'],
            'zone': first_item['zone']

        }

        print('Found service on ec2 host: {}'.format(first_item['hostInstanceId']))
        return ret_val
    else:
        error_message = 'Could not find any entries for service: {}'.format(service)
        print(error_message)
        raise ShowSlackError(error_message)
        return None


def does_ssm_have_document_named(session, region, ssm_doc_name):
    """
    Look at AWS EC2 Systems Manager to see if that region as
    a document with the name. AWS documents start with AWS-*,
    custom documents start with Roku-*.
    :param session: session for AWS account
    :param region: region for command
    :param ssm_doc_name: (ssm) systems document name.
    :return: True of document name exsists, otherwise False
    """
    ssm_client = aws_util.get_boto3_client_by_name('ssm', session, region)

    response = ssm_client.list_documents(
        DocumentFilterList=[
            {'key': 'Name', 'value': ssm_doc_name}
        ]
    )

    docs = response['DocumentIdentifiers']
    if len(docs) == 0:
        return False
    return True


def run_docker_ps_on_host(session, region, host_info):
    """
    Run the docker ps command on the host machine, to find the
    docker container id of the service we want to profile.
    :param session:
    :param region:
    :param host_info: dictionary with host information
    :return: string with docker id needed for flamegraph command
    """

    ssm_client = aws_util.get_boto3_client_by_name('ssm', session, region)

    docker_ps_doc_name = 'Roku-DockerPs-20180307'
    if not does_ssm_have_document_named(session, region, docker_ps_doc_name):
        run_docker_ps_json = create_docker_ps_doc()

        print("Didn't find document: {}\ncreating:\n{}".format(docker_ps_doc_name, run_docker_ps_json))

        doc_response = ssm_client.create_document(
            Content=run_docker_ps_json,
            Name=docker_ps_doc_name,
            DocumentType='Command'
        )
        print('SSM: run docker ps create document result:\n{}'.format(doc_response))

    # Try to send the command
    instance_run_list = [host_info['hostInstanceId']]
    send_response = ssm_client.send_command(
        InstanceIds=instance_run_list,
        DocumentName=docker_ps_doc_name,
        TimeoutSeconds=42
    )
    print('SSM: send command result:\n{}'.format(send_response))

    cmd = send_response['Command']
    cmd_id = cmd['CommandId']
    doc_name = cmd['DocumentName']
    status = cmd['Status']

    print("Success (docker ps): cmd_id={}, doc_name={}, status={}"
          .format(cmd_id, doc_name, status))

    # Note: status will typically be "Pending".
    # Need to find a way to know when the command has run.

    wait_time_in_sec = 0
    while wait_time_in_sec < 30:
        time.sleep(1)
        wait_time_in_sec += 1
        # Get the output from the command invocation
        invocation_response = ssm_client.get_command_invocation(
            CommandId=cmd_id,
            InstanceId=host_info['hostInstanceId']
        )

        print('SSM: invocation ({}) response: {}'
              .format(wait_time_in_sec, invocation_response))
        status = invocation_response['Status']
        print("Status(docker ps) = {}".format(status))
        if 'Success' == status:
            print("SSM 'docker ps' call took {} sec."
                  .format(wait_time_in_sec))
            break
        if 'Failed' == status:
            print('Failed (docker ps) after {} sec.'.format(wait_time_in_sec))
            break

    if status == 'Success':
        std_out = invocation_response['StandardOutputContent']
        if std_out:
            docker_id = find_docker_container_id(std_out, host_info)
            if not docker_id:
                # Print information in log to understand why we didn't find id.
                print('ERROR: Failed to find docker container id in:')
                print("Invocation std_out:\n{}".format(std_out))
            return docker_id
        else:
            print("ERROR: Status was success, but no STD_OUT found"
                  " for CommandId={}.".format(cmd_id))
            raise ShowSlackError("Check logs for error message. "
                                 "cmd_id={}".format(cmd_id))

    if status == 'Failed':
        print("ERROR (docker ps): Response status='failed' for CommandId={}".format(cmd_id))
        std_err = invocation_response['StandardErrorContent']
        if std_err:
            print("Invocation std_err:\n{}".format(std_err))
            raise ShowSlackError("Check logs for error message. "
                                 "cmd_id={}".format(cmd_id))

    print('ERROR (docker ps): Unexpected status={} for CommandId={}'
          .format(status, cmd_id))
    raise ShowSlackError("Check logs for error message. "
                         "cmd_id={}".format(cmd_id))


def find_docker_container_id(std_out, host_id):
    """
    Parse the result of a docker ps command looking for
    the container id. Return that.
    If it isn't found log details and raise an error.
    :param std_out: String output of docker ps
    :param host_id: Dictionary Information about service we are looking for.
    :return: String container_id of what we are looking for, otherwise return None
    """
    search_for_image = host_id['version']

    output = std_out.replace('CONTAINER ID', 'CONTAINER_ID')
    lines = output.split('\n')

    container_id_list = []
    image_list = []
    names_list = []
    for curr_line in lines:
        columns = curr_line.split()
        col_len = len(columns)
        if col_len > 3:
            container_id_list.append(columns[0])
            image_list.append(columns[1])
            last_col = col_len-1
            names_list.append(columns[last_col])

    i = 0
    found = False
    print("Searching for: {}".format(search_for_image))
    for curr_id in container_id_list:
        curr_image = image_list[i]
        i += 1
        # will be more efficient later, look for image.
        if search_for_image in curr_image:
            return curr_id

    if not found:
        return None


def create_docker_ps_doc():
    """
    ssm seems to have a problem with YAML documents according to
    this post in Dec. 2017. (2 months ago).
      https://github.com/aws/aws-cli/issues/3013
    Will try JSON formatted document.
    :return:
    """
    ret_val = '{'
    ret_val += ' "schemaVersion": "2.2",'
    ret_val += ' "description": "Run docker ps command",'
    ret_val += ' "mainSteps":['
    ret_val += '  {'
    ret_val += '    "action": "aws:runShellScript",'
    ret_val += '    "name": "runDockerPs",'
    ret_val += '    "inputs": {'
    ret_val += '     "runCommand": ['
    ret_val += '      "docker ps"'
    ret_val += '     ]'
    ret_val += '    }'
    ret_val += '  }'
    ret_val += ' ]'
    ret_val += '}'

    return ret_val


def start_flamegraph_script_on_host(
        session, region, host_info, docker_id, run_time_in_sec):
    """
    Starts the flamegraph script. (A different method look for result though)
    :param session:
    :param region:
    :param host_info:
    :param docker_id:
    :param run_time_in_sec:
    :return: None. Will raise an exception if error.
    """
    print("start_flamegraph_script_on_host. docker_id={}, run_time={}"
          .format(docker_id, run_time_in_sec))

    ssm_client = aws_util.get_boto3_client_by_name('ssm', session, region)

    # Send the command
    instance_run_list = [host_info['hostInstanceId']]

    cmd_list = []
    # ToDo: We will need to create a "dev" and "prod" version of the remote script.
    # When the longtask lambda is split, code will need to know which version to download.
    cmd_list.append('aws s3 cp s3://sr-infra-slackbud-images-us-west-2/scripts/ssm_remote.py /home/ec2-user/flamegraph.py')
    cmd_list.append('sudo python /home/ec2-user/flamegraph.py {} {} flamegraph ssm'.format(docker_id, run_time_in_sec))

    send_response = ssm_client.send_command(
        InstanceIds=instance_run_list,
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': cmd_list,
            'workingDirectory': ['/home/ec2-user'],
            'executionTimeout': ['3542']
        },
        TimeoutSeconds=42
    )
    print('SSM: send command result:\n{}'.format(send_response))

    cmd = send_response['Command']
    cmd_id = cmd['CommandId']
    doc_name = cmd['DocumentName']
    status = cmd['Status']

    print("Success: command ran! cmd_id={}, doc_name={}, status={}"
          .format(cmd_id, doc_name, status))

    return cmd_id


def transfer_svg_file_to_s3_bucket(ssm_client, instance_id, invocation_response, region, response_url):
    """
    The invocation returned 'Success', so check the output (std_out and std_err)
    for the result.

    If successful, transfer the SVG file to an S3 bucket and send a link
    to the file back to the user.

    If an error, send a UI result asking the user to check the logs.
    :return: None
    """
    response_code = invocation_response['ResponseCode']
    std_out_contents = invocation_response['StandardOutputContent']
    std_err_contents = invocation_response['StandardErrorContent']

    # print first 800 characters to log while debugging.
    print('Standard Output:\n{}'.format(std_out_contents[0:800]))

    # Look at the output for the pid file.
    pid = parse_for_std_out_for_pid(std_out_contents[0:800])
    if pid:
        print('Found pid={}'.format(pid))
        dest_file_location = move_svg_to_s3_bucket(ssm_client, instance_id, pid, region)
    else:
        print('Failed to find pid, but running (as test) transfer(s) anyway')
        dest_file_location = move_svg_to_s3_bucket(ssm_client, instance_id, pid, region)

    return dest_file_location


def parse_for_std_out_for_pid(std_out):
    """
    look for a line like this: 'pid=_5464_'
    return '5464'
    :return: pid file.
    """
    print('Looking for pid in standard out.\n{}'.format(std_out))

    lines = std_out.split('\n')
    for line in lines:
        if line.startswith('pid='):
            print('Found line: >{}<'.format(line))
            pid = line.replace('pid=','')
            pid = pid.replace('_','')
            return pid
    print('FAILED to find PID.')
    return 'no-pid'


def parse_std_out_for_pid(std_out):
    """
    The first three lines of std_out should look something like:

    Looking for PID for b90ac5a301a6
    Recording perf data on 1448
    PERFILE2...

    Here we want to part for that and get the number at the
    end of the second line, and confirm it with the docker_id
    which is the end of the first line, and the "PERFILE" which
    should start the thrid line.

    If those conditions are met return the PID.
    If no PID is found return None.

    :param std_out: Start of Standard Out.
    :return: Sting with PID value on success. NONE on Failure.
    """
    content_start = std_out[0:200]

    lines = content_start.split('\n')
    i = 0
    for curr_line in lines:
        i += 1
        print('parse_for_pid line({}): {}'.format(i, curr_line))
        if i == 2:
            parts = curr_line.rsplit(' ',1)
            if len(parts)==2:
                pid = parts[1]
                print('pid = {}'.format(pid))
                return pid
            else:
                print('ERROR: Could not find PID in this line: {}'.format(curr_line[0:100]))
                return None


def move_svg_to_s3_bucket(ssm_client, instance_id, pid, region):
    """
    Use the aws cli command to move the svg file to an s3 bucket.
    :param ssm_client: boto3 client
    :param instance_id: ec2 instance id
    :param pid: pid of the docker container, used to find perf-*.svg file
    :param region: the region you are in. us-east-1 or us-west-2
    :return: The likes S3 location, bucket and keys.
    """
    print('move_svg_to_s3_bucket instance_id={} pid={}'.format(instance_id, pid))
    ymdhm = datetime.datetime.today().strftime('%Y-%m-%d-%H-%M')
    if pid:
        svg_file = 'perf-{}.svg'.format(pid)
        dest_svg_file_name = 'flamegraph-{}-{}.svg'.format(pid, ymdhm)
    else:
        svg_file = 'perf-27551.svg'  # For now we are just testing.
        dest_svg_file_name = 'flamegraph-test-{}.svg'.format(ymdhm)

    print('S3 cp svg_file={} dest_svg_file_name={}'.format(svg_file, dest_svg_file_name))

    send_to_s3infra_west_bucket\
        = 'aws s3 cp {} s3://sr-infra-slackbud-images-us-west-2/svg/{}' \
          ' --acl public-read'.format(svg_file, dest_svg_file_name)

    send_response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [send_to_s3infra_west_bucket],
            'workingDirectory': ['/home/ec2-user'],
            'executionTimeout': ['3541']
        }
    )

    command_id = send_response['Command']['CommandId']

    # sleep on second, to give this time to start before moving on,
    # and then check that is hasn't failed.
    time.sleep(1)

    # stay here while pending up to 10 seconds.
    status = wait_for_completion(ssm_client, instance_id, command_id, 10)
    print('Cmd: aws s3 cp {} ... finished with status: {}'.format(svg_file, status))

    return 'sr-infra-slackbud-images-us-west-2/svg/{}'.format(dest_svg_file_name)


def wait_for_completion(ssm_client, ec2_instance_id, command_id, max_wait_time):
    """
    Wait for an ssm command to either reach 'Success' or 'Failed' status.
    :param ssm_client: boto3 client
    :param ec2_instance_id: aws id for ec2_instance
    :param command_id: ssm command_id
    :param max_wait_time: max_wait_time in seconds
    :return: status either 'Success', 'Failed', or value when time expired.
    """
    wait_time_in_sec = 0
    status = ''
    while wait_time_in_sec < max_wait_time:
        time.sleep(1)
        wait_time_in_sec += 1
        # Get the output from the command invocation
        invocation_response = ssm_client.get_command_invocation(
            CommandId=command_id,
            InstanceId=ec2_instance_id
        )
        status = invocation_response['Status']
        print('SSM: invocation ({}) status: {}'.format(wait_time_in_sec, status))
        if 'Success' == status:
            print("SUCCESS. Took {} sec."
                  .format(wait_time_in_sec))
            return status
        if 'Failed' == status:
            print('FAILED after {} sec.'.format(wait_time_in_sec))
            return status

    # We reached the timeout.
    print('TIMEOUT: status={} after {}'.format(status, wait_time_in_sec))
    return status


def verify_link_to_svg_file(dest_file_location):
    """
    Verify the S3 file is there, and set the permissions
    to this object properly. If found return a link to it.
    If not found return None.
    :param dest_file_location:
    :return: S3 link if found or None if missing.
    """
    # Is the object there?
    print('Looking for S3 object: {}'.format(dest_file_location))
    parts = dest_file_location.split('/', 1)
    bucket = parts[0]
    key = parts[1]
    print('bucket: {}, key: {}'.format(bucket, key))

    try:
        s3_resource = boto3.resource('s3')
        s3_resource.Object(bucket, key).load()

        return 'https://s3-us-west-2.amazonaws.com/{}/{}'.format(bucket, key)

    except botocore.exceptions.ClientError as e:
        http_code = e.response['Error']['Code']
        if http_code == '403':
            # Object is there, but owner didn't give permission to it.
            return 'https://s3-us-west-2.amazonaws.com/{}/{}'.format(bucket, key)
        elif http_code == '404':
            # Just don't see the file.
            return None
        else:
            print('Failed to find: {} in bucket: {}. http-code: {}'
                  .format(key, bucket, http_code))
            raise ShowSlackError("Unexpected S3 bucket error. Check logs.")


def validate_run_time_value(run_time_in_sec):
    """
    If the value is None, or not valid number set it to the
    default value of 20 seconds.

    For valid numbers enforce a
    min of 15 seconds
    and a max of 60 seconds

    :param run_time_in_sec:
    :return: integer between 10 and 60 seconds.
    """
    DEFAULT_RUN_TIME = 20
    MIN_TIME_IN_SEC = 15
    MAX_TIME_IN_SEC = 60

    try:
        if isinstance(run_time_in_sec, (int, long, float)):
            if run_time_in_sec < MIN_TIME_IN_SEC:
                return MIN_TIME_IN_SEC
            elif run_time_in_sec > MAX_TIME_IN_SEC:
                return MAX_TIME_IN_SEC
            else:
                return int(run_time_in_sec)
        else:
            # Is this a string that can be a number?
            int_value = int(run_time_in_sec)
            return validate_run_time_value(int_value)
    except Exception:
        print('Setting {} to default {} sec.'.format(run_time_in_sec, DEFAULT_RUN_TIME))
        return DEFAULT_RUN_TIME
