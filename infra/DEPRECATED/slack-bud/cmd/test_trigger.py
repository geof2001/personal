"""Module to start tests."""
import logging
import requests
import slack_ui_util


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# Global params
JENKINS_TOKEN = "REGRESSIONISGOOD"
JENKINS_URL = "https://cidsr.eng.roku.com"
# Map Test Job with service
NAME_MAP = {
    "content": "z_test-content-services-smoketests_jinesh"
}

CONTENT_SERVICE_ENDPOINT = {
    "us-east-1": "content-int-sr-blue-us-east-1.sr.roku.com",
    "us-west-2": "content-int-sr-blue-us-west-2.sr.roku.com"
}


def handle_test_trigger(command, response_url, args):
    job_url = ""

    if 'help' in command.strip():
        title = "Start smoke test on specific service."
        text = "*Format:* _/bud smoketest -s <service> -r <region>_\n" \
               "*Example:* _/bud smoketest -s content -r us-east-1_\n"
        return slack_ui_util.text_command_response(title, text, "#00b2ff")

    if not args:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "in_channel",
                "text":
                    "*Please provide valid arguments, see more "
                    "/bud smoketest help*",
                "mrkdwn_in": ["text"],
                "color": "#00b2ff"
            }
        )

    args.regions[0] = args.regions[0].lower()
    args.services[0] = args.services[0].lower()

    if args.services[0] == 'content':
        if args.regions[0] == "us-east-1":
            job_url = JENKINS_URL + '/job/{}/buildWithParameters?' \
                                    'token={}' \
                                    '&OVERRIDE_TARGET_HOSTNAME={}' \
                                    '&RESPONSE_URL={}'\
                .format(NAME_MAP.get('content'),
                        JENKINS_TOKEN,
                        CONTENT_SERVICE_ENDPOINT.get('us-east-1'),
                        response_url)
            logging.info("Trigger Job URL: {}".format(job_url))
            res = requests.post(job_url)
            logging.info(
                "Jenkins Smoke test Job response:"
                " {}".format(res.status_code)
            )
            if res.status_code != 201:
                logging.info("Please check jenkins smoke test job")
            return slack_ui_util.respond(
                None,
                {
                    "response_type": "in_channel",
                    "text": "*Smoke test started "
                            "on {} service in {}"
                            " region*".format(
                        str(args.services[0]),
                        str(args.regions[0]))
                }
            )

        elif args.regions[0] == "us-west-2":
            job_url = JENKINS_URL +\
                      '/job/{}/buildWithParameters?token={}' \
                      '&OVERRIDE_TARGET_HOSTNAME={}' \
                      '&RESPONSE_URL={}'\
                          .format(NAME_MAP.get('content'),
                                  JENKINS_TOKEN,
                                  CONTENT_SERVICE_ENDPOINT.get('us-west-2'),
                                  response_url)
            logging.info("Trigger Job URL: {}".format(job_url))
            res = requests.post(job_url)
            logging.info("Jenkins Smoke test Job response:"
                         " {}".format(res.status_code))
            if res.status_code != 201:
                logging.info("Please check jenkins smoke test job")
            return slack_ui_util.respond(
                None,
                {
                    "response_type": "in_channel",
                    "text":
                        "*Smoke test started on {} service in {}"
                        " region*".format(
                            str(args.services[0]), str(args.regions[0])
                        )
                }
            )
        else:
            logging.info("Region Does not match")
            return slack_ui_util.respond(
                None,
                {
                    "response_type": "in_channel",
                    "text":
                        "*Region Does not match.Please Enter valid region "
                        "like us-east-1 or us-west-2*"
                }
            )
    else:
        return slack_ui_util.respond(
            None,
            {
                "response_type": "in_channel",
                "text":
                    "*Currently this command works with content service only*"
            }
        )
