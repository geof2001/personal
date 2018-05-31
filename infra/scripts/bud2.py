#!/usr/bin/python
import threading
import subprocess
import sys
import argparse
import os
import urllib2
import json
import re
import time
import ssl
try:
    import ruamel.yaml
except ImportError:
    print 'Please install the ruamel.yaml module. Try: \'sudo pip install ruamel.yaml\''
    sys.exit(1)
try:
    import filelock as filelock
except ImportError:
    print 'Please install the filelock module. Try: \'sudo pip install filelock\''
    sys.exit(1)

# Argument Parser Configuration
PARSER = argparse.ArgumentParser(description='Build Update Deploy Service Tool')
PARSER.add_argument('services', metavar='', default=None, nargs='*', help='The Service Name(s)')
PARSER.add_argument('--code-branch', metavar='', default=['master'], nargs='*', help='Branch to build against')
PARSER.add_argument('--envs', '--env', '-e', metavar='', default=None, nargs='*', help='qa, dev, prod')
PARSER.add_argument('--debug', default=False, action='store_true', help='If true, don\'t push the build to repo')
PARSER.add_argument('--build', '-b', default=None, metavar='', nargs='*', help='Calls Jenkins Build Job(s) on Services')
PARSER.add_argument('--deploy', '-d', default=None, metavar='', nargs='*', help='Calls Jenkins Deploy Job(s) to Trigger CF')
PARSER.add_argument('--regions', '--region', '-r', default=['us-east-1'], metavar='', nargs='*', help='AWS Region(s)')
PARSER.add_argument('--commit-message', default='', metavar='', help='Optional commit message for the Git Repo')
PARSER.add_argument('--changeset', '-c', default=False, action='store_true', help='Boolean to create CF changeset')
PARSER.add_argument('--smoke', default=None, metavar='', nargs='*', help='If true, conduct a smoke test')
PARSER.add_argument('--regression', default=None, metavar='', nargs='*', help='If true, conduct a smoke test')
PARSER.add_argument('--update', '-u', default=False, action='store_true', help='If true, update config.yaml')
PARSER.add_argument('--publish', '-p', default=False, action='store_true', help='If true, publish libraries')

# Constants
PAST_BUILDS_TO_VIEW = 1000
MAXIMUM_BUILD_MINUTES = 15
MAXIMUM_ALLOWED_CHANGES_IN_YAML = 10
CRITICAL_ENVS = {'prod'}
PRINT_LOCK = threading.RLock()
THREAD_LOCK = threading.RLock()
CONFIG_FILE = 'config.yaml'
CICD_FILE = 'CICD.yaml'
TOKEN = 'REGRESSIONISGOOD'
USER = os.environ.get('USER', os.environ.get('LOGNAME', None))
ACCOUNT_MAP = {'dev': '638782101961',
               'qa': '181133766305',
               'prod': '886239521314'}
AWS_REGIONS = ['us-east-1',
               'us-east-2',
               'us-west-1',
               'us-west-2',
               'ca-central-1',
               'eu-west-1',
               'eu-west-2',
               'eu-central-1',
               'sa-east-1',
               'ap-south-1',
               'ap-northeast-1',
               'ap-northeast-2',
               'ap-southeast-1',
               'ap-southeast-2']
try:
    CACHE_DIR = os.environ['HOME'] + '/.cache.build_and_updateyaml/'
    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    LOCKFILE = os.path.join(CACHE_DIR, '.lock')

    if not os.path.exists(LOCKFILE):
        with open(LOCKFILE, 'w') as wd:
            wd.write('lockfile')
except KeyError:
    raise RuntimeError('Unable to create ~/.cache.build_and_updateyaml/.lock')

LOCK_FILE = filelock.FileLock(LOCKFILE)
LOCK_TIMEOUT = 1


# GitError Custom Exception
class GitError(RuntimeError):
    pass


# BuildError Custom Exception
class BuildError(RuntimeError):
    pass


# UpdateError Custom Exception
class UpdateError(RuntimeError):
    pass


# DeployError Custom Exception
class DeployError(RuntimeError):
    pass


# BuildInfo class to store info after Jenkins build jobs
#
# Fields - name: Name of the service
#          buildnum: Build number
#          jenkins_url: Jenkins URL
#          repo_url: Docker URL
#          user: The user
#          state: State of the Jenkins build job
#          git_hash: The git hash
#          console_text: The console text of the Jenkins build job


class BuildInfo(object):

    def __init__(self, name, buildnum, jenkins_url, repo_url, user, state, git_hash, console_text, recsys_emr):
        self.name = name
        self.buildnum = buildnum
        self.jenkins_url = jenkins_url  # Jenkins URL
        self.repo_url = repo_url  # docker URL
        self.user = user
        self.state = state
        self.git_hash = git_hash
        self.console_text = console_text
        self.recsys_emr = recsys_emr

    @staticmethod
    def CreateBuildInfo(buildnum, jenkins_url, console_text, recsys_emr):
        service_name = None
        repo_url = None
        user = None
        state = None
        git_hash = None
        for line in console_text.split('\n'):
            m = re.search('^Finished: (\w+)', line)
            if m:
                state = m.group(1)

            if recsys_emr:
                m = re.search('upload: .* to (\w\S+)', line, re.I)
                if m:
                    repo_url = m.group(1)
            else:
                m = re.search('Successfully created (\w{4}\S+)', line, re.I)
                if m:
                    repo_url = m.group(1)

            m = re.search('SERVICE_NAME=(\S+)', line)
            if m:
                service_name = m.group(1)

            m = re.search('^checking out revision (\w+)', line, re.I)
            if m:
                git_hash = m.group(1)

            m = re.search('^started by user (.+)$', line, re.I)
            if m:
                user = m.group(1)
            m = re.search('^Tags:\s*(\S.+)$', line, re.I)
            if m:
                user = m.group(1)

        return BuildInfo(service_name,
                         buildnum,
                         jenkins_url,
                         repo_url,
                         user,
                         state,
                         git_hash,
                         console_text,
                         recsys_emr)

    def __repr__(self):
        return "%s(%s,%s,%s)" % (self.name, self.repo_url, self.git_hash, self.state)


# Print function for thread with a print lock and better readability
#
# Parameters - msg: Message to print
#              service_name: Service associated with thread
#
# Returns - None

def tprint(msg, service_name=None):
    msg = msg.encode('utf-8').strip()
    with PRINT_LOCK:
        if service_name:
            print '[%s] %s' % (service_name, msg)
        else:
            print msg

# Open URL without cache
#
# Parameters - url: The URL to open
#
# Returns - Passed in URL content


def urlopen_no_cache(url):
    try:
        context = ssl._create_unverified_context()
        content = urllib2.urlopen(url, context=context).read()
    except AttributeError:
        content = urllib2.urlopen(url).read()

    return content


# Open URL with cache via created local CACHE_DIR directory
#
# Parameters - url: The URL to open
#              use_cache: Boolean value to determine whether cache is used
#
# Returns - Passed in URL content

def urlopen(url, use_cache):

    if not use_cache or not CACHE_DIR or not os.path.exists(CACHE_DIR):
        return urlopen_no_cache(url)

    _url = CACHE_DIR + url.replace(':', '#').replace('/', '|').replace('?', '#')
    _url = re.sub('token=[\w\-]+', 'token', _url)
    if os.path.exists(_url):
        return open(_url).read()
    if os.path.exists('%s.404' % _url):
        raise urllib2.HTTPError(url, 404, 'Previously could not load URL', {}, None)

    try:
        content = urlopen_no_cache(url)
    except urllib2.HTTPError as e:
        if e.code == 404:
            with open('%s.404' % _url, 'w') as fw:
                fw.write(str(e))
        raise e

    jenkins_finished = False
    contents = content.split('\n')
    if len(contents) > 2:
        if 'Finished: ' in contents[-1] or 'Finished: ' in contents[-2]:
            jenkins_finished = True

    if jenkins_finished:
        with open(_url, 'w') as fw:
            fw.write(content)

    return content

