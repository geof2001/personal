import boto3
import json
import logging
import subprocess
import os
import re
import urllib2
import argparse
from urlparse import parse_qs

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Build Update Deploy Service Tool')
PARSER.add_argument('command', metavar='', default=None, nargs='*', help='The command')
PARSER.add_argument('--services', '--service', '-s', metavar='', default=None, nargs='*', help='qa, dev, prod')
PARSER.add_argument('--envs', '--env', '-e', metavar='', default=None, nargs='*', help='qa, dev, prod')
PARSER.add_argument('--regions', '--region', '-r', default=['us-east-1'], metavar='', nargs='*', help='AWS Region(s)')
PARSER.add_argument('--create', default=False, action='store_true', help='If true, create new property')

sts = boto3.client('sts')
kms = boto3.client('kms')
dynamodb = boto3.resource('dynamodb')
bud_users_table = dynamodb.Table('BudUsers')
expected_token = os.environ['slackToken']

logger = logging.getLogger()
logger.setLevel(logging.INFO)
current = boto3.client('sts').get_caller_identity()
logger.info('caller ID: %s' % current)
environments = {"dev": '638782101961', "qa": '181133766305', "prod": '886239521314'}


def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def props_list_table(table):
    results = table.scan()
    logger.info(results)
    info = ''
    for item in results['Items']:
        info += '---------------------------------------------------------------'
        info += '---------------------------------------\n'
        info += '*{}* : {}\n'.format(item['key'], item['value'])
    return info


