#!/usr/bin/python
import sys
import boto3
import datetime
import logging
import requests
import json
import random
from requests_aws_sign import AWSV4Sign
from elasticsearch import Elasticsearch, RequestsHttpConnection, TransportError

session = boto3.session.Session()
credentials = session.get_credentials().get_frozen_credentials()

param_file = sys.argv[2]
config_file = "config.ini"

class BuildInfoBuilder:
    def __init__ (self, filename=param_file):
        # config = ConfigParser.ConfigParser()
        # config.read(config_file)
        # self.es = "search-sr-common-es-zv6yqj5gsktuwh62zfbcoyglxe.us-west-2.es.amazonaws.com"

        # Put Elastic search FQDN here
        # self.es = "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
        self.es = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
        # Put Jenkins FQDN here
        self.url = "https://cidsr.eng.roku.com"
        self.data_container = dict()
        self.field = 1
        self.logger = logging.getLogger()
        try:
            with open(filename, 'r') as f:
                for lines in f.readlines():
                    lines = lines.rstrip('\n')
                    key, value = lines.split("=")
                    if key in self.data_container.keys():
                        self.data_container[key + "{}".format(self.field)] = value
                        self.field += 1
                    else:
                        self.data_container[key] = value
        except IOError:
            self.logger.error("File {} is not accessible".format(filename))
            raise ValueError("File {} is not accessible".format(filename))

    def get_build (self):
        try:
            build_number = self.data_container['BUILD_NUMBER']
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_build_time (self):
        try:
            date = datetime.datetime.fromtimestamp(int((self.data_container['TIMESTAMP'])))
            return date
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_git_branch (self):
        try:
            git_branch = self.data_container['GIT_BRANCH']
            return git_branch
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_git_checkin (self):
        try:
            return self.data_container['GIT_COMMIT']
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_git_author (self):
        try:
            return self.data_container['GIT_AUTHOR']
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_git_repo (self):
        try:
            return self.data_container['GIT_REPO']
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_service_name (self):
        try:
            return self.data_container['SERVICE_NAME']
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_job_name (self):
        try:
            return self.data_container['JOBNAME']
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_container_info (self, copy_script_build=False):
        try:
            img = self.data_container['VERSION']
            if copy_script_build:
                return img
            img_info = img.split("/")
            if len(img_info) == 2:
                repo = img_info[0]
                image_name = img_info[1]
                return repo, image_name
            else:
                self.logger.error("Please check container-image format, might be changed?")
                raise ValueError("Please check container-image format, might be changed?")
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_code_change_info (self):
        code_change = []
        build_number = self.get_build()
        build_info_url = self.url + "/job/z_gcuni-test-buildimage/" + build_number + "/api/json"
        res = requests.get(build_info_url)
        content = json.loads(res.content)
        total_changes = content.get("changeSet").get("items")
        print(total_changes)
        code_change = [{
                           u'comment': u'[SRSEARCH-829] Partner TMS-ID Parser - added default channel store code\nof "us" to program and option builders\n',
                           u'authorEmail': u'htrinh@roku.com',
                           u'author': {u'absoluteUrl': u'https://cidsr.eng.roku.com/user/htrinh',
                                       u'fullName': u'Hieu Trinh'}, u'timestamp': 1497323447000,
                           u'id': u'68a18687c2b0f847603e64aaa01aa0d7830680c1',
                           u'commitId': u'68a18687c2b0f847603e64aaa01aa0d7830680c1',
                           u'msg': u'[SRSEARCH-829] Partner TMS-ID Parser - added default channel store code',
                           u'date': u'2017-06-12 20:10:47 -0700', u'paths': [{u'editType': u'edit',
                                                                              u'file': u'common/pojos/rokuprograms/src/main/java/com/roku/common/pojos/rokuprograms/Program.java'},
                                                                             {u'editType': u'edit',
                                                                              u'file': u'common/pojos/rokuprograms/src/main/java/com/roku/common/pojos/rokuprograms/model/ViewOption.java'}],
                           u'_class': u'hudson.plugins.git.GitChangeSet', u'affectedPaths': [
                u'common/pojos/rokuprograms/src/main/java/com/roku/common/pojos/rokuprograms/Program.java',
                u'common/pojos/rokuprograms/src/main/java/com/roku/common/pojos/rokuprograms/model/ViewOption.java']}]
        return code_change
        # code_change = json.loads(res.content)
        # print(code_change)

    def get_code_coverage_info (self):
        code_coverage = dict()
        test_result = dict()
        code_coverage_matrix = dict()
        build = self.get_build()
        url_for_code_coverage = self.url + "/job/" + str(sys.argv[1]) + "/" + build + "/jacoco/api/json"
        url_for_test_result = self.url + "/job/" + str(sys.argv[1]) + "/" + build + "/testReport/api/json"
        link_for_test_result = self.url + "/job/" + str(sys.argv[1]) + "/" + build + "/testReport"
        res = requests.get(url_for_code_coverage)
        coverage = json.loads(res.content)
        res = requests.get(url_for_test_result)
        result = json.loads(res.content)
        try:
            code_coverage_matrix['branch'] = coverage.get('branchCoverage').get('percentageFloat')
            code_coverage_matrix['line'] = coverage.get('lineCoverage').get('percentageFloat')
            code_coverage_matrix['instruction'] = coverage.get('instructionCoverage').get('percentageFloat')
            code_coverage_matrix['class'] = coverage.get('classCoverage').get('percentageFloat')
            test_result['failed'] = result.get('failCount')
            test_result['passed'] = result.get('passCount')
            test_result['skipped'] = result.get('skipCount')
            test_result['link'] = link_for_test_result
            code_coverage['coverage'] = code_coverage_matrix
            code_coverage['unittestcases'] = test_result
            return code_coverage
        except KeyError as e:
            raise AttributeError("Key \'{}\' missing in jenkins actions".format(e.message))

    def json_build (self):
        json_data = dict()
        json_data = {'image name': 'content-test:master-e5a4367a-20171023-95', 'service': 'content-test',
                     'gitauthor': 'N/A', 'buildtime': datetime.datetime(2017, 10, 23, 11, 0, 39),
                     'repositories': ['638782101961.dkr.ecr.us-east-1.amazonaws.com'],
                     'dockertag': 'master-e5a40f1-20171023-88', 'gitrepo': 'content-server',
                     'gitcommit': 'e5a40f156b668e47b1553ce76f8bece39d2d3862',
                     'coverage': {'unittestcases': {'failed': 0, 'skipped': 0, 'passed': 0},
                                  'coverage': {'line': 0, 'instruction': 0, 'class': 0,
                                               'branch': 0}}, 'gitbranch': 'master'}
        job_name = self.get_job_name()
        if job_name == 'docker-create-javaserver-image-v2':
            json_container_info = self.get_container_info()
            image_name = json_container_info[1]
            service_name = image_name.split(':')[0]
            build_id = image_name.split(':')[1]
            repo = list()
            repo.append(json_container_info[0])
            if len(repo) == 1:
                json_data["repository"] = repo
            else:
                json_data["repositories"] = repo
            json_data["image name"] = json_container_info[1]
            json_data["service"] = service_name
            json_data["gitbranch"] = self.get_git_branch()
            json_data["gitcommit"] = self.get_git_checkin()
            json_data["gitrepo"] = self.get_git_repo()
            json_data["gitauthor"] = self.get_git_author()
            json_data["buildtime"] = self.get_build_time()
            # json_data["codechange"] = self.get_code_change_info()
            json_data["dockertag"] = build_id
            json_data["coverage"] = dict()
            json_data["coverage"] = self.get_code_coverage_info()
            self.upload_json_to_es(json_data, self.es, image_name)
            print (json_data)
            return json_data
        elif job_name == 'docker-create-bifserver-image':
            json_container_info = self.get_container_info()
            image_name = json_container_info[1]
            service_name = image_name.split(':')[0]
            build_id = image_name.split(':')[1]
            repo = list()
            repo.append(json_container_info[0])
            if len(repo) == 1:
                json_data["repository"] = repo
            else:
                json_data["repositories"] = repo
            json_data["image name"] = json_container_info[1]
            json_data["service"] = service_name
            json_data["gitbranch"] = self.get_git_branch()
            json_data["gitcommit"] = self.get_git_checkin()
            json_data["gitrepo"] = self.get_git_repo()
            json_data["gitauthor"] = self.get_git_author()
            json_data["buildtime"] = self.get_build_time()
            # json_data["codechange"] = self.get_code_change_info()
            json_data["dockertag"] = build_id
            self.upload_json_to_es(json_data, self.es, image_name)
            print (json_data)
            return json_data
        elif job_name == 'docker-copy-scripts-to-s3':
            image_name = self.get_container_info(copy_script_build=True)
            json_data["image name"] = image_name
            json_data["service"] = self.get_service_name()
            json_data["dockertag"] = image_name
            json_data["gitbranch"] = self.get_git_branch()
            json_data["gitcommit"] = self.get_git_checkin()
            json_data["gitrepo"] = self.get_git_repo()
            json_data["gitauthor"] = self.get_git_author()
            json_data["buildtime"] = self.get_build_time()
            self.upload_json_to_es(json_data, self.es, image_name)
            print (json_data)
            return json_data
        elif job_name == 'docker-recsys-wikipedia-extractor':
            json_container_info = self.get_container_info()
            image_name = json_container_info[1]
            build_id = image_name.split(':')[1]
            repo = list()
            repo.append(json_container_info[0])
            if len(repo) == 1:
                json_data["repository"] = repo
            else:
                json_data["repositories"] = repo
            json_data["image name"] = image_name
            json_data["service"] = self.get_service_name()
            json_data["gitbranch"] = self.get_git_branch()
            json_data["buildtime"] = self.get_build_time()
            json_data["gitcommit"] = 'N/A'
            json_data["gitrepo"] = 'recsys'
            # json_data["codechange"] = self.get_code_change_info()
            json_data["dockertag"] = build_id
            self.upload_json_to_es(json_data, self.es, image_name)
            print (json_data)
            return json_data
        elif job_name == 'deploy-recsys-emr-jar-to-S3':
            image_name = self.get_container_info(copy_script_build=True)
            json_data["image name"] = image_name
            json_data["service"] = self.get_service_name()
            json_data["dockertag"] = image_name
            # json_data["gitbranch"] = self.get_git_branch()
            # json_data["gitcommit"] = self.get_git_checkin()
            # json_data["gitrepo"] = self.get_git_repo()
            # json_data["gitauthor"] = self.get_git_author()
            json_data["gitbranch"] = 'master'
            json_data["gitauthor"] = 'N/A'
            json_data["gitcommit"] = 'N/A'
            json_data["gitrepo"] = 'recsys'
            json_data["buildtime"] = self.get_build_time()
            self.upload_json_to_es(json_data, self.es, image_name)
            print (json_data)
            return json_data

    @staticmethod
    def upload_json_to_es (body, es, id):
        session = boto3.session.Session()
        credentials = session.get_credentials()
        # region = session.region_name
        region = "us-west-2"
        # print("Region: {}".format(region))
        service = 'es'
        auth = AWSV4Sign(credentials, region, service)
        try:
            es_client = Elasticsearch(host=es, port=443, connection_class=RequestsHttpConnection,
                                      http_auth=auth, use_ssl=True, verify_ssl=True)
            date_now = (datetime.datetime.now()).strftime('%Y-%m')
            current_index = "build_" + date_now
            if es_client.indices.exists(index=current_index):
                es_client.index(index=current_index, doc_type='json', id=id, body=body)
            else:
                es_client.create(index=current_index, doc_type='json', id=id, body=body)
        except TransportError as e:
            raise ValueError("Problem in {} connection, Error is {}".format(es, e.message))

    @staticmethod
    def upload_json_to_local_es (body, id):
        es_host = "localhost"
        es_client = Elasticsearch(host=es_host, http_auth=('elastic', 'changeme'))
        es_client.index(index='builds', doc_type='json', id=id, body=body)