# Parallel URL open
#
# Parameters - urls: List of URLS to open
#
# Returns - None


def parallel_urlopen(urls):
    lock = threading.Lock()

    class Worker(threading.Thread):
        def run(self):
            while True:
                with lock:
                    if len(urls) == 0:
                        break
                    url = urls.pop()
                try:
                    urlopen(url, use_cache=True)
                except urllib2.HTTPError as e:
                    continue
    workers = []
    for i in range(0, 16):
        worker = Worker()
        worker.start()
        workers.append(worker)

    for worker in workers:
        worker.join()

# Cleans URL via regex through token stripping
#
# Parameters - url: URL to clean
#
# Returns - Cleaned URL


def clean_url(url):
    return re.sub('([\\?&])?(token)=[\w\-]+', r'\1', url).rstrip('?').rstrip('&')

# Clones into the specified service/microservice repo to get current branch (usually master)
#
# Parameters - service: Service to build
#              microservice: Microservice of service to deploy
#
# Returns - Current git branch


def get_git_branch(service, microservice):

    microservice_path = service + '/' + microservice
    cmd = 'git clone git@gitlab.eng.roku.com:SR/%s.git' % service
    tprint('Attempting to clone into %s to gather info...' % service, microservice_path)
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        tprint(('Successfully cloned into %s...' % service), microservice_path)
    except subprocess.CalledProcessError:
        tprint(('Unable to clone into %s... The repo may already exist locally.' % service), microservice_path)
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory' % service)
        cmd = 'git pull --rebase'
        tprint(('Attempting to pull from SR/%s to gather updated info...' % service), microservice_path)

        try:
            subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            tprint('The current branch is up to date.', microservice_path)
        except subprocess.CalledProcessError:
            raise GitError('Unable to git pull --rebase. Check if you have un-staged changes')
    else:
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory.' % service)

    cmd = 'git rev-parse --abbrev-ref HEAD'
    proc = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE)
    current_branch = proc.communicate()[0]
    if proc.returncode != 0:
        raise GitError('Unable to call: %s.' % cmd)
    current_branch = current_branch.rstrip()
    os.chdir('..')

    return current_branch


# Gets service information from GitLab Repo
#
# Parameters - service: Service to get information for
#
# Returns - Dictionary with build and deploy dictionary info on the service

def get_info_via_git(service):

    git_info = {}
    cmd = 'git clone git@gitlab.eng.roku.com:SR/%s.git' % service
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory' % service)
        cmd = 'git pull --rebase'
        try:
            subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            raise GitError('Unable to git pull --rebase. Check if you have un-staged changes')
    else:
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory.' % service)

    if os.chdir('infra') is not None:
        raise OSError('Unable to find \'infra\' directory.')

    build_params = {}
    deploy_params = {}
    smoke_params = {}
    regression_params = {}
    with open(CICD_FILE) as fd:
        data = ruamel.yaml.round_trip_load(fd)
        for microservice in data['microservice']:
            build_url = data['microservice'][microservice]['build']['url']
            if not build_url.endswith('/') and (build_url.upper() != 'NONE' and build_url != ''):
                build_url = build_url + '/'
            deploy_url = data['microservice'][microservice]['deploy']['url']
            if not deploy_url.endswith('/') and (deploy_url.upper() != 'NONE' and deploy_url != ''):
                deploy_url = deploy.url + '/'
            if 'params' in data['microservice'][microservice]['build']:
                for index, param in enumerate(data['microservice'][microservice]['build']['params']):
                    for key in param:
                        build_params[key] = data['microservice'][microservice]['build']['params'][index][key]
            if 'params' in data['microservice'][microservice]['deploy']:
                for index, param in enumerate(data['microservice'][microservice]['deploy']['params']):
                    for key in param:
                        deploy_params[key] = data['microservice'][microservice]['deploy']['params'][index][key]
            smoke_url = ''
            if 'smoketest' in data['microservice'][microservice]:
                smoke_url = data['microservice'][microservice]['smoketest']['url']
                if not smoke_url.endswith('/'):
                    smoke_url = smoke_url + '/'
                if 'params' in data['microservice'][microservice]['smoketest']:
                    for index, param in enumerate(data['microservice'][microservice]['smoketest']['params']):
                        for key in param:
                            smoke_params[key] = data['microservice'][microservice]['smoketest']['params'][index][key]
            regression_url = ''
            if 'regressiontest' in data['microservice'][microservice]:
                regression_url = data['microservice'][microservice]['regressiontest']['url']
                if not regression_url.endswith('/'):
                    regression_url = regression_url + '/'
                if 'params' in data['microservice'][microservice]['regressiontest']:
                    for index, param in enumerate(data['microservice'][microservice]['regressiontest']['params']):
                        for key in param:
                            regression_params[key] = data['microservice'][microservice]['regressiontest']['params'][index][key]

            json_url = '{url}api/json?token={token}'.format(url=build_url, token=urllib2.quote(TOKEN))
            try:
                struct = json.loads(urllib2.urlopen(json_url).read())
                build_info = {'url': build_url, 'params': build_params, 'build_numbers': struct['lastBuild']['number']}
            except ValueError:
                build_info = {'url': build_url, 'params': build_params, 'build_numbers': ''}

            deploy_info = {'url': deploy_url, 'params': deploy_params}
            smoke_info = {'url': smoke_url, 'params': smoke_params}
            regression_info = {'url': regression_url, 'params': regression_params}
            microservice_dict = {'build': build_info, 'deploy': deploy_info,
                                 'smoke': smoke_info, 'regression': regression_info}
            git_info[microservice] = microservice_dict
            build_params = {}
            deploy_params = {}
            smoke_params = {}
            regression_params = {}

        if 'library' in data:
            publish_url = data['library']['publish']['url']
            if not publish_url.endswith('/') and (publish_url.upper() != 'NONE' and publish_url != ''):
                publish_url = publish_url + '/'
            publish_params = {}
            if 'params' in data['library']['publish']:
                for index, param in enumerate(data['library']['publish']['params']):
                    for key in param:
                        publish_params[key] = data['library']['publish']['params'][index][key]
            json_url = '{url}api/json?token={token}'.format(url=publish_url, token=urllib2.quote(TOKEN))
            try:
                struct = json.loads(urllib2.urlopen(json_url).read())
                library_params = {'url': publish_url, 'params': publish_params, 'build_numbers': struct['lastBuild']['number']}
            except ValueError:
                library_params = {'url': publish_url, 'params': publish_params, 'build_numbers': ''}
            library_info = {'publish': library_params}
            git_info['library'] = library_info

    os.chdir('../..')
    return git_info

# Gets previous build info associated with its build number from Jenkins
#
# Parameters - git_info: Return from get_info_via_git()
#              microservice: Microservice to get build info for
#              start_index: Starting index for loop, determines starting build number URL
#              PAST_BUILDS_TO_VIEW: Constant, determines max amount of builds URLS to go through
#
# Returns - Dictionary with build numbers as keys and their corresponding BuildInfo instances as values