def props_confirm(body):
    data = json.loads(body['payload'][0])

    if data['callback_id'] == 'confirm_delete':
        prop, db_table, stack, region, env = re.findall('\(([^)]+)', data['original_message']['text'])
        session = sts.assume_role(RoleArn='arn:aws:iam::%s:role/quentin-bud-test' % environments[env],
                                  RoleSessionName='quentin-bud-test')
        cf = boto3.client('cloudformation', aws_access_key_id=session['Credentials']['AccessKeyId'],
                          aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                          aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        dynamodb = boto3.resource('dynamodb', aws_access_key_id=session['Credentials']['AccessKeyId'],
                                  aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                                  aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                response = table.delete_item(Key={'key': prop})
                return respond(None, {"response_type": "in_channel",
                                      "text": "Successfully deleted key [%s] in table [%s] for stack [%s] in [%s][%s]..." % (
                                      prop, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#a0ffaa"
                                          }
                                      ]
                                      })
            except:
                return respond(None, {"response_type": "ephemeral",
                                      "text": "Unable to delete key [%s] in table [%s] for stack [%s] in [%s][%s]..." % (
                                      prop, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#ff3d3d"
                                          }
                                      ]
                                      })
        else:
            return respond(None, {"response_type": "ephemeral",
                                  "text": "Property [%s] will not be deleted from table [%s] for stack [%s] in [%s][%s]..." % (
                                  prop, db_table, stack, region, env),
                                  "attachments": [
                                      {
                                          "text": "%s" % props_list_table(table),
                                          "mrkdwn_in": ["text"],
                                          "color": "#ff3d3d"
                                      }
                                  ]
                                  })

    if data['callback_id'] == 'confirm_set':
        prop, value, db_table, stack, region, env = re.findall('\(([^)]+)', data['original_message']['text'])
        session = sts.assume_role(RoleArn='arn:aws:iam::%s:role/quentin-bud-test' % environments[env],
                                  RoleSessionName='quentin-bud-test')
        cf = boto3.client('cloudformation', aws_access_key_id=session['Credentials']['AccessKeyId'],
                          aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                          aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        dynamodb = boto3.resource('dynamodb', aws_access_key_id=session['Credentials']['AccessKeyId'],
                                  aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                                  aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                response = table.update_item(Key={'key': prop},
                                             UpdateExpression="set #v = :r",
                                             ExpressionAttributeValues={':r': value},
                                             ExpressionAttributeNames={'#v': 'value', '#k': 'key'},
                                             ConditionExpression='attribute_exists(#k)',
                                             ReturnValues="UPDATED_NEW")
                return respond(None, {"response_type": "in_channel",
                                      "text": "Successfully set property [%s] to value [%s] in table [%s] for stack [%s] in [%s][%s]..." % (
                                      prop, value, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#a0ffaa"
                                          }
                                      ]
                                      })
            except:
                return respond(None, {"response_type": "ephemeral",
                                      "text": "Unable to set property [%s] to value [%s] in table [%s] for stack [%s] in [%s][%s]. That property may not exist. To create a new property, make sure to include the --create flag in your command..." % (
                                      prop, value, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#a0ffaa"
                                          }
                                      ]
                                      })
        else:
            return respond(None, {"response_type": "ephemeral",
                                  "text": "Property [%s]'s value will not be set to [%s] for table [%s] for stack [%s] in [%s][%s]..." % (
                                  prop, value, db_table, stack, region, env),
                                  "attachments": [
                                      {
                                          "text": "%s" % props_list_table(table),
                                          "mrkdwn_in": ["text"],
                                          "color": "#ff3d3d"
                                      }
                                  ]
                                  })

    if data['callback_id'] == 'confirm_create':
        prop, value, db_table, stack, region, env = re.findall('\(([^)]+)', data['original_message']['text'])
        session = sts.assume_role(RoleArn='arn:aws:iam::%s:role/quentin-bud-test' % environments[env],
                                  RoleSessionName='quentin-bud-test')
        cf = boto3.client('cloudformation', aws_access_key_id=session['Credentials']['AccessKeyId'],
                          aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                          aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        dynamodb = boto3.resource('dynamodb', aws_access_key_id=session['Credentials']['AccessKeyId'],
                                  aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                                  aws_session_token=session['Credentials']['SessionToken'], region_name=region)
        table = dynamodb.Table(db_table)
        if data['actions'][0]['value'] == 'yes':
            try:
                response = table.update_item(Key={'key': prop},
                                             UpdateExpression="set #v = :r",
                                             ExpressionAttributeValues={':r': value},
                                             ExpressionAttributeNames={'#v': 'value', '#k': 'key'},
                                             ConditionExpression='attribute_not_exists(#k)',
                                             ReturnValues="UPDATED_NEW")
                return respond(None, {"response_type": "in_channel",
                                      "text": "Successfully created property [%s] with value [%s] in table [%s] for stack [%s] in [%s][%s]..." % (
                                      prop, value, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#a0ffaa"
                                          }
                                      ]
                                      })
            except:
                return respond(None, {"response_type": "ephemeral",
                                      "text": "Unable to create property [%s] with value [%s] in table [%s] for stack [%s] in [%s][%s]. That property may already exist..." % (
                                      prop, value, db_table, stack, region, env),
                                      "attachments": [
                                          {
                                              "text": "%s" % props_list_table(table),
                                              "mrkdwn_in": ["text"],
                                              "color": "#a0ffaa"
                                          }
                                      ]
                                      })
        else:
            return respond(None, {"response_type": "ephemeral",
                                  "text": "Property [%s] will not be created for table [%s] for stack [%s] in [%s][%s]..." % (
                                  prop, db_table, stack, region, env),
                                  "attachments": [
                                      {
                                          "text": "%s" % props_list_table(table),
                                          "mrkdwn_in": ["text"],
                                          "color": "#ff3d3d"
                                      }
                                  ]
                                  })


def handle_deploy(bud_user, user_name, command):
    if command not in environments:
        return respond(None, {"response_type": "ephemeral", "text": "Sorry, account %s is not supported." % (command)})
    deploy_url = '{url}buildWithParameters?token={token}&GIT_BRANCH={branch}&AWS_ACCOUNTS={accounts}&TAGS={user}'.format(
        url=os.environ['jenkinsUrl'],
        token=os.environ['jenkinsToken'],
        branch="master",
        accounts=environments[command],
        user=user_name
    )
    logger.info(deploy_url);
    response = urllib2.urlopen(deploy_url)
    html = response.read()
    logger.info(html)
    return respond(None, {"response_type": "ephemeral", "text": "Deploying to %s" % (command), "attachments": [
        {
            "text": html
        }
    ]})


