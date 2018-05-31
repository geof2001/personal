"""Methods for build_info DNS commands."""
from __future__ import print_function

import datetime
import logging
import boto3
from elasticsearch import Elasticsearch, \
    RequestsHttpConnection, TransportError
from requests_aws_sign import AWSV4Sign
import slack_ui_util


# Please put your elastic host here
# ES_HOST = \
#     "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
ES_HOST = \
    "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"


class ES:
    """ElasticSearch methods"""
    def __init__(self, host):
        session = boto3.session.Session()
        credentials = session.get_credentials()
        region = session.region_name
        service = 'es'
        auth = AWSV4Sign(credentials, region, service)
        self.logger = logging.getLogger()
        try:
            self.es_client = Elasticsearch(
                host=host, port=443,
                connection_class=RequestsHttpConnection,
                http_auth=auth, use_ssl=True, verify_ssl=True
            )
        except TransportError as e:
            raise ValueError(
                "Problem in {} connection, Error is {}".format(host, e.message)
            )

    def get_data_commit(self, id):
        date_now = (datetime.datetime.now()).strftime('%Y-%m')
        current_index = "build_" + date_now
        data = self.es_client.get(index=current_index, doc_type='_all', id=id)
        git_commit = data.get("_source").get("gitcommit", None)
        return git_commit

    def get_data_repo(self, id):
        date_now = (datetime.datetime.now()).strftime('%Y-%m')
        current_index = "build_" + date_now
        data = self.es_client.get(index=current_index, doc_type='_all', id=id)
        repo = data.get("_source").get("gitrepo", None)
        return repo

    def get_data(self, id):
        try:
            date_now = (datetime.datetime.now()).strftime('%Y-%m')
            current_index = "build_" + date_now
            data = self.es_client.get(index=current_index, id=id, doc_type='_all')
            print(data.get("coverage"))
            repo = data.get("_source").get("repositories", None)
            author = data.get("_source").get("gitauthor", None)
            service = data.get("_source").get("service", None)
            git_commit = data.get("_source").get("gitcommit", None)
            build_time = data.get("_source").get("buildtime", None)
            git_repo = data.get("_source").get("gitrepo", None)
            passed = data.get("_source").get("coverage")\
                .get("unittestcases").get("passed")
            failed = data.get("_source").get("coverage")\
                .get("unittestcases").get("failed")
            skipped = data.get("_source").get("coverage")\
                .get("unittestcases").get("skipped")
            line = int(data.get("_source").get("coverage")
                       .get("coverage").get("line"))
            class_cov = int(data.get("_source").get("coverage")
                            .get("coverage").get("class"))
            branch = int(data.get("_source").get("coverage")
                         .get("coverage").get("branch"))
            instruction = int(data.get("_source").get("coverage")
                              .get("coverage").get("instruction"))
            slack_data = {
                "response_type": "ephemeral",
                "text": "*Build information of build* : `{}`".format(id),
                "attachments": [
                    {
                        "text": "*Repository*: `{}`".format(repo),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Author*: `{}`".format(author),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Service*: `{}`".format(service),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*GIT Commit*: `{}`".format(git_commit),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Build time*: `{}`".format(build_time),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*GIT Repo*: `{}`".format(git_repo),
                        "mrkdwn_in": ["text"], "color":"#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Passed*: `{}`".format(passed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Unittest Case Failed*: `{}`".format(failed),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Unittest Case Skipped*: `{}`".format(skipped),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text": "*Line Code Coverage*: *`{}%`*".format(line),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Class Code Coverage*: *`{}%`*".format(class_cov),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Branch Code Coverage*: *`{}%`*".format(branch),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    },
                    {
                        "text":
                            "*Instruction Code Coverage*:"
                            " *`{}%`*".format(instruction),
                        "mrkdwn_in": ["text"], "color": "#a0ffaa"
                    }
                ]
            }
            return slack_ui_util.respond(None, slack_data)

        except TransportError as e:
            return slack_ui_util.respond(e)
            # raise ValueError(
            #     "Can not get data with id: {} on index: {}, error is {}"
            #         .format(id, current_index, e)
            # )


def handle_build_info(id):
    es = ES(ES_HOST)
    return es.get_data(id)


def get_commit(es, id):
    return es.get_data_commit(id)


def get_repo(es, id):
    return es.get_data_repo(id)
