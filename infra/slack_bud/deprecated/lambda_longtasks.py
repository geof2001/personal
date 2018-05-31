"""Entry point for longer running lambda tasks for the lambda function, called from slack-bud."""
from collections import OrderedDict
import json
import logging
import re
import gitlab
import requests
from deprecated.cmds_service import CmdService
from deprecated.cmds_flamegraph import CmdFlamegraph
from deprecated.cmds_test import CmdTest
# {cmdimportline}
import util.aws_util as aws_util
import util.slack_ui_util as slack_ui_util

# Constant Params
GITLAB_URL = 'https://gitlab.eng.roku.com/'
JIRA_URL = 'https://jira.portal.roku.com:8443/'
GIT_TOKEN = 'B8cREFMrfFKF7MKWi8jP'
MAX_COMMITS = 200
ES_HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
REGEX_FOR_JIRA = re.compile(r'(\[\w+\-\d{2,5}\]|\w+\-\d{2,5})')
ENVIRONMENTS = aws_util.ENVIRONMENTS


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def get_commit_difference_data(build1,build2,commit1, commit2,repo_name, jira=False):
    gl = gitlab.Gitlab(GITLAB_URL, GIT_TOKEN, api_version=3)
    logging.info(gl)
    project = gl.projects.list(search=repo_name)[0]
    logging.info(project)
    commits = [str(x.id) for x in project.commits.list(page=0, per_page=MAX_COMMITS,ref_name='master')]
    logging.info('Commits :{}'.format(commits))
    current_commit = commit1
    last_commit = commit2
    logging.info('Current Commit {}'.format(current_commit))
    logging.info('Last commit: {}'.format(last_commit))
    logging.info(current_commit)
    logging.info(last_commit)
    logging.info(' ' in current_commit)
    logging.info(' ' in last_commit)
    try:
        start_point, end_point = 0, 0
        start_point = commits.index(commit1)
        end_point = commits.index(commit2)
        if start_point > end_point:
            start_point,end_point = end_point,start_point
        commits_in_between = commits[start_point:end_point]
    except ValueError:
        data = {
            "response_type": "in_channel",
            "text": "One of the commit is not find in gitlab, Please check commit is present in gitlab"
        }
        return data
    if commits_in_between == []:
        data = {
            "response_type": "in_channel",
            "text": "There is no commits in between builds.",
        }
        return data
    commit_info = []
    #commit_info =  OrderedDict()
    jira_info =  OrderedDict()
    for commit in commits_in_between:
        commit_title = project.commits.get(commit).title
        short_id = project.commits.get(commit).short_id
        author = str(project.commits.get(commit).author_email).split('@')[0]
        jira_task = re.search(REGEX_FOR_JIRA, commit_title)
        logging.info('JIRA task: {}'.format(jira_task))
        # if jira_task:
        #     if "SR" in jira_task.group(1):
        #         #url_for_jira_task = jira_url + 'browse/' + jira_task.group(1)
        #         task_id = jira_task.group(1)
        #         commit_title = (commit_title.replace(task_id,"")).strip()
        #         if '[' or ']' in task_id:
        #             task_id = ''.join(char for char in task_id if char not in '()[]')
        #         url_for_jira_task = JIRA_URL + 'browse/' + task_id
        #         commit_id = "`{}`,`{}`".format(short_id, author)
        #         if len(commit_title) <= 45:
        #             jira_info[commit_id] = commit_title
        #         else:
        #             jira_info[commit_id] = commit_title[:45]+".."
        #
        #     else:
        #         pass
        # url_for_difference = GITLAB_URL + "SR/" + repo_name + "/commit/" + commit
        # commit_id = "`{}`,`{}`".format(short_id, author)
        commit_message = "`{}`,`{}`,`{}`".format(short_id, author, commit_title)
        if len(commit_message) <= 75:
            pass
        else:
            commit_message = commit_message[:75]+".."+'`'
        commit_info.append(commit_message)
        # if len(commit_title) <= 45:
        #     commit_info[commit_id] = commit_title
        # else:
        #     commit_info[commit_id] = commit_title[:45]+".."
    logging.info("Commit Information: {}".format(commit_info))
    logging.info("Jira Information: {}".format(jira_info))
    attachments = []
    dash = '-'*50
    if not jira:
        for commit_msg in commit_info:
            info = ''
            information = {}
            info += "{}".format(commit_msg.encode('ascii', 'ignore'))
            #info += dash
            information["text"] = info
            information["mrkdwn_in"] = ["text"]
            information["color"] = "#bd9ae8"
            attachments.append(information)
        slack_data = {
            "response_type": "in_channel",
            "text": "*Git difference between builds*: `{}` and `{}`\n*Total commits in between*: {}\n".format(build1, build2, len(attachments)),
            "attachments": attachments
        }
        return slack_data
    else:
        if jira_info != {}:
            for k, v in jira_info.items():
                info = ''
                information = {}
                info += "*JIRA Title*: {}, \n*Jira Task*: `{}`\n".format(k.encode('ascii', 'ignore'), v)
                #info += dash
                information["text"] = info
                information["mrkdwn_in"] = ["text"]
                information["color"] = "#bd9ae8"
                attachments.append(information)
            slack_data = {
                "response_type": "in_channel",
                "text": "*JIRA tasks between builds*: `{}` and `{}`\n*Total JIRA tasks in between*: {}\n     {}".format(build1, build2, len(attachments), dash),
                "attachments": attachments
            }
            return slack_data
        else:
            slack_data = {
                "response_type": "in_channel",
                "text": "*Jira task not found between builds*: `{}` and `{}`".format(build1, build2),
            }
            return slack_data