class DeployInfoBuilder:
    def __init__ (self, filename=param_file):
        # self.es = "search-es-prototype-afakfdnohhsesghb7jbyk7i674.us-west-2.es.amazonaws.com"
        self.es = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
        self.url = "https://cidsr.eng.roku.com"
        self.data_container = dict()
        self.logger = logging.getLogger()
        try:
            with open(filename, "r") as f:
                for lines in f.readlines():
                    lines = lines.rstrip('\n')
                    key, value = lines.split("=")
                    self.data_container[key] = value
        except IOError:
            self.logger.error("File {} is not accessible".format(filename))
            raise ValueError("File {} is not accessible".format(filename))

    def get_build (self):
        try:
            build_number = self.data_container.get('BUILD_NUMBER', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_region (self):
        try:
            build_number = self.data_container.get('AWS_REGIONS', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_environment (self):
        try:
            build_number = self.data_container.get('AWS_ACCOUNTS', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_jobname (self):
        try:
            build_number = self.data_container.get('JOBNAME', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_changeset (self):
        try:
            build_number = self.data_container.get('CHANGE_SET', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_userID (self):
        try:
            build_number = self.data_container.get('User_name', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_cf_status (self):
        try:
            build_number = self.data_container.get('CF_STATUS', None)
            return build_number
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_time (self):
        try:
            date = datetime.datetime.fromtimestamp(int((self.data_container['TIMESTAMP'])))
            return date
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_container_info (self):
        try:
            img = self.data_container['IMAGE_VERSION']
            return img
        except KeyError as e:
            self.logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def json_build (self):
        json_data = dict()
        image_name = self.get_container_info()
        image_split = image_name.split(':')
        service_name = image_split[0]
        docker_tag = image_split[1]

        try:
            json_data["image_name"] = image_name
            json_data["service"] = service_name
            json_data["dockertag"] = docker_tag
            json_data["deploy_time"] = self.get_time()
            json_data["region"] = self.get_region()
            json_data["environment"] = self.get_environment()
            json_data["jobname"] = self.get_jobname()
            json_data["deploy_job_number"] = self.get_build()
            json_data["changeset"] = self.get_changeset()
            json_data["userID"] = self.get_userID()
            json_data["cf_status"] = self.get_cf_status()
            self.upload_json_to_es(json_data, self.es, image_name)

            print (json_data)
            return json_data
        except KeyError as e:
            raise AttributeError("Key \'{}\' missing in jenkins actions".format(e.message))

    @staticmethod
    def upload_json_to_es (body, es, id):
        session = boto3.session.Session()
        credentials = session.get_credentials()
        # region = session.region_name
        region = "us-west-2"
        # print("Region: {}".format(region))
        service = 'es'
        auth = AWSV4Sign(credentials, region, service)
        try:
            es_client = Elasticsearch(host=es, port=443, connection_class=RequestsHttpConnection,
                                      http_auth=auth, use_ssl=True, verify_ssl=True)
            date_now = (datetime.datetime.now()).strftime('%Y-%m')
            current_index = "deploy_" + date_now
            if es_client.indices.exists(index=current_index):
                es_client.index(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)), body=body)
                print "index existed"
            else:
                es_client.create(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)), body=body)
                print "new index"
        except TransportError as e:
            raise ValueError("Problem in {} connection, Error is {}".format(es, e.message))


class InfoBuilder:
    @staticmethod
    def json_build (filename):
        if filename == "prams.txt":
            J = BuildInfoBuilder()
            J.json_build()
        if filename == "deploy_params.txt":
            print "deploy_params"
            J = DeployInfoBuilder()
            J.json_build()


if __name__ == '__main__':
    InfoBuilder.json_build(param_file)