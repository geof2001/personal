import sys
import boto3
import datetime
import logging
import requests
import json
import time
from requests_aws_sign import AWSV4Sign
from elasticsearch import Elasticsearch, RequestsHttpConnection,TransportError




"""



"""

RECORDER_ES = "search-event-recorder-fxiq7oydlpvhadn67twlmt5ska.us-west-2.es.amazonaws.com"
#SLACK_CHANNEL = "https://hooks.slack.com/services/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"
#SLACK_CHANNEL_PROD = "https://hooks.slack.com/services/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"
#SLACK_CHANNEL_NON_PROD = "https://hooks.slack.com/services/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"

# tmp change for testing, will be move back to original afterwards.
SLACK_CHANNEL_NON_PROD = "https://hooks.slack.com/services/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"
SLACK_CHANNEL_PROD = "https://hooks.slack.com/services/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"

class Notification:

    def __init__(self, message):
        self.message = None
        #self.slack_channel = SLACK_CHANNEL
        self.slack_channel = ""
        # Put service nameon which sending notification.
        self.service_list = ['homescreen','search','content']
        
        if message.get('fail'):
            #self.message = "*`Failed notification`*"
            self.message = "\n*`Environment : {}`*".format(message.get('environment'))
            self.message += "\n`Endpoint : {}`".format(message.get('endpoint'))
            self.message += "\n`Region : {}`".format(message.get('region'))
            self.message += "\t`Service : {}`".format(message.get('service'))
            self.message += "\n`Testcase Failed : {}`".format(message.get('testfailed'))
            self.message += "\t`Testcase Passed : {}`".format(message.get('testpassed'))
            self.message += "\n`Test Link : {}`".format(message.get('testlink'))
            self.message += "\n`Test Report : {}`".format(message.get('testreport'))

        if message.get('fail increment'):
            # self.message = "*`Incremental Failed notification`*"
            self.message = "\n*`Environment : {}`*".format(message.get('environment'))
            self.message += "\n`Endpoint : {}`".format(message.get('endpoint'))
            self.message += "\n`Region : {}`".format(message.get('region'))
            self.message += "\t`Service : {}`".format(message.get('service'))
            self.message += "\n`Testcase Failed : {}`".format(message.get('testfailed'))
            self.message += "\t`Testcase Passed : {}`".format(message.get('testpassed'))
            self.message += "\n`Test Link : {}`".format(message.get('testlink'))
            self.message += "\n`Test Report : {}`".format(message.get('testreport'))
     
        if message.get('recover'):
            #self.message = "*`Recover notification`*"
            self.message = "\n*`Environment : {}`*".format(message.get('environment'))
            self.message += "\n`Endpoint : {}`".format(message.get('endpoint'))
            self.message += "\n`Region : {}`".format(message.get('region'))
            self.message += "\t`Service : {}`".format(message.get('service'))
            self.message += "\n`Testcase Failed : {}`".format(message.get('testfailed'))
            self.message += "\t`Testcase Passed : {}`".format(message.get('testpassed'))
            self.message += "\n`Test Link : {}`".format(message.get('testlink'))
            self.message += "\n`Test Report : {}`".format(message.get('testreport'))
        
    def send_notification(self):
        self.slack_channel = SLACK_CHANNEL_NON_PROD
        if self.message is not None:
            if message.get('environment') == "qa" or message.get('environment') == "dev":
                self.slack_channel = SLACK_CHANNEL_NON_PROD
            if message.get('environment') == "prod":
                self.slack_channel = SLACK_CHANNEL_PROD
            if message.get('fail'):
                data = {"attachments": [
                        {"color": "#ff0000",

                        "mrkdwn_in": ["text"],
                        "text": self.message
                        }
                ]}
            if message.get('recover'):
                data = {"attachments": [
                    {"color": "#00ff00",
                     "mrkdwn_in": ["text"],
                     "text": self.message
                     }
                ]}

            if message.get('fail increment'):
                data = {"attachments": [
                    {"color": "#ff0000",

                     "mrkdwn_in": ["text"],
                     "text": self.message
                     }
                ]}
            print(data)
            json_params_encoded = json.dumps(data)
            if message.get('service') in self.service_list:
                slack_response = requests.post(url=self.slack_channel, data=json_params_encoded, headers={"Content-type": "application/json"})
                if slack_response.text == 'ok':
                    print ('\n Successfully posted pytest report on Slack channel')
                else:
                    print ('\n Something went wrong. Unable to post pytest report on Slack channel. Slack Response:', slack_response)






