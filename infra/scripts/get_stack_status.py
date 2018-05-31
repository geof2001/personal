import argparse
import boto3

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Gets CF stack status')
PARSER.add_argument('-a', '--accounts', metavar='', default=None, help='AWS Accounts')
PARSER.add_argument('--regions', metavar='', default=None, help='AWS Regions')
PARSER.add_argument('--stack', metavar='', default=None, help='Stack Name')
args = PARSER.parse_args()

boto3.setup_default_session(profile_name=args.accounts, region_name=args.regions)

# cf = boto3.client('cloudformation')
cf = boto3.resource('cloudformation')

stack = cf.Stack(args.stack)
stack_status = stack.stack_status
print stack_status

# stack_events = cf.describe_stack_events(StackName=args.stack)
# current_status = stack_events['StackEvents'][0]['ResourceStatus']
# print current_status