def get_build_info(git_info, microservice, start_index=0, past_builds_to_view=PAST_BUILDS_TO_VIEW):

    if not git_info[microservice]['build']['build_numbers']:
        return

    # If there are less than 100 builds for the service
    if git_info[microservice]['build']['build_numbers'] < past_builds_to_view:
        past_builds_to_view = git_info[microservice]['build']['build_numbers']

    # Pre-load
    urls = []
    index = start_index

    # Get URLS to parallel open using parallel_urlopen() function
    while index < past_builds_to_view and index < git_info[microservice]['build']['build_numbers']:
        build_number_url = '{url}{build_num}'.format(
            url=git_info[microservice]['build']['url'],
            build_num=str(git_info[microservice]['build']['build_numbers'] - past_builds_to_view + 1 + index)
        )
        console_url = '{url}/consoleText?token={token}'.format(url=build_number_url, token=TOKEN)
        urls.append(console_url)
        index += 1
    parallel_urlopen(urls)

    build_number_info = {}
    index = start_index

    # Creates BuildInfo class instances via Jenkins console and associates them with the build number in a dictionary
    while index < past_builds_to_view and index < git_info[microservice]['build']['build_numbers']:
        build_number_url = '{url}{build_num}'.format(
            url=git_info[microservice]['build']['url'],
            build_num=str(git_info[microservice]['build']['build_numbers'] - past_builds_to_view + 1 + index)
        )
        build_number = str(git_info[microservice]['build']['build_numbers'] - past_builds_to_view + 1 + index)
        console_url = '{url}/consoleText?token={token}'.format(url=build_number_url, token=TOKEN)
        console_text_cache = urlopen(console_url, use_cache=True)
        recsys_emr = False
        if 'recsys-emr' in git_info[microservice]['build']['url']:
            recsys_emr = True
        build_number_info[build_number] = BuildInfo.CreateBuildInfo(
            build_number, build_number_url, console_text_cache, recsys_emr)
        index += 1

    return build_number_info

# Gets even older previous build info associated with its build number from Jenkins
#
# Parameters - service: Service to get build info for
#              microservice - Microservice of the specified service
#              build_number_info: Return from get_build_info()
#              current_dir: The current directory to keep track of
#
# Returns - Dictionary with older build numbers as keys and their corresponding BuildInfo instances as values


def get_older_build_info(service, microservice, build_number_info, current_dir):

    microservice_path = service + '/' + microservice
    tprint('ATTENTION: Looking through builds older than the past %d to determine information for the service...'
           % PAST_BUILDS_TO_VIEW, microservice_path)

    if len(build_number_info) == 0:
        raise RuntimeError('Unable to get any build info from Jenkins!')
    oldest_build_num = sorted(map(lambda x: int(x), build_number_info.keys()))[0]
    tprint(('Getting builds older than build #%d,'
           ' this may take a while please be patient...' % oldest_build_num), microservice_path)
    skipped_build_nums = []

    # Pre-load
    urls = []
    while current_dir != os.getcwd():
        time.sleep(3)
    git_info = get_info_via_git(service)
    index = oldest_build_num - 1

    while index > 0 and index > oldest_build_num - PAST_BUILDS_TO_VIEW * 4:
        build_number_url = '{url}{buildnum}/consoleText?token={token}'.format(
                url=git_info[microservice]['build']['url'],
                token=urllib2.quote(TOKEN),
                buildnum=index
        )
        index -= 1
        urls.append(build_number_url)
    parallel_urlopen(urls)
    index = oldest_build_num - 1

    while index > 0 and index > oldest_build_num - PAST_BUILDS_TO_VIEW * 4:
        build_number_url = '{url}{buildnum}/consoleText?token={token}'.format(
            url=git_info[microservice]['build']['url'],
            token=urllib2.quote(TOKEN),
            buildnum=index
        )
        buildnum = index
        try:
            text = urlopen(build_number_url, use_cache=True)
        except urllib2.HTTPError:
            skipped_build_nums.append(index)
            index -= 1
            continue

        recsys_emr = False
        if'recsys-emr' in git_info[microservice]['build']['url']:
            recsys_emr = True
        build_number_info[str(buildnum)] = BuildInfo.CreateBuildInfo(buildnum, build_number_url, text, recsys_emr)
        index -= 1

    if skipped_build_nums:
        print 'Unable to get build #%s (%d/%d) ...' % (
            skipped_build_nums, len(skipped_build_nums), index)

    return build_number_info

# Builds service via Jenkins Build job, adds its info into dictionary of build information
#
# Parameters - service: Service to build
#              microservice: Microservice of service to build
#              debug: Boolean value of debug mode, value taken from command line as a flag
#              branch: The repo branch to be built upon
#              prod_status: Checks whether prod was specified as an env which alters the build
#
# Returns - BuildInfo class instance of new build


def build(service, microservice, debug, branch, prod_status, current_dir):
    microservice_path = service + '/' + microservice
    while current_dir != os.getcwd():
        time.sleep(3)

    git_info = get_info_via_git(service)
    recsys_emr = False
    build_number_info = get_build_info(git_info, microservice)
    # Check if there's an on-going build
    try:
        test_url = '{url}{buildnum}/api/json'.format(url=git_info[microservice]['build']['url'],
                                                     buildnum=str(git_info[microservice]['build']['build_numbers'] + 1))
        urllib2.urlopen(test_url)
        raise BuildError('[%s] Build #%s of (%s) seems to be pending. '
                         'This happens once in a while if multiple Jenkins builds happen at the same time. '
                         'Retry build, and hopefully the problem will go away :) '
                         % (microservice_path, str(git_info[microservice]['build']['build_numbers'] + 1),
                            git_info[microservice]['build']['url']))
    except urllib2.HTTPError:
        pass

    if (git_info[microservice]['build']['url']).upper() == 'NONE' or git_info[microservice]['build']['url'] == '':
        tprint('ERROR: Unable to find Jenkins Build job URL for the service [%s]. The build job will be skipped.'
               % microservice_path)
        return

    # Start build job
    if 'docker' in git_info[microservice]['build']['url']:
        build_url = '{url}buildWithParameters?token={token}&BRANCH={branch}&SERVICE_INFO={service_info}' \
                    '{user}{prodpush}{debug}'.format(
                     url=git_info[microservice]['build']['url'],
                     token=urllib2.quote(TOKEN),
                     branch=urllib2.quote(branch),
                     service_info=urllib2.quote(git_info[microservice]['build']['params']['SERVICE_INFO'])
                     if git_info[microservice]['build']['params']['SERVICE_INFO'] else '',
                     user=('&TAGS=' + urllib2.quote(USER)) if USER else '',
                     prodpush=('&ProdPush=true' if prod_status else ''),
                     debug='&DEBUG=true' if debug else ''
                     )
    elif 'recsys-emr' in git_info[microservice]['build']['url']:
        build_url = '{url}build?token={token}'.format(
            url=git_info[microservice]['build']['url'],
            token=urllib2.quote(TOKEN)
        )
        recsys_emr = True
    elif 'java' in git_info[microservice]['build']['url'] or 'jar' in git_info[microservice]['build']['url']:
        build_url = '{url}buildWithParameters?token={token}&build_name={build_name}'.format(
                     url=git_info[microservice]['build']['url'],
                     token=urllib2.quote(TOKEN),
                     build_name=git_info[microservice]['build']['params']['build_name']
                     )
    # if 'GIT_REPO' in build_url:
    #     build_url = build_url.replace('GIT_REPO' + '%' + '3D%s' % service, 'GIT_REPO' + '%' + '3Dcode')
    build_text = urlopen(build_url, use_cache=False)
    tprint('Kicking off Jenkins build job %s %s (Please Wait Patiently)...' % (microservice_path, build_text), microservice_path)
    tprint("%s" % (re.sub('token=[\-\.\w]+', 'token=***', build_url)), microservice_path)

    time.sleep(10)
    git_info[microservice]['build']['build_numbers'] = git_info[microservice]['build']['build_numbers'] + 1
    last_build_url = '{url}{buildnum}/api/json'.format(url=git_info[microservice]['build']['url'],
                                                       buildnum=str(git_info[microservice]['build']['build_numbers']))
    struct = json.loads(urllib2.urlopen(last_build_url).read())
    build_status = struct['building']
    minutes_elapsed = 10.0 / 60
    while build_status:
        time.sleep(10)
        minutes_elapsed += 10.0/60

        if minutes_elapsed > MAXIMUM_BUILD_MINUTES:
            raise BuildError('Passed %.1f minutes. Build considered failed.' % MAXIMUM_BUILD_MINUTES)
        try:
            struct = json.loads(urllib2.urlopen(last_build_url).read())
        except urllib2.HTTPError:
            struct = json.loads(urllib2.urlopen(last_build_url).read())

        build_status = struct['building']
        tprint("Jenkins build still in process... (%.2f minutes passed)" % minutes_elapsed, microservice_path)

    if struct['result'] == 'FAILURE':
        raise BuildError('Jenkins job #%s failed. Check the console to see why.'
                         % git_info[microservice]['build']['build_numbers'])

    if struct['result'] != 'SUCCESS':
        tprint("Build is finished (Finished status: %s)" % struct['result'], microservice_path)
        raise BuildError('Please check the console to see why job failed.')

    build_number_url = '{url}{build_num}'.format(
        url=git_info[microservice]['build']['url'],
        build_num=str(git_info[microservice]['build']['build_numbers'])
    )
    build_number = str(git_info[microservice]['build']['build_numbers'])
    console_url = '{url}/consoleText?token={token}'.format(url=build_number_url, token=TOKEN)
    time.sleep(1)
    console_text_cache = urllib2.urlopen(console_url).read()
    build_number_info[build_number] = BuildInfo.CreateBuildInfo(build_number, build_number_url, console_text_cache, recsys_emr)

    if recsys_emr:
        tprint('Successfully uploaded jar file to S3: %s.'
               ' Now we need to place this into in the config file.'
               % build_number_info[build_number].repo_url, microservice_path)
    else:
        tprint('Successfully built Docker image: %s.'
               ' Now we need to place this into in the config file.'
               % build_number_info[build_number].repo_url, microservice_path)

    return build_number_info[build_number]


