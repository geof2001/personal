#!/usr/bin/python
import argparse
from datetime import datetime
try:
    from gitlab import Gitlab
except ImportError:
    print 'Please install the gitlab module. Try: \'sudo pip install python-gitlab\''
    exit(1)

# Argument parser configuration
parser = argparse.ArgumentParser(description='Determines all dead branches in /SR Repo')
parser.add_argument('-d', '--days', '--day', metavar='', type=int, help=' Days since last commit', default='60')
args = parser.parse_args()

# GitLab Credentials for authentication
gl = Gitlab('https://gitlab.eng.roku.com/', 'XKkALxEsnwSaQwbDgiyF')
#gl = Gitlab('https://gitlab.eng.roku.com/', 'KvQaBkiuiZ4JPH9vqWQg')
gl.auth()

# Loop through all projects and their branches to check latest commit dates
projects = gl.projects.list(all=True)
print '=== Going through every /SR Repo to find all branches older than %d day(s) ===' % args.days
branches_found = 0

for project in projects:
    branches = project.branches.list(all=True)
    for branch in branches:
        commits = project.commits.list(ref_name=branch.name)
        latest_commit = str(commits[0].committed_date)[:-6]
        latest_commit = datetime.strptime(latest_commit, "%Y-%m-%dT%H:%M:%S.%f")
        time_passed = datetime.now() - latest_commit
        days_passed = time_passed.days
        if days_passed >= args.days:
            st = 'SR/%s [%s]' % (project.name, branch.name)
            print '%-45s %s ago\t' % (st, str(time_passed))
            branches_found += 1

if not branches_found:
    print 'No branches were found with a commit of %d days or over.' % args.days