def handle_build_diff(event):
    """
    This code is here temporarily, since it is a long running task.
    It will need to move back to the
    :param event:
    :return:
    """
    logging.info('EVENT GIT DIFF: {}'.format(event))
    build1 = event.get('build1')
    build2 = event.get('build2')
    callback_url = event.get('url')
    jira = event.get('jira')
    logging.info("JIRA: {}".format(jira))
    try:
        logging.info("Build1: {}".format(build1))
        logging.info("Build2: {}".format(build2))
        logging.info("Callback url is {}".format(callback_url))
        es_client = aws_util.setup_es()
        def get_query(build):
            query = {
                "query":{
                        "query_string":{
                            "query" : "dockertag.keyword:{}".format(build)
                            }
                        }
            }
            return query

        build1_info = es_client.search(index='build*', body=get_query(build1))
        build2_info = es_client.search(index='build*', body=get_query(build2))

        repo_for_build1 = build1_info.get('hits').get('hits')[0].get('_source').get('gitrepo')
        repo_for_build2 = build2_info.get('hits').get('hits')[0].get('_source').get('gitrepo')

        commit_for_build1 = build1_info.get('hits').get('hits')[0].get('_source').get('gitcommit')
        commit_for_build2 = build2_info.get('hits').get('hits')[0].get('_source').get('gitcommit')

        if repo_for_build1 != repo_for_build2:
            header = {"Content-type": "application/json"}
            body = {
                "response_type": "ephemeral",
                "text": "*Can not get git difference or jira task between builds,"
                        "build: `{}` is from repository: `{}` and build: `{}` is "
                        "from repository `{}`,"
                        " repositories *".format(build1, repo_for_build1, build2, repo_for_build2)
            }
            r = requests.post(callback_url, data=json.dumps(body), headers=header)
        if jira:
            slack_data = get_commit_difference_data(build1,build2,commit_for_build1, commit_for_build2,repo_for_build1, jira=True)
            header = {"Content-type": "application/json"}
            body = slack_data
            r = requests.post(callback_url, data=json.dumps(slack_data), headers=header)
            logging.info("Posted on this URL: {}".format(callback_url))
            logging.info("Posted this DATA {}".format(slack_data))
            logging.info("Response Code for POST : {}".format(r.status_code))
            logging.info("Reason: {}".format(r.reason))
        else:
            slack_data = get_commit_difference_data(build1,build2,commit_for_build1, commit_for_build2,repo_for_build1)
            header = {"Content-type": "application/json"}
            body = slack_data
            r = requests.post(callback_url, data=json.dumps(slack_data), headers=header)
            logging.info("Posted on this URL: %s" % callback_url)
            logging.info("Posted this DATA {}".format(slack_data))
            logging.info("Response Code for POST : {}".format(r.status_code))
            logging.info("Reason: {}".format(r.reason))
    except ValueError:
        header = {"Content-type": "application/json"}
        body = {
            "response_type": "in_channel",
            "text": "*Arrrghhhh !!! Something going wrong!!*"
        }
        r = requests.post(callback_url, data=json.dumps(body), headers=header)


# Gets parameter index for deploy
def get_parameter_index(cf_image, lst_of_map):
    """
    Entry point when deploy status is called

    :param cf_image: - Image Parameter Name
    :param lst_of_map: - List of the parameters map
    """
    for index, dic in enumerate(lst_of_map):
        LOGGER.info('LIST OF MAPS PARAM:' % lst_of_map)
        LOGGER.info('for loop index %s dic %s value %s' % (index, dic, dic['ParameterKey']))
        if dic['ParameterKey'] == cf_image:
            return index
    return -1


