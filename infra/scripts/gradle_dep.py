#!/usr/bin/python
import os
import subprocess
import argparse
import urllib2
from distutils.version import LooseVersion

# Argument parser configuration
parser = argparse.ArgumentParser(description='Determines all service dependencies of Roku libraries')
parser.add_argument('repo', metavar='', help=' /SR GitLab repo to check')
parser.add_argument('--no_git', default=False, action='store_true', help='If true, do not clone/pull from git')
args = parser.parse_args()

if not args.no_git:
    # Get info of the repo through GitLab
    cmd = 'git clone git@gitlab.eng.roku.com:SR/%s.git' % args.repo
    print 'Attempting to clone into SR/%s...' % args.repo
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        print 'Successfully cloned into SR/%s...' % args.repo
    except subprocess.CalledProcessError:
        print 'Unable to clone into SR/%s... The repo may already exist locally.' % args.repo
        if os.chdir(args.repo) is not None:
            raise OSError('Unable to find \'%s\' directory' % args.repo)
        cmd = 'git pull --rebase'
        print 'Attempting to pull from SR/%s to gather updated info...' % args.repo

        try:
            subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            print 'The current branch is up to date...'
        except subprocess.CalledProcessError:
            raise OSError('Unable to git pull --rebase. Check if you have un-staged changes')
    else:
        if os.chdir(args.repo) is not None:
            raise OSError('Unable to find \'%s\' directory.' % args.repo)
else:
    if os.chdir(args.repo) is not None:
        raise OSError('Unable to find \'%s\' directory' % args.repo)

# Find latest versions of artifactory Roku libraries
local_url = urllib2.urlopen('https://artifactory.ctidev.roku.com/artifactory/sr-lib-release-local/com/roku/').read()
ext_url = urllib2.urlopen('https://artifactory.ctidev.roku.com/artifactory/sr-ext-lib/com/roku/').read()
local_libs = []
ext_libs = []

print 'Scanning SR/%s for Roku Artifactory Dependencies... (Please Wait)...' % args.repo
for line in local_url.split('\n'):
    if line.startswith('<a'):
        splitter = line.split('\"')
        local_libs.append(splitter[1][:-1])

for line in ext_url.split('\n'):
    if line.startswith('<a'):
        splitter = line.split('\"')
        ext_libs.append(splitter[1][:-1])

version_dict = {}

for lib in local_libs:
    url = urllib2.urlopen('https://artifactory.ctidev.roku.com/artifactory/sr-lib-release-local/com/roku/%s' % lib)
    versions = []
    for line in url:
        if line.startswith('<a'):
            splitter = line.split('\"')
            if splitter[1].startswith('1.'):
                versions.append(LooseVersion(splitter[1][:-1]))
    if not versions:
        continue
    version_dict[lib] = max(versions)

for lib in ext_libs:
    url = urllib2.urlopen('https://artifactory.ctidev.roku.com/artifactory/sr-ext-lib/com/roku/%s' % lib)
    versions = []
    for line in url:
        if line.startswith('<a'):
            splitter = line.split('\"')
            if splitter[1].startswith('0.'):
                versions.append(LooseVersion(splitter[1][:-1]))
    if not versions:
        continue
    version_dict[lib] = max(versions)

# Find all service + microservices and find Roku Artifactory libraries
services = []
try:
  with open('settings.gradle') as fd:
    for line in fd:
        if line.startswith('project'):
            splitter = line.split('\'')
            services.append(splitter[3])
except:
    print "can\'t find settings.gradle for repo. Not checking"
    exit()

for service in services:
    print_count = 0
    cmd = subprocess.Popen(['gradle', service + ':dependencies', '--configuration', 'compile'], stdout=subprocess.PIPE)
    output = cmd.communicate()[0]
    if cmd.returncode != 0:
        print 'Failed to determine gradle dependencies for %s. Skipping...' % service
        continue
    print '____________________________________________________________________'
    print '=== Roku libraries in use by %s ===' % service
    print '--------------------------------------------------------------------'
    for line in output.split('\n'):
        if '(*)' in line:
            continue
        line = line.lstrip('|+ -\\')
        if line.startswith('com.roku'):
            splitter = line.split(':')
            if LooseVersion(splitter[2]) < version_dict[splitter[1]] or 'BRANCH' in splitter[2]:
                print '%-55s(Outdated by - %s)' % \
                      (line.strip(), ':'.join(splitter[:-1]) + ':' + str(version_dict[splitter[1]]))
            else:
                print line
            print_count += 1
    if not print_count:
        print 'None'

os.chdir('..')
