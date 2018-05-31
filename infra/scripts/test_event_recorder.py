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

# Global constant params
JENKINS_URL = "https://cidsr.eng.roku.com"
ES = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"


session = boto3.session.Session()
credentials = session.get_credentials().get_frozen_credentials()


# Set logging for test recording job
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


try:
    param_file = sys.argv[1]
except IndexError:
    logger.error("No test data file found.Please provide data file")
    logger.info("Test recording operation aborted.")
    sys.exit(1)


class TestInfoBuilder:
    """
    Build test data json object for elastic search.
    """
    def __init__(self, filename=param_file):
        """
        initiate test data builder with dashboard.txt or build_info.txt file.
        :param filename:
        """
        self.es = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
        self.url = "https://cidsr.eng.roku.com"
        self.data_container = dict()
        try:
            with open(filename, "r") as f:
                for lines in f.readlines():
                    lines = lines.rstrip('\n')
                    key, value = lines.split("=")
                    self.data_container[key] = value
        except IOError:
            logger.error("File {} is not accessible".format(filename))
            raise ValueError("File {} is not accessible".format(filename))

    def get_build(self):
        """
        mandatory params for logging data.if not then raise error.
        :return:
        """
        try:
            build_number = self.data_container.get('BUILD_NUMBER', None)
            return build_number
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_test_time(self):
        """
        mandatory params for logging data.if not then raise error.data in linux timestamp.
        :return:
        """
        try:
            date = datetime.datetime.utcfromtimestamp(int((self.data_container['TIMESTAMP'])))
            return date
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_container_info(self):
        """
        mandatory params,can be single service or multiple services.
        :return:
        """
        try:
            img = self.data_container['VERSION']
            return img
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_test_result_url(self):
        """
        mandatory params, get test result info.
        :return:
        """
        try:
            result_url = self.data_container['TEST_RESULT']
            return result_url
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))
    
    def get_test_report(self):
        """
        optional params
        """
        try:
            test_report = self.data_container.get('TEST_REPORT',None)
            return test_report
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            return None

    def get_test_cases_result(self):
        test_result = dict()
        link_for_test_result = self.get_test_result_url()
        res = requests.get(link_for_test_result + 'api/json')
        logger.info(res.content)
        result = json.loads(res.content)
        try:
            test_result['failed'] = result.get('failCount')
            test_result['passed'] = result.get('passCount')
            test_result['skipped'] = result.get('skipCount')
            test_result['link'] = link_for_test_result
            return test_result
        except KeyError as e:
            return None

    def get_endpoint(self):
        try:
            endpoint = self.data_container.get('ENDPOINT', None)
            return endpoint
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            raise AttributeError("Key {} is not found".format(e.message))

    def get_test_environment (self):
        try:
            test_env = self.data_container.get('TESTENV', None)
            if (test_env == None) or (test_env == "None"):
                endpoint = self.data_container.get('ENDPOINT', None)
                if endpoint != None:
                    if "qa" in endpoint:
                        test_env = "qa"
                    elif "dev" in endpoint:
                        test_env = "dev"
                    else:
                        test_env = "prod"
            return test_env
        except KeyError as e:
            logger.error("Key {} is not found".format(e.message))
            pass

    def get_test_region(self):
        """
        TODO: will implement when regions are available for majority services.
        :return:
        """
        default_region = "us-east-1"
        try:
            provided_region = self.data_container.get('REGION', None)
            if provided_region:
                return provided_region
            else:
                return default_region
        except KeyError as e:
            return default_region


    def get_test_service_plugin(self):
        service_plugin = None
        try:
            service_plugin = self.data_container.get('SERVICE_PLUGIN', None)
            logger.info(service_plugin)
            return service_plugin
        except KeyError as e:
            logger.info("Key {} is not found".format(e.message))
            return None

class JsonInfoBuilder:
    """
    Build and upload json to ES.create json object from test file.
    """
    def __init__(self):
        self.test_data = TestInfoBuilder()

    def json_build(self):
        """
        main method for building json blob inserted into
        :return:
        """
        jenkins_job_number = self.test_data.get_build()
        jenkins_test_result_url = self.test_data.get_test_result_url()
        jenkins_job_name = [x for x in jenkins_test_result_url.split("/") if x is not ''][3]
        image_name = self.test_data.get_container_info()
        service = image_name.split(':')[0]
        # sometimes test also check multiple services.
        if ',' in image_name:
            build_id = image_name.split(',')[0].split(':')[1]
        else:
            build_id = image_name.split(':')[1]
        endpoint = self.test_data.get_endpoint()
        test_env = self.test_data.get_test_environment()
        service_plugin = self.test_data.get_test_service_plugin()
        try:
            json_data = dict()
            json_data["image name"] = image_name
            json_data["testtime"] = self.test_data.get_test_time()
            json_data["dockertag"] = build_id
            json_data["service"] = service
            json_data["endpoint"] = endpoint
            json_data["testenv"] = test_env
            test_result = self.test_data.get_test_cases_result()
            json_data["testlink"] = test_result.get("link", None)
            json_data["testpassed"] = test_result.get("passed", None)
            json_data["testfailed"] = test_result.get("failed", None)
            json_data["testskipped"] = test_result.get("skipped", None)
            json_data["plugin"] = service_plugin
            json_data['jenkins_job_name'] = jenkins_job_name
            json_data['jenkins_job_number'] = jenkins_job_number
            json_data['testreport'] = self.test_data.get_test_report()
            json_data['region'] = self.test_data.get_test_region()
            self.upload_json_to_es(json_data, ES, image_name)
            print("Test result to be uploaded...")
            print(json_data)
            return json_data
        except KeyError as e:
            raise AttributeError("Key \'{}\' missing in jenkins actions".format(e.message))

    @staticmethod
    def upload_json_to_es(body, es, id):
        """
        Upload json obj to ES.
        :param body: json data
        :param es: ES host
        :param id: unique id for index.
        :return:
        """
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
            current_index = "testresult_" + date_now
            if es_client.indices.exists(index=current_index):
                es_client.index(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)),
                                body=body)
            else:
                es_client.create(index=current_index, doc_type='json', id=id + str(random.randint(0, 1000)),
                                 body=body)
        except TransportError as e:
            raise ValueError("Problem in {} connection, Error is {}".format(es, e.message))


if __name__ == '__main__':
    J = JsonInfoBuilder()
    J.json_build()