# Status of current deployed versions
def handle_deploy_status(event):
    """
    Entry point when deploy status is called

    :param event: - The payload passed into the function
    """
    service = event.get('service')
    stack_name = event.get('stack_name')
    region_map = event.get('region_map')
    response_url = event.get('response_url')
    cf_image = event.get('cf_image')
    output = ''

    # Order map to enhance env readability
    order = ['dev', 'qa', 'prod']
    ordered_map = OrderedDict()
    for env in order:
        if env in region_map:
            ordered_map[env] = region_map[env]

    LOGGER.info('ORDERED_MAP: %s' % ordered_map)
    ordered_dict = OrderedDict()

    # Loop through map
    for env in ordered_map:
        ordered_dict[env] = OrderedDict()
        for region in ordered_map[env]:
            LOGGER.info('ENV/REGION: %s/%s' % (env, region))
            session = aws_util.create_session(env)
            try:
                cf = aws_util.get_cloudformation_client(session, region)
                stack_description = cf.describe_stacks(StackName=stack_name)
                LOGGER.info('STACK DESCRIPTION : %s ' % stack_description)
                index = get_parameter_index(cf_image, stack_description['Stacks'][0]['Parameters'])
                LOGGER.info('index : %s ' % index)
                full_version = stack_description['Stacks'][0]['Parameters'][index]['ParameterValue']
                current_version = full_version.split(':')[1] if ':' in full_version else full_version
                ordered_dict[env][region] = current_version
            except:
                error_text = "The service *[%s]* may not have a CF stack with the version as a " \
                             "parameter, or does not exist in *[serviceInfo]*..." % service
                return slack_ui_util.error_response(error_text, post=True, response_url=response_url)

    LOGGER.info('Ordered dict : %s' % ordered_dict)

    # Setup ES client
    es_client = aws_util.setup_es()

    # Loops through dict and fathers the image info from ES and prints
    for env in ordered_dict:
        output += '```[%s]```\n' % env
        max_num_env = 0

        # Determines max build number
        for region in ordered_dict[env]:
            if '-' not in ordered_dict[env][region]:
                continue
            build_num = int(ordered_dict[env][region].rsplit('-',1)[1])
            if build_num > max_num_env:
                max_num_env = build_num

        for region in ordered_dict[env]:
            current_version = ordered_dict[env][region]

            # If parameter value is None or some non traditional value
            if '-' not in current_version:
                output += '_%s_: `%s` - `?` `?`\n' % (region, current_version)
                continue

            query_version = service + '\:' + current_version
            build_num = int(current_version.rsplit('-',1)[1])
            LOGGER.info('build num for %s  %s : %s' % (env, region, build_num))
            LOGGER.info('max env num for %s  %s : %s' % (env, region, max_num_env))

            # ES query
            query = {
                "query": {
                    "query_string": {
                        "query": "changeset.keyword:(false OR true) AND "
                                 "region.keyword:%s AND "
                                 "image_name.keyword:%s "
                                 "AND environment:%s"
                                 % (region, query_version, ENVIRONMENTS[env])
                    }
                }
            }

            # Search using the specified query and sort by most recent deploy job number
            search = es_client.search(index='deploy*',
                                      body=query,
                                      _source_include=['deploy_time',
                                                       'deploy_job_number',
                                                       'image_name',
                                                       'service',
                                                       'userID'],
                                      sort=['deploy_job_number.keyword:desc'],
                                      size=4
                                      )
            user_id = search['hits']['hits'][0]['_source']['userID'] \
                if search['hits']['hits'] else '?'
            deploy_time = search['hits']['hits'][0]['_source']['deploy_time'] \
                if search['hits']['hits'] else '?'

            # Check if an environment in the same region has a out of date version
            if build_num < max_num_env:
                output += '_%s_: `%s*` - `%s` `%s`\n' \
                          % (region, current_version, deploy_time, user_id)
            else:
                output += '_%s_: `%s` - `%s` `%s`\n' \
                          % (region, current_version, deploy_time, user_id)

    output += '\n\n\n`*` - _Signifies that the version may potentially be out of ' \
              'date compared to those of other regions in the same environment_'

    return slack_ui_util.text_command_response(
        title='Here are the current versions of `%s` deployed for service `%s`:' % (cf_image, service),
        text=output,
        color="#d77aff",
        post=True,
        response_url=response_url
    )


def lambda_handler(event, context):
    print 'EVENT LONGTASKS: {}'.format(event)
    task = event.get('task')
    print('TASK :{}'.format(task))
    if task == 'builddiff':
        return handle_build_diff(event)
    elif task == 'deploy_status':
        return handle_deploy_status(event)
    elif task == 'CmdService':
        return CmdService().invoke_longtask_command(event)
    elif task == 'CmdFlamegraph':
        return CmdFlamegraph().invoke_longtask_command(event)
    elif task == 'CmdTest':
        return CmdTest().invoke_longtask_command(event)
# {cmdlongtaskswitchline}
    else:
        print("WARNING: Unrecognized task value: {}".format(task))
        response_url = event.get('response_url')
        error_text = "Unrecognized long task value. Check error logs".format(task)
        return slack_ui_util.error_response(error_text, post=True, response_url=response_url)
