#!/usr/bin/env python

import boto3
import zipfile
import csv
import gzip
import json
import os

account_set = {"638782101961", "181133766305", "886239521314", "661796028321"}
account_map = {"638782101961": "dev", "181133766305": "qa", "886239521314": "prod", "661796028321": "infra"}
source_bucket = 'roku-billing'
dest_bucket = 'roku-billing-analysis'
# add your log group here as key, and the spend category as value
loggroupmap = {
    '/svc/idresolver': 'content-svcs',
    '/svc/int-gateway': 'ecs-service',
    '/svc/tfs': 'legacy-content-svcs',
    '/svc/imagefetcher2': 'images-svcs',
    '/svc/cms/api2': 'legacy-content-svcs',
    '/svc/search/imageresizer': 'images-svcs',
    '/svc/ext-gateway': 'ext-haproxy',
    '/svc/deduper': 'cap',
    '/svc/cms/etlpipeline': 'legacy-content-svcs',
    '/svc/myfeed/api': 'myfeed',
    '/svc/homescreen': 'homescreen',
    '/svc/search/api': 'search',
    '/svc/capingestor': 'cap',
    '/svc/myfeed/myfeed-contenteventupdater': 'myfeed',
    '/svc/content': 'content-svcs',
    '/svc/content-redis/data-loader': 'content-svcs',
    '/svc/datafetcher2': 'cap',
    '/svc/searchindexer': 'cap',
    '/svc/bookmarker': 'bookmarks',
    '/svc/downloader2etl2': 'cap',
    '/svc/ota': 'search',
    '/aws/batch/job': 'recsys',
    '/svc/bifservice': 'bif'
}
arn_assignments = {
    'arn:aws:rds:us-east-1:886239521314:cluster:cluster-a7l67jqkptq7pusvrtujqirfgy': 'cap',
    'arn:aws:rds:us-east-1:181133766305:cluster:cluster-qyvoeepskl3itr4d44pjxej2ba': 'cap',
    'arn:aws:rds:us-east-1:638782101961:cluster:cluster-ynjrbdmceg23swehmolj4ozsku': 'cap',
    'arn:aws:rds:us-east-1:638782101961:cluster:cluster-snii3ca7sdjeuecm3bjgfiivfi': 'cap',
    'arn:aws:rds:us-east-1:886239521314:cluster:cluster-buifzb6j4dut54rirbwig6y3si': 'cap',
    'arn:aws:es:us-east-1:181133766305:domain/beehive-es-6': 'beehive',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/search-api-details': 'search',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/search-api-options': 'search',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/search-api-searches': 'search',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/tracking-ota': 'search',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/tracking-homescreen': 'homescreen',
    'arn:aws:firehose:us-east-1:638782101961:deliverystream/search-api-options': 'search',
    'arn:aws:firehose:us-east-1:638782101961:deliverystream/search-api-details': 'search',
    'arn:aws:firehose:us-east-1:638782101961:deliverystream/search-api-searches': 'search',
    'arn:aws:firehose:us-east-1:181133766305:deliverystream/tracking-ota': 'search',
    'arn:aws:firehose:us-east-1:181133766305:deliverystream/tracking-ota-registration': 'search',
    'arn:aws:firehose:us-east-1:886239521314:deliverystream/tracking-ota-registration': 'search',
    'arn:aws:ecr:us-east-1:638782101961:repository/bifservice': 'bif',
    'arn:aws:ecr:us-east-1:638782101961:repository/bookmarker': 'bookmarks',
    'arn:aws:ecr:us-east-1:638782101961:repository/bookmarker-batch': 'bookmarks',
    'arn:aws:ecr:us-east-1:638782101961:repository/deduper': 'cap',
    'arn:aws:ecr:us-east-1:638782101961:repository/homescreen': 'homescreen',
    'arn:aws:ecr:us-east-1:638782101961:repository/datafetcher': 'cap',
    'arn:aws:ecr:us-east-1:638782101961:repository/search': 'search',
    'arn:aws:ecr:us-east-1:638782101961:repository/content': 'content-svcs',
    'arn:aws:ecr:us-east-1:638782101961:repository/downloader2etl': 'cap',
    'arn:aws:ecr:us-east-1:638782101961:repository/gateway': 'ecs-service',
    'arn:aws:ecr:us-east-1:638782101961:repository/tfs': 'legacy-content-svcs',
    'arn:aws:ecr:us-east-1:638782101961:repository/cmsloader2': 'cap',
    'arn:aws:ecr:us-east-1:638782101961:repository/popularity': 'tracking',
    'arn:aws:ecr:us-east-1:638782101961:repository/registrar': 'ecs-service',
    'arn:aws:ecr:us-east-1:638782101961:repository/search-indexer': 'cap',
    'arn:aws:ecr:us-east-1:638782101961:repository/searchindexercap': 'cap'
}
ri_cost = {
    'c3.2xlarge': 0.248000,
    'c3.4xlarge': 0.840000,
    'c3.8xlarge': 0.992000,
    'c4.large': 0.059000,
    'c5.large': 0.050000,
    'c4.8xlarge': 0.947000,
    'm3.xlarge': 0.163000,
    'm3.2xlarge': 0.324000,
    'm4.large': 0.058000,
    'm5.large': 0.057000,
    'r3.xlarge': 0.176000,
    'r3.2xlarge': 0.353000,
    'r3.8xlarge': 1.411000,
    'r4.large': 0.078000,
    'r4.xlarge': 0.156000,
    'r4.4xlarge': 0.626000,
    't2.micro': 0.007000,
    't2.small': 0.013000,
    't2.medium': 0.027000,
    't2.nano': 0.003000
}
dest_manifest_prefix = ''
dest_data_prefix = 'data'
files_to_process = 2