# Updates config.yaml the services Git Repo
#
# Parameters - yaml_file: The yaml file to be updated (config.yaml)
#              build_number_info: Return from get_build_info()
#              service: Service Git Repo to update
#              microservice: The microservice of the service specified
#              envs: The environments to update, taken from the flag --envs in command line
#              regions: The regions to update, taken from flag --regions in command line, default as us-east-1
#              commit_message: Optional commit message when pushing, taken from flag in command line
#              debug: Boolean value of debug mode, value taken from command line as a flag
#
# Returns - None

def update_yaml(yaml_file, build_number_info, service, microservice, envs, regions, commit_message, debug=False):
    envs = set(envs)
    number_of_changes = 0
    service_name = build_number_info.name
    repo_url = build_number_info.repo_url
    microservice_path = service + '/' + microservice
    envs_replaced = []
    regions_replaced = []

    tprint("Attempting to update SR/%s/infra/%s with %s on %s" % (service, CONFIG_FILE,
           build_number_info, list(envs)), microservice_path)

    # if not service_name or not repo_url:
    #     raise UpdateError('Fatal error with service: %s - url: %s.' % (microservice_path, repo_url))

    if os.chdir(service) is not None:
        raise OSError('Unable to find %s directory.' % service)

    if os.chdir('infra') is not None:
        raise OSError('Unable to find \'infra\' directory.')

    # Git pull --rebase command
    cmd = 'git pull --rebase'
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        raise UpdateError('Unable to git pull --rebase. Check if you have un-staged changes.')

    # Loads yaml_file preserving comments into a dictionary and replaces old repo_urls with new ones
    with open(yaml_file) as fd:
        data = ruamel.yaml.round_trip_load(fd)
        if microservice not in data['microservices']:
            response = raw_input('[%s] ATTENTION: Microservice \'%s\' does not exist for service \'%s\'. '
                                 'Would you like to create it?'
                                 ' Enter \'Y\' to create or any other key to continue without creating:\n'
                                 % (microservice_path, microservice, service))
            if response.upper() == 'Y':
                tprint('Creating: microservice \'%s\' for service \'%s\'...'
                       % (microservice, service))
                data['microservices'][microservice] = {}
            else:
                tprint(('\'%s\' will not be created.' % microservice), microservice_path)
                return
        for region in regions:
            if region not in data['microservices'][microservice] and region in AWS_REGIONS:
                response = raw_input('[%s] ATTENTION: Region \'%s\' does not exist for \'%s\'. '
                                     'Would you like to create it with the selected environments?'
                                     ' Enter \'Y\' to create or any other key to continue without creating:\n'
                                     % (microservice_path, region, microservice_path))
                if response.upper() == 'Y':
                    tprint('Creating: [%s][%s] with the selected environments: %s'
                           % (microservice_path, region, envs))
                    data['microservices'][microservice][region] = \
                        {env: repo_url if repo_url and env in ACCOUNT_MAP else {} for env in envs}
                    number_of_changes += len(envs) + 1
                    regions_replaced.append(region)
                else:
                    tprint(('\'%s\' will not be created.' % region), microservice_path)
                    regions.remove(region)
                    continue

            for env in envs:
                if env not in data['microservices'][microservice][region] and env in ACCOUNT_MAP:
                    response = raw_input('[%s] ATTENTION: Environment \'%s\' does not currently exist for \'%s\' in'
                                         '\'%s\'. Would you like to create it?'
                                         ' Enter \'Y\' to create or any other key to continue without creating.\n'
                                         % (microservice_path, env, region, microservice_path))
                    if response.upper() == 'Y':
                        data['microservices'][microservice][region][env] = repo_url
                        number_of_changes += 1
                        envs_replaced.append(env)
                        regions_replaced.append(region)
                        tprint('Creating:\t[%s][%s][%s]\twith repo url:\t%s'
                               % (microservice_path, region, env, data['microservices'][microservice][region][env]))
                    else:
                        tprint(('[%s] \'%s\' will not be created.' % (region, env)), microservice_path)
                        continue

                if data['microservices'][microservice][region][env] != repo_url:
                    old_repo = data['microservices'][microservice][region][env]
                    data['microservices'][microservice][region][env] = repo_url
                    number_of_changes += 1
                    envs_replaced.append(env)
                    regions_replaced.append(region)
                    tprint('Replacing:\t[%s][%s][%s]\t%s\twith\t%s'
                           % (microservice_path, region, env, old_repo, data['microservices'][microservice][region][env]))

    if number_of_changes == 0:
        tprint('Did not need to replace anything!', microservice_path)
        os.chdir('../..')
        return

    if debug:
        tprint('In debugging mode, will not push to repo.', microservice_path)
        os.chdir('../..')
        return

    # Dumps newly written dictionary back into yaml_file
    with open(yaml_file, 'w') as fd:
        ruamel.yaml.round_trip_dump(data, fd)

    # Git diff to check for number of changes made
    proc = subprocess.Popen(['git', 'diff'], stdout=subprocess.PIPE)
    stdout_value = proc.communicate()[0]
    return_code = proc.returncode

    if return_code != 0:
        raise GitError('Unable to perform \'git diff\'.')

    changed_lines = 0

    # Determine number of lines changed for safety precautions via git diff
    for line in stdout_value.split('\n'):
        if line.startswith('+++ ') or line.startswith('--- '):
            continue
        if line.startswith('+') or line.startswith('-'):
            changed_lines += 1
    if changed_lines > MAXIMUM_ALLOWED_CHANGES_IN_YAML or changed_lines > 2 * number_of_changes:
            tprint(('ATTENTION: Excessive number of changes (%d) detected!' % changed_lines), microservice_path)
            response = raw_input('Press ENTER to confirm the changes you see above, or CTRL-C to abort...')
            if len(response) != 0:
                tprint('Aborted git commit.', microservice_path)
                sys.exit(1)

    envs_replaced = set(envs_replaced)
    regions_replaced = set(regions_replaced)

    # Git add
    cmd = 'git add %s' % yaml_file
    if subprocess.call(cmd, shell=True):
        raise GitError('Unable to git add %s. Check if file exists.' % yaml_file)

    # Git commit
    cmd = 'git commit -m \'[{service}] auto-push to {regions} {envs} {repo_url} {commit_message}\''.format(
        service=microservice_path, regions=','.join(regions_replaced), envs=','.join(envs_replaced),
        repo_url=repo_url, commit_message=commit_message
    )
    if subprocess.call(cmd, shell=True):
        raise GitError('Unable to commit. Check if proper file was added to stage.')

    # Git Push
    cmd = 'git push'
    if subprocess.call(cmd, shell=True):
        raise GitError('Unable to git push.')

    os.chdir('../..')

