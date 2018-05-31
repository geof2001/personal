#!/usr/bin/python
# import argparse
# from datetime import datetime
import argparse
import os
import subprocess

try:
    from gitlab import Gitlab
except ImportError as e:
    print 'Please install the gitlab module. Try: \'sudo pip install python-gitlab\''
    print e
    exit(1)

if __name__ == '__main__':

    # Argument parser configuration
    parser = argparse.ArgumentParser(description='Setups webhooks for Gitlab')
    parser.add_argument('-a', '--audit', default=False, action='store_true')
    parser.add_argument('-u', '--update', default=False, action='store_true')
    args = parser.parse_args()

    # git archive --remote=git@gitlab.eng.roku.com:SR/datafetcher.git master infra | tar -t
    conf_file = os.path.expanduser('~/.sr/config')
    with open(conf_file) as f:
        token = f.readline().rstrip()

    # GitLab Credentials for authentication
    gl = Gitlab('https://gitlab.eng.roku.com/', token)

    gl.auth()

    # Loop through all projects
    projects = gl.projects.list(all=True)

    for project in projects:
        cmd = 'git archive --remote=git@gitlab.eng.roku.com:SR/' + project.name + '.git master infra | tar -t'

        # check if this is a Tucson compatible repo
        is_tucson = False
        proc = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        if 'did not match any files' in proc:
            print "%s - not a Phoenix project" % project.name
            continue
        elif 'infra/service_info.yaml' in proc:
            print "%s - is a Tucson Project" % project.name
            is_tucson = True
        else:
            print "%s not a Tucson project" % project.name
            continue

        create_hook = False
        remove_test_hook = False
        hooks = project.hooks.list()
        if len(hooks) == 0:
            print "No hooks in project:", project.name
            if is_tucson:
                create_hook = True
        else:
            for hook in hooks:
                print "found hook: ", hook.url
                if 'utils-service-info-populate' in hook.url and is_tucson:
                    print "found service hooK: ", hook.url
                elif is_tucson:
                    print "Tucson project", project.name, " doesn\'t have service hook"
                    create_hook = True

        if not args.audit and create_hook and args.update:
            print "Setting up web hook for"
            new_hook = project.hooks.create(
                            {'url': 'https://cidsr.eng.roku.com/project/utils-service-info-populate',
                             'push_events': 1,
                             'token': 'cfb6afca526e0d9bb291f35d1a1accf2'})
