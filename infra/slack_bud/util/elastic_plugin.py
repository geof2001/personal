import boto3
import sys
from requests_aws_sign import AWSV4Sign
#from elasticsearch_dsl import Search
from elasticsearch import Elasticsearch, RequestsHttpConnection, TransportError




HOST = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
REGION = "us-west-2"


"""
Elastic search plugin exceptions.
"""
class ItemNotFoundException(IndexError):
    """
    if result has not no value, return this exception.
    """
    def __init__(self, *args, **kwargs):
        super(ItemNotFoundException, self).__init__(*args, **kwargs)


class ElasticConnectionError(TransportError):
    """
    Define elastic search database connection error exception
    """
    def __init__(self, *args, **kwargs):
        super(ElasticConnectionError, self).__init__(*args, **kwargs)

class MissingParams(ValueError):
    """
    any api params which is missing.
    """
    def __init__(self, *args, **kwargs):
        super(MissingParams, self).__init__(*args, **kwargs)


class ElasticQuery:

    def __init__(self):
        """
        Setup elastic search connection with recorder host.
        """
        session = boto3.session.Session()
        credentials = session.get_credentials()
        region = REGION
        service = "es"
        auth = AWSV4Sign(credentials, region, service)
        self.accounts = {
            "dev": "638782101961",
            "qa": "181133766305",
            "prod": "886239521314"
        }
        try:
            self.es_client = Elasticsearch(host=HOST, port=443, connection_class=RequestsHttpConnection,
                                  http_auth=auth, use_ssl=True, verify_ssl=True)
            #self.query = Search(using=self.es_client)
        except ElasticConnectionError:
            print("Can not connect ES Host: {} , Exit".format(HOST))
            sys.exit(1)

    def _get_testinfo_by_image(self, image_name, env):
        """
        private api for getting test information by image
        :param image_name: name of image
        :return: test data
        """
        if not (image_name or env):
            raise MissingParams
        query = {
            "query": {
                "query_string": {
                    "query": "\"{}\" AND testenv:\"{}\"".format(image_name,env)
                }
            }
        }
        search = self.es_client.search(index='test*', body=query, sort=['testtime:desc'], size=1)
        try:
            return search.get('hits').get('hits')[0]
        except ItemNotFoundException:
            return None

    def get_build_history(self, service=None, branch=None, size=1):
        """
        api for getting build history information.
        :param service: name of service (e.g homescreen, search etc)
        :param branch: on which branch main or custom branch)
        :param size:   no of build
        :return: list of builds.
        """
        if not service:
            raise MissingParams
        if branch:
            branch_search = " AND gitbranch.keyword:\"{}\"".format(branch)
        else:
            branch_search = ""
        query = {
            "query": {
                "query_string": {
                    "query": "service.keyword:\"{}\"".format(service + branch_search)
                }
            }
        }
        search = self.es_client.search(index='build*', body=query, sort=['buildtime:desc'], size=size)
        return search.get('hits').get('hits')

    def get_build_info(self, build_name=None):
        """
        api for getting build info.
        :param build_name: name of the build.
        :return: list
        """
        if not build_name:
            raise MissingParams
        query = {
            "query": {
                "query_string": {
                    "query": "dockertag.keyword:\"{}\"".format(build_name)
                }
            }
        }
        search = self.es_client.search(index='build*', body=query, sort=['buildtime:desc'], size=1)
        return search.get('hits').get('hits')

    def get_deploy_history(self, region=None, env=None, service=None, changeset="false", size=1):
        """
        api for getting build deploy history.
        :param region: region (us-east-1,us-west-2)
        :param env: on which environment (qa,dev,prod).
        :param service: service name (homescreen, bifservice)
        :param size: no of deployment.
        :return: list
        """
        if not (region or env or service):
            raise MissingParams
        environment = self.accounts.get(env)
        env_str = " AND environment:\"{}\"".format(environment)
        region_str = " AND region:\"{}\"".format(region)
        changeset_str = " AND changeset:\"{}\"".format(changeset)
        cf_status = " AND cf_status:\"UPDATE_COMPLETE\""
        es_query_str = '{} {} {} {}'.format(service,env_str,region_str,cf_status)
        query = {
            "query": {
                "query_string": {
                    "query": 'service.keyword:{}'.format(es_query_str)
                }
            }
        }
        search = self.es_client.search(index='deploy*', body=query, sort=['deploy_time:desc'], size=size)
        return search.get('hits').get('hits')

    def get_latest_build(self,service=None, branch=None):
        """
        api for getting the latest build triggered by jenkins.
        :param service: Name of service
        :param branch: Name of branch(e.g main)
        :return: list
        """
        result = self.get_build_history(service=service,branch=branch,size=1)
        try:
            return result[0]
        except ItemNotFoundException:
            return None

    def get_latest_deployed_build(self,region=None, env=None, service=None):
        """
        api for getting info for the latest deployed build
        :param region: Name of region
        :param env: Name of environment.
        :param service: Name of service.
        :return:
        """
        if not (region or env or service):
            raise MissingParams
        result = self.get_deploy_history(region=region,env=env,service=service,size=1)
        try:
            return result[0]
        except ItemNotFoundException:
            return None

    def get_last_deploy_git_checkin(self,region=None, env=None, service=None):
        """
        api for getting latest git checkin.
        :param region: Name of region
        :param env: Name of environment.
        :param service: Name of service.
        :return:str git checkin.
        """
        if not (region or env or service):
            raise MissingParams
        result = self.get_latest_deployed_build(region=region, env=env, service=service)
        try:
            image_name = result.get('_source').get('dockertag')
            build_info = self.get_build_info(build_name=image_name)
            git_commit = build_info[0].get('_source').get('gitcommit')
            return git_commit
        except ItemNotFoundException:
            return None

    def get_test_history(self, service=None, env=None, size=1):
        """
        api for getting test history.
        :param service: Name of service
        :param env: Name of environment.
        :param size: No of results.
        :return: list
        """
        if not (env or service):
            raise MissingParams
        env_str = "AND testenv:\"{}\"".format(env)
        service_str = "service:\"{}\"".format(service)
        es_query_str = '{} {}'.format(service_str, env_str)
        query = {
            "query": {
                "query_string": {
                    "query": '{}'.format(es_query_str)
                }
            }
        }
        search = self.es_client.search(index='test*', body=query, sort=['testtime:desc'], size=size)
        return search.get('hits').get('hits')

    def get_latest_test_status(self, service=None, env=None):
        """
        api for getting latest test result.
        :param service: Name of service
        :param env: Name of environment (dev/qa/prod)
        :return: list
        """
        if not (env or service):
            raise MissingParams
        result = self.get_test_history(service=service,env=env, size=1)
        try:
            return result[0]
        except ItemNotFoundException:
            return None

    def get_last_test_failed(self, service=None, env=None):
        """
        api for last failed.
        :param service: Name of service
        :param env: Name of environment (dev/qa/prod)
        :return: list
        """
        if not (env or service):
            raise MissingParams
        env_str = "AND testenv:\"{}\"".format(env)
        service_str = "service:\"{}\"".format(service)
        es_query_str = '{} {} AND testfailed:[1 TO *]'.format(service_str, env_str)
        query = {
            "query": {
                "query_string": {
                    "query": '{}'.format(es_query_str)
                }
            }
        }
        search = self.es_client.search(index='test*', body=query, sort=['testtime:desc'], size=1)
        try:
            result = search.get('hits').get('hits')[0]
            return result
        except ItemNotFoundException:
            return None

    def get_deployed_build_test_status(self, region=None, env=None, service=None):
        """
        api for get deployed build test status.
        :param region: Name of region
        :param env: Name of environment.
        :param service: Name of service.
        :return: str
        """
        build = self.get_latest_deployed_build(region=region,env=env, service=service)
        if build is not None:
            build_data = build.get('_source')
            image_name = build_data.get('image_name')
            test_result = self._get_testinfo_by_image(image_name, env)
            if test_result:
                test_result = test_result.get('_source')
                passed_tc = test_result.get('testpassed')
                failed_tc = test_result.get('testfailed')
                skipped_tc = test_result.get('testskipped')
                test_time = test_result.get('testtime')
                percentage_pass = (float(passed_tc) / float(passed_tc) + float(failed_tc)) * 100
                return str(passed_tc)+'/'+str(failed_tc)
            else:
                return "NA/NA"
        return "NA/NA"

    def get_build_deploy_info(self):
        pass

    def get_build_test_info(self):
        pass