# Deploys service via Jenkins deploy job and CloudFormation
#
# Parameters - service: Service to build
#              microservice: Microservice of service to deploy
#              envs: Environments to deploy to, to be part of the deploy Jenkins URL
#              branch: Branches to deploy to, to be part of the deploy Jenkins URL
#              regions: The regions to deploy to, to be part of the deploy Jenkins URL
#              prod_status: Checks whether prod was specified as an env which alters the build
#              current_dir: The current directory to be kept track of
#
# Returns - None


def deploy(service, microservice, envs, regions, prod_status, current_dir, change_set):
    microservice_path = service + '/' + microservice
    envs = set(envs)
    while current_dir != os.getcwd():
        time.sleep(3)
    git_info = get_info_via_git(service)
    deploy_url = git_info[microservice]['deploy']['url']
    if deploy_url.upper() == 'NONE':
        tprint('ERROR: Unable to find Jenkins Deploy job URL for the service [%s]. The deploy job was skipped.'
               % microservice_path)
        return

    for env in CRITICAL_ENVS:
        if not prod_status and env in envs:
            envs.discard(env)
            tprint(('Sorry, \'%s\' is a critical environment and CF cannot be'
                   ' invoked automatically for safety reasons.'
                    ' Please manually invoke it via: %s' % (env, deploy_url)), microservice_path)

    account_nums = ['AWS_ACCOUNTS=' + ACCOUNT_MAP[env] for env in envs]
    regs = ['AWS_REGIONS=' + region for region in regions]
    params = [key + '=' + str(git_info[microservice]['deploy']['params'][key])
              for key in git_info[microservice]['deploy']['params']]
    deploy_url = '{url}buildWithParameters?token={token}&{params}' \
                 '&CreateChangeSet={changeset}&{accounts}&{regions}{ProdPush}{user}'.format(
                    url=deploy_url,
                    token=urllib2.quote(TOKEN),
                    params='&'.join(params),
                    changeset=change_set,
                    accounts='&'.join(account_nums),
                    regions=('&'.join(regs)) if regions else '',
                    ProdPush='&ProdPush=true' if prod_status else '',
                    user=('&TAGS=' + urllib2.quote(USER)) if USER else ''
                    )
    tprint("%s" % (re.sub('token=[\-\.\w]+', 'token=***', deploy_url)), microservice_path)
    urlopen(deploy_url, use_cache=False)
    tprint('Kicking off Jenkins Deploy job %s (Please Wait Patiently)...' % microservice_path, microservice_path)

    time.sleep(10)
    last_build_url = '{url}lastBuild/api/json'.format(url=git_info[microservice]['deploy']['url'])
    struct = json.loads(urllib2.urlopen(last_build_url).read())
    build_status = struct['building']
    minutes_elapsed = 10.0 / 60
    while build_status:
        time.sleep(10)
        minutes_elapsed += 10.0 / 60

        if minutes_elapsed > MAXIMUM_BUILD_MINUTES:
            raise DeployError('Passed %.1f minutes. Deploy considered failed.' % MAXIMUM_BUILD_MINUTES)
        try:
            struct = json.loads(urllib2.urlopen(last_build_url).read())
        except urllib2.HTTPError:
            struct = json.loads(urllib2.urlopen(last_build_url).read())

        build_status = struct['building']

        tprint("Deployment still in process... (%.2f minutes passed)" % minutes_elapsed, microservice_path)

    if struct['result'] == 'FAILURE':
        raise DeployError('Latest Jenkins deploy job failed. Check the console to see why.')

    if struct['result'] != 'SUCCESS':
        tprint("Deploy is finished (Finished status: %s)" % struct['result'], microservice_path)
        raise DeployError('Please check the console to see why job failed.')

    tprint('Successfully deployed onto CloudFormation.', microservice_path)


# Runs smoke test on the service
#
# Parameters - service: Service to build
#              microservice: Microservice of service to deploy
#              current_dir: The current directory
#
# Returns - None

def smoke_test(service, microservice, current_dir):
    microservice_path = service + '/' + microservice
    while current_dir != os.getcwd():
        time.sleep(3)

    git_info = get_info_via_git(service)
    smoke_url = git_info[microservice]['smoke']['url']
    if smoke_url.upper() == 'NONE' or smoke_url == '':
        tprint('ERROR: Unable to find Jenkins smoke test URL for the service [%s]. The smoke test will be skipped.'
               % microservice_path)
        return
    tprint('Attempting to run smoke test... [%s]' % smoke_url, microservice_path)
    if 'params' in git_info[microservice]['smoke']:
        params = [key + '=' + str(git_info[microservice]['smoke']['params'][key])
                  for key in git_info[microservice]['smoke']['params']]
    smoke_url = '{url}buildWithParameters?token={token}&{params}'.format(
                url=smoke_url,
                token=urllib2.quote(TOKEN),
                params='&'.join(params) if params else '',
    )
    tprint("%s" % (re.sub('token=[\-\.\w]+', 'token=***', smoke_url)), microservice_path)
    urlopen(smoke_url, use_cache=False)
    tprint('Smoke test Jenkins job successfully triggered... Please check Jenkins for its info.', microservice_path)


# Runs a regression test on the service
#
# Parameters - service: Service to build
#              microservice: Microservice of service to deploy
#              current_dir: The current directory
#
# Returns - None