class Query:

    def __init__(self):
        session = boto3.session.Session()
        credentials = session.get_credentials()
        region = "us-west-2"
        service = 'es'
        auth = AWSV4Sign(credentials, region, service)
        try:
            self.es_client = Elasticsearch(host=RECORDER_ES, port=443, connection_class=RequestsHttpConnection,
                                      http_auth=auth, use_ssl=True, verify_ssl=True)
            date_now = (datetime.datetime.now()).strftime('%Y-%m')
            self.current_index = "testresult_" + date_now
        except TransportError as e:
            raise ValueError("Problem in {} connection, Error is {}".format(RECORDER_ES, e.message))

    def query_by_string(self,job_name, job_id):
        # job_name and job_id query gives unique result.
        #data = job_name + job_id
        WAIT = 30
        TRIES = 3
        while(TRIES):
            q = {
                "query": {
                    "query_string": {
                        "query": "jenkins_job_name:\"{}\" AND jenkins_job_number:\"{}\"".format(job_name, job_id)
                    }
                }
            }
            search_result = self.es_client.search(index="test*", doc_type="json", body=q)
            print("Elastic Query is: {}".format(q))
            print("And search result is :{}".format(search_result))
            # check in case of missing or data is not present for a while.Some times elastic search takes time to upload.
            if search_result.get('hits').get('total') == 0:
                time.sleep(WAIT)
                TRIES -= 1
            else:
                break
        if TRIES == 0:
            sys.exit(0)
        # job_id and job_name combined must be unique across jenkins.
        if search_result.get('hits').get('total') != 1:
            print("job id is not unique")
        content_list = search_result.get('hits').get('hits')
        if content_list is not []:
            print("%"*100)
            print(content_list)
            print("%" * 100)
            try:
                test_result_data = content_list[0]
                return test_result_data.get('_source')
            except IndexError:
                pass
        return None

    def get_run_environment(self, jobdata):
        env = jobdata.get("testenv")
        if env == "None":
            endpoint = jobdata.get("endpoint")
            if "qa" in endpoint:
                env = "qa"
            elif "dev" in endpoint:
                env = "dev"
            else:
                env = "prod"
            return env
        else:
            return env

    def get_build_notification(self, job_link,job_id):
        notification = {}
        try:
            job_name = [x for x in job_link.split("/") if x is not ""][-3]
            #job_id = int([x for x in testlink.split("/") if x is not ""][-2])
            job_id = int(job_id)
            current_job_data  = self.query_by_string(job_name,job_id)
            if current_job_data != None:
                current_job_env = self.get_run_environment(current_job_data)
                current_job_region = current_job_data.get('region', None)
                notification['environment'] = current_job_env
                notification['region'] = current_job_region
                past_job_data = self.query_by_string(job_name,job_id-1)
                past_job_env = self.get_run_environment(past_job_data)
                past_job_region = past_job_data.get('region', None)
                past_counter = 1
                while(current_job_env != past_job_env):
                    past_job_data = self.query_by_string(job_name,job_id - past_counter)
                    past_job_env = self.get_run_environment(past_job_data)
                    past_counter += 1
                    
                print("@"*100)
                print("PAST JOB FOUND: {}".format(past_job_data))
                print("@" * 100)
                print(current_job_data.get('testfailed'))
                print(past_job_data.get('testfailed'))
                if current_job_data.get('testfailed') != 0 and past_job_data.get('testfailed') != 0:
                    if current_job_data.get('testfailed') == past_job_data.get('testfailed'):
                        pass
                    if current_job_data.get('testfailed') > past_job_data.get('testfailed'):
                        notification['fail increment'] = True
                        notification['endpoint'] = current_job_data.get('endpoint')
                        notification['service'] = current_job_data.get('service')
                        notification['testpassed'] = current_job_data.get('testpassed')
                        notification['testfailed'] = current_job_data.get('testfailed')
                        notification['testskipped'] = current_job_data.get('testskipped')
                        notification['testlink'] = current_job_data.get('testlink')
                        notification['testreport'] = current_job_data.get('testreport', None)

                if current_job_data.get('testfailed') != 0 and past_job_data.get('testfailed') == 0:
                    notification['fail'] = True
                    notification['endpoint'] = current_job_data.get('endpoint')
                    notification['service'] = current_job_data.get('service')
                    notification['testpassed'] = current_job_data.get('testpassed')
                    notification['testfailed'] = current_job_data.get('testfailed')
                    notification['testskipped'] = current_job_data.get('testskipped')
                    notification ['testlink'] = current_job_data.get('testlink')
                    notification ['testreport'] = current_job_data.get('testreport',None)

                if current_job_data.get('testfailed') == 0 and past_job_data.get('testfailed') != 0:
                    notification['recover'] = True
                    notification['endpoint'] = current_job_data.get('endpoint')
                    notification['service'] = current_job_data.get('service')
                    notification['testpassed'] = current_job_data.get('testpassed')
                    notification['testfailed'] = current_job_data.get('testfailed')
                    notification['testskipped'] = current_job_data.get('testskipped')
                    notification ['testlink'] = current_job_data.get('testlink')
                    notification ['testreport'] = current_job_data.get('testreport',None)
            else:
                print("Data is not found for job {}".format(job_id))
            return notification
        except ValueError:
            print ("Job id is not found.Check testlink")



if __name__ == '__main__':
    job_id = sys.argv[1]
    job_link = sys.argv[2]
    q = Query()
    message = q.get_build_notification(job_link,job_id)
    n = Notification(message)
    n.send_notification()