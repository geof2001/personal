import argparse
try:
    import gitlab
except ImportError:
    exit('Please install the gitlab module. Try: \'sudo pip install python-gitlab\'')

# Argument parser configuration
parser = argparse.ArgumentParser(description='Creates service repo with sample templates')
parser.add_argument('service', metavar='', help=' Name of SR service/repo')
parser.add_argument('--microservices', '-m', metavar='', nargs='*', help=' Microservices of the specified service')
args = parser.parse_args()

# GitLab Credentials for authentication
gl = gitlab.Gitlab('https://gitlab.eng.roku.com/', 's3Ltz3P_xFqba-C266ms')
gl.auth()


# CICD.yaml setup
def create_cicd():
    st = '# Defines basic CICD settings for the %s service\n\nmicroservice:\n' % args.service
    for ms in args.microservices:
        st += '  %s:\n    build:\n      url: BUILD URL HERE...\n      params: BUILD PARAMETERS HERE...\n\n    ' \
              'deploy:\n      url: DEPLOY URL HERE...\n      params: DEPLOY PARAMETERS HERE...\n\n' % ms
    st += 'git_repo: %s\n\npersistent_branches: PERSISTENT BRANCHES HERE...' % args.service
    return st


# config.yaml setup
def create_config():
    st = 'microservices:\n'
    for ms in args.microservices:
        st += '  %s:\n    us-east-1:\n      dev:\n      qa:\n      prod:\n' % ms
    return st


# Service params.json file setup
def create_params_json():
    st = '[\n'
    for ms in args.microservices:
        st += '  {\n    "ParameterKey":\n    ' \
           '"ParameterValue": "{{microservices[\'%s\'][region][accounts[profile]]}}"\n  },\n' % ms
        st = st[:-2] + '\n]'
    return st


# Service stack.yaml setup
def create_stack_yaml():
    st = 'Description: Stack for %s microservices\n\n' % args.service
    st += 'Conditions:\n\nParameters:\n\nResources:\n\n'
    return st

group_id = gl.groups.search('SR')[0].id
project = ''

try:
    if gl.projects.get('SR/%s' % args.service):
        print '-------------------------------------------------------------------------------------'
        print 'ATTENTION: SR/%s already exists. Adding missing sample Phoenix files...' % args.service
        print '-------------------------------------------------------------------------------------'
        project = gl.projects.get('SR/%s' % args.service)
except gitlab.exceptions.GitlabGetError:
    print '-------------------------------------------------------------------------------------'
    print 'Creating Sample Phoenix Repo For SR/%s ...' % args.service
    print '-------------------------------------------------------------------------------------'
    project = gl.projects.create({'name': args.service, 'namespace_id': group_id})

try:
    read_me = project.files.create({'file_path': 'README.md',
                                    'branch_name': 'master',
                                    'commit_message': 'Create sample README.md',
                                    'content':
                                        '# %s\nInsert READ_ME information here...' % args.service.title()})
    print '[%s] \'README.md\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s] \'README.md\' already exists and will not be created...' % args.service

try:
    git_ignore = project.files.create({'file_path': '.gitignore',
                                       'branch_name': 'master',
                                       'commit_message': 'Create sample .gitignore',
                                       'content':
                                           '.idea/\n'
                                           'gradle/\n'
                                           'gradlew\n'
                                           'gradlew.bat\n'
                                           'apiDoc/\n'
                                           'classes/\n'
                                           'build/\n'
                                           'gradle_graphs/\n'
                                           'target/\n'
                                           'out/\n'
                                           'output/\n'
                                           '.gradle/\n'
                                           '.idea/\n'
                                           'logs/\n'
                                           '*.iml\n'
                                           '*.iws\n'
                                           '*.ipr\n'
                                           '*.class\n'
                                           '*.dll\n'
                                           '*.so\n'
                                           '*.exe\n'
                                           '*.o\n'
                                           '*.pyc\n'
                                           '*.cache\n'
                                           '.DS_Store\n'})
    print '[%s] \'.gitignore\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s] \'.gitignore\' already exists and will not be created...' % args.service

try:
    build_gradle = project.files.create({'file_path': 'build.gradle',
                                         'branch_name': 'master',
                                         'commit_message': 'Create sample build.gradle',
                                         'content':
                                             '//allprojects{}\n\n'
                                             '//subprojects{}\n\n//Include dependencies/repos/other info here...'})
    print '[%s] \'build.gradle\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s] \'build.gradle\' already exists and will not be created...' % args.service

try:
    settings_gradle = project.files.create({'file_path': 'settings.gradle',
                                            'branch_name': 'master',
                                            'commit_message': 'Create sample settings.gradle',
                                            'content':
                                                'rootProject.name = \'%s\'\n//Includes here..\n\n'
                                                '//Project microservice name alias here..' % args.service})
    print '[%s] \'settings.gradle\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s] \'settings.gradle\' already exists and will not be created...' % args.service

try:
    cicd_yaml = project.files.create({'file_path': 'infra/CICD.yaml',
                                      'branch_name': 'master',
                                      'commit_message': 'Create sample infra/CICD.yaml file',
                                      'content': create_cicd()})
    print '[%s/infra] \'CICD.yaml\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s/infra] \'CICD.yaml\' already exists and will not be created...' % args.service

try:
    config_yaml = project.files.create({'file_path': 'infra/config.yaml',
                                        'branch_name': 'master',
                                        'commit_message': 'Create sample infra/config.yaml file',
                                        'content': create_config()})
    print '[%s/infra] \'config.yaml\' was created...' % args.service
except gitlab.exceptions.GitlabCreateError:
    print '[%s/infra] \'config.yaml\' already exists and will not be created...' % args.service

try:
    params_json = project.files.create({'file_path': 'infra/%s.params.json' % args.service,
                                        'branch_name': 'master',
                                        'commit_message': 'Create sample infra/%s/params.json file' % args.service,
                                        'content': create_params_json()})
    print '[%s/infra] \'%s.params.json\' was created...' % (args.service, args.service)
except gitlab.exceptions.GitlabCreateError:
    print '[%s/infra] \'%s.params.json\' already exists and will not be created...' % (args.service, args.service)

try:
    stack_yaml = project.files.create({'file_path': 'infra/%s.stack.yaml' % args.service,
                                       'branch_name': 'master',
                                       'commit_message': 'Create sample infra/%s/stack.yaml file' % args.service,
                                       'content': create_stack_yaml()})
    print '[%s/infra] \'%s.stack.yaml\' was created...' % (args.service, args.service)
except gitlab.exceptions.GitlabCreateError:
    print '[%s/infra] \'%s.stack.yaml\' already exists and will not be created...' % (args.service, args.service)

if args.microservices:
    for microservice in args.microservices:
        try:
            ms_gradle = project.files.create({'file_path': '%s/build.gradle' % microservice,
                                              'branch_name': 'master',
                                              'commit_message': 'Create build.gradle for %s/%s' %
                                                                (args.service, microservice),
                                              'content':
                                                  '//Plug-Ins, Dependencies, Tasks here...'})
            print '[%s/%s] \'build.gradle\' was created...' % (args.service, microservice)
        except gitlab.exceptions.GitlabCreateError:
            print '[%s/%s] \'build.gradle\' already exists and will not be created...' % (args.service, microservice)