def regression_test(service, microservice, current_dir):
    microservice_path = service + '/' + microservice
    while current_dir != os.getcwd():
        time.sleep(3)

    git_info = get_info_via_git(service)
    regression_url = git_info[microservice]['regression']['url']
    if regression_url.upper() == 'NONE' or regression_url == '':
        tprint('ERROR: Unable to find Jenkins regression test URL for the service [%s].'
               ' The regression test will be skipped.'
               % microservice_path)
        return
    tprint('Attempting to run regression test... [%s]' % regression_url, microservice_path)
    if 'params' in git_info[microservice]['regression']:
        params = [key + '=' + str(git_info[microservice]['regression']['params'][key])
                  for key in git_info[microservice]['regression']['params']]
    regression_url = '{url}buildWithParameters?token={token}&{params}'.format(
                url=regression_url,
                token=urllib2.quote(TOKEN),
                params='&'.join(params) if params else '',
    )
    tprint("%s" % (re.sub('token=[\-\.\w]+', 'token=***', regression_url)), microservice_path)
    urlopen(regression_url, use_cache=False)
    tprint('Regression test Jenkins job successfully triggered... Please check Jenkins for its info.', microservice_path)


# Subclass of threading.Thread to implement multi threading
#
# Functions - __init__(): Constructor
#             run(): Code the thread runs when start() is called, has locks to prevent race condition
#
# Fields - service_name: Service associated with thread
#          args: Arguments from command line
#          status: Status of thread (0 for success)

def publish(service, current_dir):
    while current_dir != os.getcwd():
        time.sleep(3)

    git_info = get_info_via_git(service)
    if 'library' in git_info:
        publish_url = git_info['library']['publish']['url']
        if publish_url.upper() == 'NONE' or publish_url == '':
            tprint('ERROR: Unable to find Jenkins library publish URL for the service [%s].'
                   ' The publishing step will be skipped.' % service)
            return
        tprint('Attempting to publish library onto Artifactory...\n[%s]' % publish_url, service)
        if 'params' in git_info['library']['publish']:
            params = [key + '=' + str(git_info['library']['publish']['params'][key])
                      for key in git_info['library']['publish']['params']]
        publish_url = '{url}buildWithParameters?token={token}&{params}'.format(
            url=publish_url,
            token=urllib2.quote(TOKEN),
            params='&'.join(params) if params else '',
        )
        tprint("%s" % (re.sub('token=[\-\.\w]+', 'token=***', publish_url)), service)
        urlopen(publish_url, use_cache=False)
        tprint('Library publish Jenkins job successfully kicked off...', service)

        time.sleep(10)
        git_info['library']['publish']['build_numbers'] = git_info['library']['publish']['build_numbers'] + 1
        last_build_url = '{url}{buildnum}/api/json'.format(url=git_info['library']['publish']['url'],
                                                           buildnum=git_info['library']['publish']['build_numbers'])
        struct = json.loads(urllib2.urlopen(last_build_url).read())
        build_status = struct['building']
        minutes_elapsed = 10.0 / 60
        while build_status:
            time.sleep(10)
            minutes_elapsed += 10.0 / 60

            if minutes_elapsed > MAXIMUM_BUILD_MINUTES:
                tprint('Passed %.1f minutes. Build considered failed.' % MAXIMUM_BUILD_MINUTES)
            try:
                struct = json.loads(urllib2.urlopen(last_build_url).read())
            except urllib2.HTTPError:
                struct = json.loads(urllib2.urlopen(last_build_url).read())

            build_status = struct['building']

            tprint("Jenkins build still in process... (%.2f minutes passed)" % minutes_elapsed, service)

        if struct['result'] == 'FAILURE':
            tprint('Jenkins job #%s failed. Check the console to see why.'
                   % git_info['library']['publish']['build_numbers'], service)
        elif struct['result'] != 'SUCCESS':
            tprint("Build is finished (Finished status: %s)" % struct['result'], service)
            tprint('Please check the console to see why job failed.', service)
        else:
            tprint('Successfully published libraries onto Artifactory!', service)
            publish_text_url = '{url}{buildnum}/consoleText'.format(url=git_info['library']['publish']['url'],
                                                           buildnum=git_info['library']['publish']['build_numbers'])
            console_text_cache = urllib2.urlopen(publish_text_url).readlines()
            for pub_line in console_text_cache:
                if "Upload" in pub_line and ".jar\n" in pub_line and "sources" not in pub_line:
                    print pub_line
    else:
        tprint('ERROR: Unable to find library information for the service [%s].'
               ' The publishing step will be skipped.' % service)


