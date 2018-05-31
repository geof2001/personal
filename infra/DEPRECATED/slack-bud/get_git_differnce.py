"""Is entry point for git-difference lambda function, called from slack-bud."""
import json
import logging
import re
import gitlab
import requests
import cmd.build_info as build_info
from cmd.build_info import ES

# Constant Params 
GITLAB_URL = 'https://gitlab.eng.roku.com/'
JIRA_URL = 'https://jira.portal.roku.com:8443/'
GIT_TOKEN = 'B8cREFMrfFKF7MKWi8jP'
MAX_COMMITS = 200
ES_HOST = "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
REGEX_FOR_JIRA = re.compile(r'(\[\w+\-\d{2,5}\]|\w+\-\d{2,5})')


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def get_commit_difference_data(build1, build2, es, repo_name, jira=False):
    gl = gitlab.Gitlab(GITLAB_URL, GIT_TOKEN)
    project = gl.projects.list(search=repo_name)[0]
    commits = [str(x.id) for x in project.commits.list(page=0, per_page=MAX_COMMITS)]
    current_commit = build_info.get_commit(es, build1)
    last_commit = build_info.get_commit(es, build2)

    logging.info('Current Commit {}'.format(current_commit))
    logging.info('Last commit: {}'.format(last_commit))
    start_point, end_point = 0, 0

    for no, commit in enumerate(commits):
        if commit == current_commit:
            start_point = no
        if commit == last_commit:
            end_point = no
            break
    commits_in_between = commits[start_point:end_point]
    if commits_in_between == []:
        data = {
            "response_type": "in_channel",
            "text": "Please check build order, it should be in <new> <old> order, try after changing order",
        }
        return data
    commit_info = {}
    jira_info = {}
    for commit in commits_in_between:
        commit_title = project.commits.get(commit).title
        jira_task = re.search(REGEX_FOR_JIRA, commit_title)
        logging.info('JIRA task: {}'.format(jira_task))
        if jira_task:
            if "SR" in jira_task.group(1):
                #url_for_jira_task = jira_url + 'browse/' + jira_task.group(1)
                task_id = jira_task.group(1)
                if '[' or ']' in task_id:
                    task_id = ''.join(char for char in task_id if char not in '()[]')
                url_for_jira_task = JIRA_URL + 'browse/' + task_id
                jira_info[commit_title] = url_for_jira_task
            else:
                pass
        url_for_difference = GITLAB_URL + "SR/" + repo_name + "/commit/" + commit
        commit_info[commit_title] = url_for_difference

    logging.info("Commit Information: {}".format(commit_info))
    logging.info("Jira Information: {}".format(jira_info))
    attachments = []
    dash = '-'*100
    if not jira:
        for k, v in commit_info.items():
            info = ''
            information = {}
            info += "\n*Change Title*: `{}`, \n*Full Change List*: {}\n".format(k.encode('ascii', 'ignore'), v)
            info += dash
            information["text"] = info
            information["mrkdwn_in"] = ["text"]
            information["color"] = "#bd9ae8"
            attachments.append(information)
        slack_data = {
            "response_type": "in_channel",
            "text": "*Git difference between builds*: `{}` and `{}`\n*Total commits in between*: {}\n     {}".format(build1, build2, len(attachments), dash),
            "attachments": attachments
        }
        return slack_data
    else:
        if jira_info != {}:
            for k, v in jira_info.items():
                info = ''
                information = {}
                info += "*JIRA Title*: `{}`, \n*Jira Task*: {}\n".format(k.encode('ascii', 'ignore'), v)
                info += dash
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


def lambda_handler(event, context):
    build1 = event.get('build1')
    build2 = event.get('build2')
    callback_url = event.get('url')
    jira = event.get('jira')
    logging.info("JIRA: {}".format(jira))

    try:
        logging.info("Build1: {}".format(build1))
        logging.info("Build2: {}".format(build2))
        logging.info("Callback url is {}".format(callback_url))
        es = ES(ES_HOST)
        repo_for_build1 = build_info.get_repo(es, build1)
        repo_for_build2 = build_info.get_repo(es, build2)
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
            slack_data = get_commit_difference_data(build1, build2, es, repo_for_build1, jira=True)
            header = {"Content-type": "application/json"}
            body = slack_data
            r = requests.post(callback_url, data=json.dumps(slack_data), headers=header)
            logging.info("Posted on this URL: {}".format(callback_url))
            logging.info("Posted this DATA {}".format(slack_data))
            logging.info("Response Code for POST : {}".format(r.status_code))
            logging.info("Reason: {}".format(r.reason))
        else:
            slack_data = get_commit_difference_data(build1, build2, es, repo_for_build1)
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