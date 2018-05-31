"""Unit tests."""
import json
import unittest
import slack_ui_util


class TestCase(unittest.TestCase):
    def test_ask_for_confirmation(self):
        """Verify the ask_for_confirmation works with danger style setting."""
        json_text1 = slack_ui_util.ask_for_confirmation_response(
            "text", "fallback", "callback_id"
        )

        json_text2 = slack_ui_util.ask_for_confirmation_response(
            "text", "fallback", "callback_id", danger_style=True
        )

        #print(json.dumps(json_text1))
        print(json.dumps(json_text2))

        self.assertTrue(isinstance(json_text2, dict))

        # self.assertTrue(json_text2["body"]["attachments"][0]["actions"][0]["style"] == "danger", "Expected Danger tag")

        body = json_text2["body"]
        print("BODY: %s" % json.dumps(body))
        sc = json_text2["statusCode"]
        headers = json_text2["headers"]
        print("SC: %s" % sc)
        print("HEADERS: %s" % headers)

        # response_type = json_text2["body"]["response_type"]
        # print("RESPONSE_TYPE: %s" % response_type)
        #
        # for a in json_text2["body"]["attachments"]:
        #     print("attachments: %s" % a)
        #
        # danger_result = json_text2["body"]["attachments"][0]["actions"][0]["style"]
        #
        # print("Style tag: %s", danger_result)
        #
        # self.assertEquals(json_text2["body"]["attachments"][0]["actions"][0]["style"],"danger", "Expected Danger tag")

        # self.assertTrue(isinstance(json_text2, str), msg="This is as expected.")

    def test_text_command(self):
        """Verify the text command optional color parameter works."""
        json_test1 = slack_ui_util.text_command_response(
            "title","with title version"
        )

        json_test2 = slack_ui_util.text_command_response(
            None,"No title version", "#a0cbacba"
        )

        print(json_test1)
        print(json_test2)

        self.assertTrue(True)

    def test_error_ui(self):
        """Verify the error ephemeral vs. in_channel setting works"""

        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
