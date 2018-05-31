#!/usr/bin/python
import os
import urllib2
import argparse
import subprocess
import json
from distutils.version import LooseVersion

# Argument parser configuration
parser = argparse.ArgumentParser(description='Release notes of updated Roku Artifactory Library')
parser.add_argument('dir', metavar='', help=' /SR/common GitLab directory (aws1.11.54, es, utils)')
parser.add_argument('hash', metavar='', help='The git commit hash of the newest build')
args = parser.parse_args()

# Get info of SR/common through GitLab
cmd = 'git clone git@gitlab.eng.roku.com:SR/common.git'
print 'Attempting to clone into SR/common...'
try:
    subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    print 'Successfully cloned into SR/common...'
except subprocess.CalledProcessError:
    print 'Unable to clone into SR/common... The repo may already exist locally.'
    if os.chdir('common') is not None:
        raise OSError('Unable to find \'common\' directory')
    cmd = 'git pull --rebase'
    print 'Attempting to pull from SR/common to gather updated info...'

    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        print 'The current branch is up to date...'
    except subprocess.CalledProcessError:
        raise OSError('Unable to git pull --rebase. Check if you have un-staged changes')
else:
    if os.chdir('common') is not None:
        raise OSError('Unable to find \'common\' directory.')

# Find latest versions of artifactory Roku libraries
local_url = urllib2.urlopen('https://artifactory.ctidev.roku.com/artifactory/sr-lib-release-local/com/roku/').read()
local_libs = []

for line in local_url.split('\n'):
    if line.startswith('<a'):
        splitter = line.split('\"')
        local_libs.append(splitter[1][:-1])

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

# Get previous version's Jenkins build number to determine git commit hash
directory = 'common-' + args.dir
build_number = str(version_dict[directory]).split('.')[3]
url = urllib2.urlopen('https://cidsr.eng.roku.com/view/Code/job/code-common-libs-update-artifactory/%s/api/json'
                      % build_number).read()
struct = json.loads(url)
old_hash = struct['changeSet']['items'][0]['commitId']

# Find all commits hashes between previous version hash and new hash
cmd = subprocess.Popen(['git', 'log', '--pretty=%H', '%s' % args.hash, '^%s^' % old_hash], stdout=subprocess.PIPE)
output = cmd.communicate()[0]
if cmd.returncode != 0:
    raise OSError('Failed to git log...')
lines = [line for line in output.split('\n')]
line_str = ' '.join(lines)

# Put the diff into text file release_notes
print '=== Generated release notes between new version and previous version for %s ===' % directory
cmd = 'git show --stat %s > release_notes' % line_str
if subprocess.call(cmd, shell=True):
    raise OSError('Unable to git show...')