def write_line(csv_writer, csv_row, index_adjust):
    # zero out a few rows we don't use since it's just a description that takes up space
    csv_writer.writerow((csv_row[0], None, csv_row[2], None, None,
                         csv_row[5], None, None, None, csv_row[9],
                         csv_row[10], csv_row[11], csv_row[12], None, csv_row[14],
                         None, csv_row[16], csv_row[17], csv_row[18], csv_row[19],
                         csv_row[20], csv_row[21], csv_row[22], csv_row[23], csv_row[24],
                         csv_row[25], csv_row[26], csv_row[27], csv_row[28], csv_row[29],
                         csv_row[30], None, csv_row[32+index_adjust], csv_row[33+index_adjust], csv_row[34+index_adjust],
                         None, None))
    return


def parse_instance_and_family(usage, index, spot):
    instance_type = usage[index:]
    family = instance_type[:instance_type.rfind('.')]
    return instance_type, family, spot


def get_instance_and_family(usage):
    index = usage.find('BoxUsage:')
    if index >= 0:
        return parse_instance_and_family(usage, index+9, False)

    index = usage.find('SpotUsage:')
    if index >= 0:
        return parse_instance_and_family(usage, index+10, True)

    index = usage.find('NodeUsage:')
    if index >= 0:
        return parse_instance_and_family(usage, index+10, False)

    return None


