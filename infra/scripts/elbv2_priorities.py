#!/usr/bin/python
import boto3
import botocore
import argparse

def listRules(listeners, conn):
  for listener in listeners['Listeners']:
    rules = conn.describe_rules(ListenerArn=listener['ListenerArn'])
    print("Priority:\tPath:\t\tTargetGroup:")
    for rule in rules['Rules']:
      if rule['Priority'] == 'default':
        print("%s\t\t%s\t\t%s") % (rule['Priority'],rule['Conditions'],rule['Actions'][0]['TargetGroupArn'].split("/")[1])
      else:
        priority = rule['Priority']
        path = rule['Conditions'][0]['Values']
        targetGroup = rule['Actions'][0]['TargetGroupArn']
        print("%s\t\t%s\t\t%s" % (priority, path[0], targetGroup.split("/")[1]))


def stringMatch(mystr, mytype, conn):
  args = parser.parse_args()
  elbs = conn.describe_load_balancers()
  for lb in elbs['LoadBalancers']:
    print("\nLoadbalancer name: %s" % (lb['LoadBalancerName']))
    if mytype == 'arn' and mystr == lb['LoadBalancerArn']:
      listeners = conn.describe_listeners(LoadBalancerArn=lb['LoadBalancerArn'])
      listRules(listeners, conn)
      exit()

    elif mytype == 'name' and mystr == lb['LoadBalancerName']:
      listeners = conn.describe_listeners(LoadBalancerArn=lb['LoadBalancerArn'])
      listRules(listeners, conn)
      exit()
    else:
      listeners = conn.describe_listeners(LoadBalancerArn=lb['LoadBalancerArn'])
      listRules(listeners, conn)
      exit()

def main(profile, region, arn, name):
    print ("Profile: %s\nRegion: %s\nARN: %s\nName: %s") % (profile, region, arn, name)
    
    if not profile:
      parser.print_help()
      exit()
    # establish AWS session using provided profile
    boto3.setup_default_session(profile_name=profile, region_name=region)
    
    # establish client for elbv2 api calls
    elbv2 = boto3.client('elbv2')

    if name and arn:
      print("You only need to specify the name of the ELB or its ARN but not both.")
      exit()

    if name:
      stringMatch(name,'name', elbv2)
      
    if arn:
      stringMatch(arn, 'arn', elbv2)

    if not arn and not name:
      elbs = elbv2.describe_load_balancers()
      for lb in elbs['LoadBalancers']:
        print("\nLoadbalancer name: %s" % (lb['LoadBalancerName']))
        listeners=elbv2.describe_listeners(LoadBalancerArn=lb['LoadBalancerArn'])
        listRules(listeners, elbv2)
    exit()
    
if __name__ == '__main__':
    #
    # Define argparse arguments
    #
    
    parser = argparse.ArgumentParser(description='Shows the priorities of ELBV2 Listeners')
    parser.add_argument('--profile', '-p', metavar='', help=' AWS Profile to use')
    parser.add_argument('--region', '-r', metavar='', help=' AWS Region to get listeners from', default='us-east-1')
    parser.add_argument('--arn', '-a', metavar='', help=' ELBV2 Arn that you want to get priorities for')
    parser.add_argument('--name', '-n', metavar='', help=' Name of ELBV2 you want to list priorities for')
    args = parser.parse_args()
    
    #
    # call main here
    #
    
    main(args.profile, args.region, args.arn, args.name)