def handle_add_user(bud_user, command):
    m = re.search('^<@(.*)\|(.*)> *(.*)$', command)
    userid = m.group(1)
    user_name = m.group(2)
    role = m.group(3)
    logger.info(bud_user)
    logger.info("Adding user %s with role %s" % (userid, role))
    if bud_user['role'] != "admin":
        return respond(None,
                       {"response_type": "ephemeral", "text": "Sorry, you need to be an admin to use this command."})

    if not role:
        role = "dev"
    bud_users_table.put_item(
        Item={
            'userid': userid,
            'role': role,
            'username': user_name
        }
    )
    return respond(None, {"response_type": "ephemeral",
                          "text": "User <@%s|%s> was added with role %s" % (userid, user_name, role)})


def handle_remove_user(bud_user, command):
    m = re.search('^<@(.*)\|(.*)>.*$', command)
    userid = m.group(1)
    user_name = m.group(2)
    logger.info(bud_user)
    logger.info("Removing user %s (%s)" % (userid, user_name))
    if bud_user['role'] != "admin":
        return respond(None,
                       {"response_type": "ephemeral", "text": "Sorry, you need to be an admin to use this command."})

    bud_users_table.delete_item(
        Key={
            'userid': userid
        }
    )
    return respond(None, {"response_type": "ephemeral", "text": "User <@%s|%s> was removed" % (userid, user_name)})


def handle_props(command, args):
    if 'help' in command.strip():
        return respond(None, {"response_type": "in_channel",
                              "text": "Gets the properties of the specified service.",
                              "attachments": [
                                  {
                                      "text": "*Format:* _/bud props <action> -s <service>  -e <environment> -r <region>_\n*Example:* _/bud props list -s search -e dev -r us-east-1_\n\n*<list>* _Lists properties_\n*<set>* _Sets a property to the specified value_\n*<get>* _Gets the value of a specified property_\n",
                                      "mrkdwn_in": ["text"],
                                      "color": "#00b2ff"
                                  }
                              ]
                              })

    session = sts.assume_role(RoleArn='arn:aws:iam::%s:role/quentin-bud-test' % environments[args.envs[0]],
                              RoleSessionName='quentin-bud-test')
    cf = boto3.client('cloudformation', aws_access_key_id=session['Credentials']['AccessKeyId'],
                      aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                      aws_session_token=session['Credentials']['SessionToken'], region_name=args.regions[0])
    dynamodb = boto3.resource('dynamodb', aws_access_key_id=session['Credentials']['AccessKeyId'],
                              aws_secret_access_key=session['Credentials']['SecretAccessKey'],
                              aws_session_token=session['Credentials']['SessionToken'], region_name=args.regions[0])

    logger.info(session)
    logger.info('caller ID: %s' % current)
    stacks = cf.describe_stacks(StackName=args.services[0])
    table = dynamodb.Table(stacks['Stacks'][0]['Outputs'][0]['OutputValue'])

    if args.command[1] == 'list':
        return respond(None, {"response_type": "in_channel",
                              "text": "Table [%s] of stack [%s]..." % (
                              stacks['Stacks'][0]['Outputs'][0]['OutputValue'], args.services[0]),
                              "attachments": [
                                  {
                                      "text": "%s" % props_list_table(table),
                                      "mrkdwn_in": ["text"],
                                      "color": "#a0ffaa"
                                  }
                              ]
                              })

    if args.command[1] == 'set':
        if not args.create:
            return respond(None, {"response_type": "in_channel",
                                  "text": "Are you sure you want to set property (%s) to value (%s), from table (%s) for stack (%s) in (%s)(%s)?" % (
                                  args.command[2], args.command[3], stacks['Stacks'][0]['Outputs'][0]['OutputValue'],
                                  args.services[0], args.regions[0], args.envs[0]),
                                  "attachments": [
                                      {
                                          "fallback": "Unable to process click",
                                          "callback_id": "confirm_set",
                                          "color": "#3AA3E3",
                                          "attachment_type": "default",
                                          "actions": [
                                              {
                                                  "name": "button1",
                                                  "text": "Yes",
                                                  "type": "button",
                                                  "value": "yes"
                                              },
                                              {
                                                  "name": "button2",
                                                  "text": "No",
                                                  "type": "button",
                                                  "value": "no"
                                              },
                                          ]
                                      }
                                  ]
                                  })
        else:
            return respond(None, {"response_type": "in_channel",
                                  "text": "Are you sure you want to create property (%s) with value (%s), for table (%s) of stack (%s) in (%s)(%s)?" % (
                                  args.command[2], args.command[3], stacks['Stacks'][0]['Outputs'][0]['OutputValue'],
                                  args.services[0], args.regions[0], args.envs[0]),
                                  "attachments": [
                                      {
                                          "fallback": "Unable to process click",
                                          "callback_id": "confirm_create",
                                          "color": "#3AA3E3",
                                          "attachment_type": "default",
                                          "actions": [
                                              {
                                                  "name": "button1",
                                                  "text": "Yes",
                                                  "type": "button",
                                                  "value": "yes"
                                              },
                                              {
                                                  "name": "button2",
                                                  "text": "No",
                                                  "type": "button",
                                                  "value": "no"
                                              },
                                          ]
                                      }
                                  ]
                                  })

    if args.command[1] == 'delete':
        response = table.get_item(Key={'key': args.command[2]})
        if 'Item' not in response:
            return respond(None, {"response_type": "in_channel",
                                  "text": "Key [%s] does not exist in table [%s] for stack [%s] in [%s][%s]..." % (
                                  args.command[2], stacks['Stacks'][0]['Outputs'][0]['OutputValue'], args.services[0],
                                  args.regions[0], args.envs[0]),
                                  "attachments": [
                                      {
                                          "text": "%s" % props_list_table(table),
                                          "mrkdwn_in": ["text"],
                                          "color": "#a0ffaa"
                                      }
                                  ]
                                  })
        return respond(None, {
            "response_type": "in_channel",
            "text": "Are you sure you want to delete (%s) from table (%s) for stack (%s) in (%s)(%s)?" % (
            args.command[2], stacks['Stacks'][0]['Outputs'][0]['OutputValue'], args.services[0], args.regions[0],
            args.envs[0]),
            "attachments": [
                {
                    "fallback": "Unable to process click",
                    "callback_id": "confirm_delete",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "button1",
                            "text": "Yes",
                            "type": "button",
                            "value": "yes",
                            "style": "danger"

                        },
                        {
                            "name": "button2",
                            "text": "No",
                            "type": "button",
                            "value": "no"
                        },
                    ]
                }
            ]
        })