class ExecuteThread(threading.Thread):

    def __init__(self, service_name, microservice, args, current_git_branch, current_dir, prod_status):
        threading.Thread.__init__(self)
        self.service_name = service_name
        self.microservice = microservice
        self.args = args
        self.current_git_branch = current_git_branch
        self.current_dir = current_dir
        self.prod_status = prod_status
        self.status = 1

    def run(self):
        microservice_path = self.service_name + '/' + self.microservice
        git_info = get_info_via_git(self.service_name)
        if microservice_path.isdigit():
            self.status = 0
            return
        if self.args.publish:
            publish(self.service_name, self.current_dir)
            time.sleep(5)
        if self.args.build is not None and microservice_path in self.args.build:
            services = [service for service in self.args.services if not service.isdigit()]
            branch_map = dict(zip(services, self.args.code_branch))
            for service in services:
                if service not in branch_map:
                    branch_map[service] = 'master'
            if microservice_path in branch_map:
                self.current_git_branch = branch_map[microservice_path]

            # build a new job on Jenkins
            build_info = build(self.service_name,
                               self.microservice,
                               self.args.debug,
                               self.current_git_branch,
                               self.prod_status,
                               self.current_dir)
        elif (self.args.build is not None or self.args.deploy is not None or self.args.envs is not None) and 'none' not in git_info[self.microservice]['build']['url']:
            build_info = None
            # find builds
            while self.current_dir != os.getcwd():
                time.sleep(3)
            git_info = get_info_via_git(self.service_name)
            build_number_info = get_build_info(git_info, self.microservice)
            index = self.args.services.index(microservice_path)

            if self.args.services.index(self.args.services[index]) < len(self.args.services) - 1 and self.args.services[index + 1].isdigit():
                # find a particular build
                build_num = self.args.services[index + 1]
                if int(build_num) > git_info[self.microservice]['build']['build_numbers']:
                    tprint('WARNING: The build number \'%s\' does not exist for [%s] and will '
                           'be skipped.' % (build_num, microservice_path))
                    return 1

                if int(build_num) < int(git_info[self.microservice]['build']['build_numbers']) - PAST_BUILDS_TO_VIEW + 1:
                    build_number_info = get_older_build_info(self.service_name, self.microservice,
                                                             build_number_info, self.current_dir)
                    if not build_number_info:
                        return 1

                    past_builds = get_past_builds(git_info, self.service_name, self.microservice, build_number_info)
                    past_builds.sort(key=lambda b: int(b.buildnum), reverse=True)
                    build_info = build_number_info[build_num]

                    if int(build_num) not in [int(num.buildnum) for num in past_builds]:
                        tprint('--------------------------------------------------------------------------------------')
                        tprint('WARNING: Build #%d is not associated with [%s]' % (int(build_num), microservice_path))
                        tprint('--------------------------------------------------------------------------------------')
                        response = raw_input(
                            'Would you like to use the most recent successful build instead?'
                            ' Enter \'Y\' to proceed or any other key to exit.\n')
                        if response.upper() == 'Y':
                            for _buildinfo in past_builds:
                                if _buildinfo.state == 'SUCCESS':
                                    build_info = _buildinfo
                                    break
                            tprint('Will use the most recent successful build of [%s] instead...' % build_info,
                                   microservice_path)
                        else:
                            print '[%s] will be skipped...' % microservice_path
                            return 1
                else:
                    build_info = build_number_info[build_num]
                    # do nothing for recsys jenkins because they are unique to RecSys
                    if 'recsys' in git_info[self.microservice]['build']['url']:
                        pass
                    else:
                        if self.service_name == 'recsys' and self.microservice == 'api':
                            micro_serv = 'recsys'
                        else:
                            micro_serv = self.microservice

                        if build_info.name != micro_serv:
                            tprint('--------------------------------------------------------------------------------------')
                            tprint('WARNING: Build #%d is not associated with [%s]' % (int(build_num), microservice_path))
                            tprint('--------------------------------------------------------------------------------------')
                            response = raw_input(
                                'Would you like to use the most recent successful build instead?'
                                ' Enter \'Y\' to proceed or any other key to exit.\n')
                            if response.upper() == 'Y':
                                past_builds = [buildinfo for buildinfo in build_number_info.values()
                                               if buildinfo.name == micro_serv]
                                past_builds.sort(key=lambda b: int(b.buildnum), reverse=True)
                                for _buildinfo in past_builds:
                                    if _buildinfo.state == 'SUCCESS':
                                        build_info = _buildinfo
                                        break
                                tprint('Will use the most recent successful build of [%s] instead...' % build_info,
                                       microservice_path)
                            else:
                                print '[%s] will be skipped...' % microservice_path
                                return 1
            else:
                past_builds = get_past_builds(git_info, self.service_name, self.microservice, build_number_info)
                if len(past_builds) <= 5:
                    build_number_info = get_older_build_info(self.service_name, self.microservice,
                                                             build_number_info, self.current_dir)
                    if not build_number_info:
                        return 1

                past_builds = get_past_builds(git_info, self.service_name, self.microservice, build_number_info)
                past_builds.sort(key=lambda b: int(b.buildnum), reverse=True)
                for _buildinfo in past_builds:
                    if _buildinfo.state == 'SUCCESS':
                        build_info = _buildinfo
                        break

            if build_info is None:
                tprint('Unable to find [%s] within previous builds...' % (
                    microservice_path), microservice_path)
                return 1
        else:
            pass

        if (self.args.build is not None or self.args.deploy is not None or self.args.envs is not None) and 'none' not in git_info[self.microservice]['build']['url']:
            if build_info.state != 'SUCCESS':
                tprint("Unable to use %s which finished in %s [%s]." %
                       (build_info.jenkins_url, build_info.state, build_info), microservice_path)
                return 1

        if not self.args.update and not self.args.publish:
            tprint('The --update flag was not called. The config.yaml file will not be updated...', microservice_path)

        if self.args.envs and not self.args.debug and self.args.update:
            with THREAD_LOCK:
                try:
                    with LOCK_FILE.acquire(timeout=LOCK_TIMEOUT):
                        while self.current_dir != os.getcwd():
                            time.sleep(3)
                        update_yaml(CONFIG_FILE,
                                    build_info,
                                    self.service_name,
                                    self.microservice,
                                    self.args.envs,
                                    self.args.regions,
                                    self.args.commit_message,
                                    self.args.debug)
                except filelock.Timeout:
                    while self.current_dir != os.getcwd():
                        time.sleep(3)
                    update_yaml(CONFIG_FILE,
                                build_info,
                                self.service_name,
                                self.microservice,
                                self.args.envs,
                                self.args.regions,
                                self.args.commit_message,
                                self.args.debug)

        if self.args.deploy is not None and microservice_path in self.args.deploy and self.args.envs \
                and not self.args.debug:
            deploy(self.service_name, self.microservice, self.args.envs,
                   self.args.regions, self.prod_status, self.current_dir, self.args.changeset)
        elif self.args.debug:
            tprint('The debug flag was set. Deploy will not be initiated if called.', microservice_path)
            return 1
        elif self.args.envs and self.args.deploy is None:
            tprint('Deploy flag was not called. Please go to Jenkins to deploy manually.', microservice_path)
            tprint('Afterwards, when CloudFormation is deploying in'
                   ' the background, you can check'
                   ' https://console.aws.amazon.com/cloudformation/'
                   ' and https://console.aws.amazon.com/ecs/'
                   ' for the most up to date status.', microservice_path)
        else:
            pass
        if self.args.smoke and microservice_path in self.args.smoke:
            smoke_test(self.service_name, self.microservice, self.current_dir)
        if self.args.regression and microservice_path in self.args.regression:
            regression_test(self.service_name, self.microservice, self.current_dir)

        self.status = 0

# Displays information for services if neither build, deploy, or envs flags are called. If no service, print help screen
#
# Parameters - service: Service to build
#              microservice: Microservice of service specified
#              current_dir: The current directory to be kept track of
#
# Returns - None


def service_info(service, microservice, current_dir, build_num=0):
    microservice_path = service + '/' + microservice
    while current_dir != os.getcwd():
        time.sleep(3)
    git_info = get_info_via_git(service)
    if git_info[microservice]['build']['url'].upper() == 'NONE' or git_info[microservice]['build']['url'] == '':
        tprint('The build URL for this service either does not exist or is invalid. '
               'Therefore, no information about this service can be gathered. It will be skipped.',
               microservice_path)
        return
    if not git_info[microservice]['build']['build_numbers']:
        return
    build_number_info = get_build_info(git_info, microservice)
    build_num = int(build_num)
    if build_num == 0:
        build_num = git_info[microservice]['build']['build_numbers']
    if build_num > git_info[microservice]['build']['build_numbers']:
        tprint('WARNING: The build number \'%s\' does not exist for [%s] and will '
               'be skipped.' % (build_num, microservice_path))
        return

    older_flag = False
    past_builds = get_past_builds(git_info, service, microservice, build_number_info)
    if build_num < git_info[microservice]['build']['build_numbers'] - PAST_BUILDS_TO_VIEW + 1:
        build_number_info = get_older_build_info(service, microservice, build_number_info, current_dir)
        older_flag = True
        if not build_number_info:
            return
        past_builds = get_past_builds(git_info, service, microservice, build_number_info)
    past_builds.sort(key=lambda b: int(b.buildnum), reverse=False)

    tprint('----------------------------------------------------------------------------')
    tprint('=== Recent builds and docker images for %s ===' % microservice_path)
    tprint('----------------------------------------------------------------------------')
    if len(past_builds) == 0:
        if older_flag:
            tprint('Unable to find any within the past %d builds...' % PAST_BUILDS_TO_VIEW * 8)
        else:
            tprint('Unable to find any within the past %d builds...' % PAST_BUILDS_TO_VIEW)
    else:
        for build in past_builds:
            tprint(('%s (%s %s)' % (
                clean_url(build.jenkins_url), build.repo_url, build.state)))

    cmd = 'git clone git@gitlab.eng.roku.com:SR/%s.git' % service
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory' % service)
        cmd = 'git pull --rebase'
        try:
            subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            raise GitError('Unable to git pull --rebase. Check if you have un-staged changes')
    else:
        if os.chdir(service) is not None:
            raise OSError('Unable to find %s directory.' % service)

    if os.chdir('infra') is not None:
        raise OSError('Unable to find \'infra\' directory.')

    tprint('----------------------------------------------------------------------------')
    tprint('=== Current content in SR/%s/infra/%s ===' % (service, CONFIG_FILE))
    tprint('----------------------------------------------------------------------------')
    with open(CONFIG_FILE) as fd:
        data = ruamel.yaml.round_trip_load(fd)
        output = ''
        for line in ruamel.yaml.round_trip_dump(data, indent=5, block_seq_indent=3).splitlines(True):
            output += line
        print output

    os.chdir('../..')