if __name__ == '__main__':
    s3 = boto3.resource('s3')
    listing = s3.meta.client.list_objects(Bucket=source_bucket, Prefix='088414020449-aws-billing-detailed-line-items-with-resources-and-tags-')
    bills = listing['Contents'][-files_to_process:]
    downloaded_files = 0

    for bill in bills:
        key = bill['Key']
        size = bill['Size']
        local_file = key
        local_size = -1
        try:
            local_size = os.path.getsize(local_file)
        except:
            pass

        if size > local_size:
            print("Downloading {}...".format(key))
            s3.Bucket(source_bucket).download_file(key, local_file)
            print("Download into {} finished".format(local_file))
            downloaded_files += 1
        else:
            print ("Skipping {} because local size is the same as remote size".format(key))

    if downloaded_files == 0:
        print ("No new data downloaded - skipping processing and upload to s3")
        exit(0)

    gzipout = 'aws-billing-detailed-line-items-with-resources-and-tags.csv.gz'
    first = True
    count = 0
    print("Processing data prior to upload...")
    with gzip.open(gzipout, 'wb') as gzout:
        writer = csv.writer(gzout)
        count = 0
        for bill in bills:
            key = bill['Key']
            print("Processing {} ...".format(key))
            adjust = -1
            if key.find('2018-03') >= 0:
                adjust = 0
            with zipfile.ZipFile(key) as zf:
                with zf.open(key.replace('.zip', '')) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if first:
                            write_line(writer, row, 0)
                            first = False
                        # Only process line items and not totals otherwise it screws up analysis
                        # also replace numerical account with string to make charts easier to read
                        elif row[2] in account_set and row[3] == 'LineItem':
                            row[2] = account_map.get(row[2])
                            # 33 is Spend_Category
                            # 5 is product name
                            # 21 is resourceid
                            # 13 is item description

                            # if no category - mark it as 'unknown' so it's friendlier in quicksight filtering
                            if not row[33+adjust]:
                                row[33+adjust] = 'unknown'
                            # the aws support item should get marked as 'support' category
                            if row[5] and row[5].find('Support') >= 0:
                                row[21] = 'support'
                                row[33+adjust] = 'support'
                            # assign spend category of athena-query to all Athena spend
                            if row[5] and row[5].find('Athena') >= 0:
                                row[21] = 'athena-query'
                                row[33+adjust] = 'athena-query'
                            # by default all cloudwatch and xray goes under monitoring category
                            if row[5] and (row[5].find('CloudWatch') >= 0 or row[5].find('X-Ray') >= 0):
                                if not row[21]:
                                    row[21] = 'monitoring'
                                row[33+adjust] = 'monitoring'
                            # if it's the first file getting processed mark it as 'previous', other wise 'current'
                            # this refers to previous or current month
                            if count == 0:
                                row[0] = 'previous'
                            elif count == 1:
                                row[0] = 'current'
                            # if the arn is a log group, override the category with one from the map defined
                            # at the top of the file
                            if row[21] and row[21].find(':log-group:') > 0:
                                key = row[21][row[21].rfind(':')+1:]
                                if key in loggroupmap:
                                    row[33+adjust] = loggroupmap[key]
                            # otherwise if the arn is in the arn_overrides, use that category
                            elif row[21] and row[21] in arn_assignments:
                                row[33+adjust] = arn_assignments[row[21]]

                            # hijack column 29 to put instance family or N/A
                            # convert usage column to have pure instance type
                            row[29] = 'n/a'
                            if row[9]:
                                type_family = get_instance_and_family(row[9])
                                if type_family:
                                    row[9] = type_family[0]
                                    row[29] = type_family[1]
                                    if type_family[2]:
                                        row[12] = 'S'
                                    if type_family[0] in ri_cost and row[12] == 'Y':
                                        row[17] = ri_cost[type_family[0]]
                                        row[18] = float(row[16]) * ri_cost[type_family[0]]
                            # edge lambdas are not getting tagged properly
                            if row[21] and row[21].find('function:us-east-1.jwt-edge-token-verify') >= 0:
                                row[33+adjust] = 'content-svcs'

                            # if infra account - just set spend_category to infra
                            if row[2] == "infra":
                                row[33+adjust] = 'infra'

                            write_line(writer, row, adjust)
            count += 1

    print("Uploading into {}".format(dest_bucket + '/' + dest_data_prefix + '/' + gzipout))

    infras3 = s3
    # need the following for local testing because I have two profiles, one with access to
    # billing bucket and one with access to infra s3
    session = boto3.session.Session(profile_name='661796028321')
    infras3 = session.resource('s3')
    infras3.meta.client.upload_file(gzipout, dest_bucket, dest_data_prefix + '/' + gzipout)
    manifest = {
        "fileLocations": [
            {
                "URIs": [
                    "s3://" + dest_bucket + "/" + dest_data_prefix + "/" + gzipout
                ]
            }
        ],
        "globalUploadSettings": {
            "textqualifier": "\""
        }
    }
    manifest = json.dumps(manifest)
    manifestObject = infras3.Object(dest_bucket, dest_manifest_prefix + 'manifest.json')
    manifestObject.put(Body=manifest)
    print("Upload complete.")
