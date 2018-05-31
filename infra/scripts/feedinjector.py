import requests
import boto3
"""
This script inject feed into QA and Dev environment
"""


def InjectFeed(env="dev", BUCKET_NAME="roku-downloader-886239521314"):
    boto3.setup_default_session(profile_name="886239521314", region_name="us-east-1")
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(BUCKET_NAME)

    for obj in bucket.objects.filter(Prefix="channelMetadata"):
        file_name = obj.key

        if "pending" in file_name:
            pass
        else:
            exclude_feedIds = [
                            "american_classics_canada.current.en",
                            "filmrise_tv_canada.current.en",
                            "filmrise_movies_canada.current.en"]
            feedId = file_name.split('/')[1]
            body = obj.get()['Body'].read()
            payload = str(body)
            if feedId in exclude_feedIds:
                pass
            else:
                url = "http://api.{}.sr.roku.com/downloader/v1/channelmetadata/{}".format(env, feedId)
                send_req = requests.put(url, data=payload)
                print("Environment: {}, feedId : {}, Injected Status: {}".format(env, feedId, send_req.reason))


if __name__ == '__main__':
    InjectFeed(env="dev")
    print("#"*100)
    print("feed injection completed on dev environment")
    print("#" * 100)
    InjectFeed(env="qa")
    print("#" * 100)
    print("feed injection completed on qa environment")
    print("#" * 100)