def get_past_builds(git_info, service, microservice, build_number_info):
    if 'recsys' in git_info[microservice]['build']['url']:
        past_builds = [buildinfo for buildinfo in build_number_info.values()]
    elif service == 'recsys' and microservice == 'api':
        past_builds = [buildinfo for buildinfo in build_number_info.values() if buildinfo.name == 'recsys']
    else:
        past_builds = [buildinfo for buildinfo in build_number_info.values() if buildinfo.name == microservice]
    return past_builds


# Help screen of BUD, with sample commands
def bud_help():
    print """
    ---------------------------------------------------------------------------------------------------
                                                Flags
    ---------------------------------------------------------------------------------------------------
    (--build)(-b)    -     Builds services inputted after flag (all if not specified) and negates build number if inputted.
    (--envs)(--env)(-e)  - Environments to build, update, and deploy for [dev, qa, prod].
    (--update)(-u)      -  Takes the most recent successful build(unless a  build # is specified) and updates on config.yaml (Default: False)
    (--deploy)(-d)   -     Deploys services inputted after flag (all if not specified) and negates build number if inputted.
    (--regions)(-r)  -     AWS Regions to update/deploy specified after --regions flag. (Default: us-east-1)
    (--changeset)(-c)  -   Creates changeset when deploying. (Default: False)
    (--debug)    -     Debug mode. Doesn't update/deploy when the flag is specified.
    (--smoke)    -     Conducts a smoke test on the service. (Default: None)
    (--regression) -   Conducts a regression test on the service. (Default: None)
    (--code-branch) -  Code branch to build against. (Default: master)
    (--commit-message) - Optional commit message when updating config.yaml file.\n
    ---------------------------------------------------------------------------------------------------
    This will give you the latest info of the service(s) from Jenkins and the YAML file...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed\n
    ---------------------------------------------------------------------------------------------------
    You can input multiple service(s) as a command to gather info, build, update, deploy...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed myfeed/myfeed-contenteventcreator recsys/client\n
    ---------------------------------------------------------------------------------------------------
    This will do the traditional build, update, and deploy of the service(s)...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed recsys/api --build --envs dev qa --update --deploy\n
    ---------------------------------------------------------------------------------------------------
    Without the update flag (--update)(-u), calling deploy will just deploy whats currently on the config file...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed --envs dev qa --deploy\n
    ---------------------------------------------------------------------------------------------------
    You can input build numbers [AFTER] service names to update, deploy with that specific build #...
    (No number after defaults as the latest build of that service)
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed 1238 recsys/api 384 --envs dev qa --update --deploy\n
    ---------------------------------------------------------------------------------------------------
    This will take the latest existing Jenkins build of myfeed/api, update the YAML file, and deploy...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed --envs dev qa --update --deploy\n
    ---------------------------------------------------------------------------------------------------
    You can choose to build/deploy certain services by putting their names after their respective flags...
    By disregarding this, all services inputted will be built/deployed...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed recsys/api --build myfeed/api --envs dev qa --update --deploy\n
    (This will build myfeed/api only, but deploy both myfeed/api and recsys/client with their latest builds)\n
    ---------------------------------------------------------------------------------------------------
    You can deploy to specific regions with the --regions flag, note that default will be us-east-1 only...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed recsys/api --build --envs dev qa --update --deploy --regions us-east-1 eu-west-1\n
    ---------------------------------------------------------------------------------------------------
    If regression/smoke tests are setup and put on the CICD.yaml file, you can use run them through bud2
    as well with the flags --regression and/or --smoke...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed --envs dev qa --update --deploy --smoke\n
    ---------------------------------------------------------------------------------------------------
    To create a changeset when deploying, use the --changeset (-c) flag...
    ---------------------------------------------------------------------------------------------------\n
    ./bud2 myfeed/myfeed --envs dev qa --update --deploy --changeset\n
    ---------------------------------------------------------------------------------------------------
    """


# Main Function
def main():
    args = PARSER.parse_args()
    current_dir = os.getcwd()
    if not args.services and (args.build is not None or args.deploy is not None
                              or args.smoke is not None or args.regression is not None):
        exit('No service was inputted. Please make sure the services precede the flags as they are required arguments.')
    if args.build is not None and len(args.build) == 0:
        args.build = args.services
    if args.deploy is not None and len(args.deploy) == 0:
        args.deploy = args.services
    if args.smoke is not None and len(args.smoke) == 0:
        args.smoke = args.services
    if args.regression is not None and len(args.regression) == 0:
        args.regression = args.services
    for region in args.regions:
        if region not in AWS_REGIONS:
            exit('\'%s\' is not a valid AWS region.' % region)
    if args.envs:
        for env in args.envs:
            if env not in ACCOUNT_MAP:
                exit('\'%s\' is an unfamiliar environment.' % env)
    if args.deploy is not None and not args.envs:
        exit('Cannot deploy without environments. Please take out the deploy flag or specify environments.')
    if not args.build and not args.envs and not args.deploy and not args.smoke and not args.regression and not args.publish:
        if len(args.services) > 0:
            for full_service in args.services:
                if full_service.isdigit():
                    continue
                if '/' not in full_service:
                    print '\'%s\' is not a valid service. Format of service name: ' \
                          '<repo/microservice_name>' % full_service
                    continue
                service, microservice = full_service.split('/')
                index = args.services.index(service + '/' + microservice)
                if args.services.index(args.services[index]) < len(args.services) - 1 and args.services[index + 1].isdigit():
                    build_num = args.services[index + 1]
                    service_info(service, microservice, current_dir, build_num)
                else:
                    service_info(service, microservice, current_dir)
        else:
            bud_help()
        return 1

    prod_status = False
    if args.envs and 'prod' in args.envs:
        tprint('------------------------------------------------------------------------------------------------------')
        tprint('WARNING: \'prod\' was inputted as an environment.\nThis will alter the repo url '
               'of \'prod\' in the config.yaml file(s) when updating and further alter the parameters '
               'of the build and deploy jobs.')
        tprint('------------------------------------------------------------------------------------------------------')
        response = raw_input('Enter \'Y\' to proceed or any other key to exit.\n')
        if response.upper() == 'Y':
            prod_status = True
        else:
            exit('Exited. \'Y\' was not entered.')

    threads = []
    for full_service in args.services:
        if full_service.isdigit():
            continue
        if '/' not in full_service:
            print '\'%s\' is not a valid service. Format of service name: ' \
                  '<repo/microservice_name>' % full_service
            continue
        service, microservice = full_service.split('/')
        while current_dir != os.getcwd():
            time.sleep(3)
        current_git_branch = get_git_branch(service, microservice)
        thread = ExecuteThread(service, microservice, args, current_git_branch, current_dir, prod_status)
        thread.start()
        threads.append(thread)
        if len(args.services) > 1:
            time.sleep(20)
        else:
            time.sleep(11)
    for thread in threads:
        thread.join()
    sum_status = sum([t.status for t in threads])

    for full_service in args.services:
        if full_service.isdigit():
            continue
        if '/' not in full_service:
            print '\'%s\' is not a valid service. Format of service name: ' \
                  '<repo/microservice_name>' % full_service
            continue
        service, microservice = full_service.split('/')
        cmd = 'rm -rf %s' % service
        if subprocess.call(cmd, shell=True):
            raise OSError('Unable to remove directory %s. The directory may not exist...' % service)

    return sum_status


if __name__ == '__main__':
    main()