def lambda_handler(event, context):
    logger.info(event)
    if 'payload' in parse_qs(event['body']):
        return props_confirm(parse_qs(event['body']))

    params = parse_qs(event['body'])
    token = params['token'][0]
    if token != expected_token:
        logger.error("Request token (%s) does not match expected", token)
        return respond(Exception('Invalid request token'))

    response = bud_users_table.get_item(
        Key={
            'userid': params['user_id'][0],
        }
    )

    if 'Item' not in response:
        return respond(None, {"response_type": "ephemeral",
                              "text": "Sorry, I can't take orders from you. Ask an admin in SR team to be given permission to use this service."})

    bud_user = response['Item']
    command_text = params['text'][0]
    user = params['user_name'][0]

    args = PARSER.parse_args(command_text.split())

    logger.info('COMMAND: %s' % args.command)
    logger.info('SERVICES: %s' % args.services)
    logger.info('ENVS: %s' % args.envs)
    logger.info('REGIONS: %s' % args.regions)

    if args.command[0] == 'add_user':
        return handle_add_user(bud_user, command_text[9:])
    elif args.command[0] == 'remove_user':
        return handle_remove_user(bud_user, command_text[12:])
    elif args.command[0] == 'deploy':
        return handle_deploy(bud_user, user, command_text[7:])
    elif args.command[0] == 'props':
        return handle_props(command_text[6:], args)
    else:
        return respond(None, {"response_type": "ephemeral",
                              "text": "The command is invalid. Please enter a valid command..."})

    command = params['command'][0]
    channel = params['channel_name'][0]

    return respond(None, {"response_type": "ephemeral", "text": "%s invoked %s in %s with the following text: %s" % (
    user, command, channel, command_text), "attachments": [
        {
            "text": "Will now take action on the command..."
        }
    ]})