#!/usr/local/bin/python
from __future__ import print_function
import ConfigParser
import argparse
import json
import hashlib
import cPickle as pickle
import os
import os.path
import sys
# from time import sleep
from multiprocessing import Process

try:
    import ruamel.yaml as yaml
except ImportError:
    sys.exit("Missing python module ruamel.yaml.\n  Please run"
             "'sudo pip install ruamel.yaml'")
from ruamel.yaml import RoundTripLoader, RoundTripDumper

try:
    from datadog import initialize, api
except ImportError:
    sys.exit("You need datadog's python module!\ninstall it from"
             "http://pypi.python.org/pypi/datadog\nor run sudo pip"
             "install datadog.")


DEFAULT_REGION = "us-east-1"
WILDCARD_CHAR = "*"
DDTOOLS_CFGPATH = os.path.expanduser('~') + "/.ddtools"
CHANGES = {}

def timed_function(func, args, kwargs, time):
    """
      Passed function will be started as a separate thread
      and timed out if threshold exceeded.
    """
    proc = Process(target=func, args=args, kwargs=kwargs)
    proc.start()
    proc.join(time)
    if proc.is_alive():
        proc.terminate()
        return False
    return True

def construct_yaml_str(self, node):
    """ load yaml as utf-8 """
    return self.construct_scalar(node)

if os.name == "nt":
    RoundTripLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
    # Forcing unicode only works on windows and is required for hashes to work otherwise
    # it thinks there is always a change.  If on linux this doesn't seem to be an issue.

def setup(section):
    """
    Store and save credentials in users home folder as
    .ddtools/creds
    """
    config = ConfigParser.SafeConfigParser()
    if os.path.exists(DDTOOLS_CFGPATH + '/creds'):
        print ("Reading from configuration file")
        cfgfile = DDTOOLS_CFGPATH + '/creds'
        config.read(cfgfile)
    else:
        print ("You have no credentials configured for this tool.  You will need \n"
               "to provide an API key and an Application key from the datadog \n"
               "console.")
        if not os.path.exists(DDTOOLS_CFGPATH):
            os.makedirs(DDTOOLS_CFGPATH)
        cfgfile = DDTOOLS_CFGPATH + '/creds'
    if config.has_section(section):
        print ("This section already exists.")
        print (config.items(section))
        overwrite = raw_input("Overwrite? (Y/N): ")
        if overwrite.lower() == "y":
            print("Overwriting.")
            apikey = raw_input("API key: ")
            appkey = raw_input("Application key: ")
            if apikey == '' or appkey == '':
                print("Key values can not be empty.")
                raise SystemExit
            config.set(section, 'apikey', apikey)
            config.set(section, 'appkey', appkey)
            with open(cfgfile, 'wb') as configfile:
                config.write(configfile)
        else:
            print("You chose not to overwrite the existing values... exiting")
            raise SystemExit

    else:
        config.add_section(section)
        apikey = raw_input("API key: ")
        appkey = raw_input("Application key: ")
        if apikey == '' or appkey == '':
            print("Keys values can not be empty.")
            raise SystemExit
        config.set(section, 'apikey', apikey)
        config.set(section, 'appkey', appkey)
        with open(cfgfile, 'wb') as configfile:
            config.write(configfile)

def dd_initialize(profile):
    """
    Initialize datadog api connection using API and
    Integration token from credentials stored.
    """
    result = "Initializing api connection to profile: " + profile
    parser = ConfigParser.SafeConfigParser()
    parser.read(DDTOOLS_CFGPATH + '/creds')
    options = {
        'api_key': parser.get(profile, 'apikey'),
        'app_key': parser.get(profile, 'appkey')
    }
    initialize(**options)
    return result

def dd_list(args):
    """ Return monitor/timeboard for display. """
    dd_initialize(args.profile)
    if args.objectType == "monitors":
        result = api.Monitor.get_all(name=args.stringMatch)
        scrub_monitor(result)    # strip unwanted elements
    elif args.objectType == "timeboards" and args.stringMatch:
        if args.stringMatch.isdigit():
            print ("You want a specific timeboard with ID: %s" % (args.stringMatch))
            result = api.Timeboard.get(args.stringMatch)
        else:
            result = ("You must supply the ID of a timeboard.")
    elif args.objectType == "timeboards":
        boards = api.Timeboard.get_all()
        detailedBoards = {}
        # dirtyBoards = {}
        for element in boards:
            # print (boards[element])
            for dash in boards[element]:
                board = api.Timeboard.get(dash['id'])
                # dirtyBoards.update(board)
                detailedBoards.update(scrub_dashboard(board))
        # result = dirtyBoards
        result = detailedBoards
    else:
        result = ("You didn't specify whether you want to list monitors or"
                  "timeboards.  Try list --help")
    return result

def scrub_monitor(data_blob):
    """ Remove unused elements from monitor before display or saving to file. """
    remove_items = {'created_at', 'org_id', 'modified',
                    'created', 'deleted', 'creator', 'overall_state_modified',
                    'overall_state', 'matching_downtimes'}
    # print("Class type of blob is: %s" % (data_blob.__class__.__name__))
    # print("Blob is: %s" % (data_blob))
    for element in data_blob:
        try:
            del element['options']['locked']
        #     del element['options']['notify_audit']
        except KeyError:
            continue
        for item in remove_items:
            del element[item]
    return data_blob

def scrub_dashboard(data_blob):
    """ Remove used elements from Dashboard for display or saving to file. """
    # remove_items = {'created', 'modified', 'read_only', 'graphs', 'description', 'id', 'template_variables'}
    remove_items = {'created', 'modified'}
    # print ("Dashboard scrubber object pre-clean: %s" % (data_blob))
    for dash in data_blob:
        if dash == "dash":
            dash_id = "dash_" + str(data_blob[dash]['id'])
            # print (dashId)
            data_blob[dash_id] = data_blob.pop(dash)
            for item in remove_items:
                if item in data_blob[dash_id]:
                    del data_blob[dash_id][item]
            # print (data_blob[dash]['title'])
    del data_blob['url']
    del data_blob['resource']
    # scrubbed_board = yaml.dump(data_blob, Dumper=yaml.RoundTripDumper)
    # print ("Dashboard scrubbed object \n %s \n" % (scrubbed_board))
    return data_blob

def deprecated_save_to_yaml(args):
    """ Fetch monitors from datadog api and store in a file. """
    dd_initialize(args.profile)
    data = api.Monitor.get_all(name=args.stringMatch)
    clean_data = scrub_monitor(data)
    if args.stringMatch:
        filename = ("ddf_" + args.objectType + "_" + args.profile + "_" +
                    args.stringMatch.replace(" ", "_").replace(":", "") + ".yaml")
    else:
        filename = "ddf_" + args.objectType + "_" + args.profile + ".yaml"
    savefile = open(filename, 'wb')
    savefile.write(yaml.dump(clean_data, Dumper=yaml.RoundTripDumper))
    # savefile.close
    return filename

def save_object(data, args):
    """ Save objects to file.  """
    if args.objectType == "timeboards" and args.stringMatch:
        filename = "ddf_" + args.objectType + "_" + args.profile + "_" + args.stringMatch + ".yaml"
    elif args.objectType == "timeboards":
        filename = "ddf_" + args.objectType + "_" + args.profile + ".yaml"
    elif args.objectType == "monitors":
        if args.stringMatch:
            filename = ("ddf_" + args.objectType + "_" + args.profile + "_" +
                        args.stringMatch.replace(" ", "_").replace(":", "") + ".yaml")
        else:
            filename = "ddf_" + args.objectType + "_" + args.profile + ".yaml"
    else:
        print ("What are you trying to save?  Try using --help.")
    savefile = open(filename, 'wb')
    savefile.write(yaml.dump(data, Dumper=yaml.RoundTripDumper))
    return filename

def get_hash(obj):
    """ Return md5 hash of object for comparison """
    data_obj = pickle.dumps(obj)
    # print("See my pickle? ", data_obj)
    obj_hash = hashlib.md5(data_obj).hexdigest()
    return obj_hash

def dict_compare(dict1, dict2):
    """
    Returns dict with one key/value of {"match": "True"} if all key/value pairs in dict2
    match what is in dict1.  Otherwise returns dict with key/value of
    {"match": "true", {"changes": []}} with a list of changes.

    This function is not complete for timeboards as current direction indicated to me 
    seems to be that it is not necessary.  Will come back to this at a later time.
    """
    global CHANGES
    result = {'update': False}
    # print ("Dict1 Type: %s" % (dict1.__class__.__name__))
    # print ("Dict2 Type: %s" % (dict2.__class__.__name__))
    # print ("Dict1: ", dict1, "\nDict2: ", dict2)
    for key, value in dict1.items():
        if value.__class__.__name__ == "dict":
            dict_compare(dict1[key], dict2[key])
        elif value.__class__.__name__ == "list":
            if key == "graphs":
                graphs_hash_list1 = []
                graphs_hash_list2 = []
                for item in dict1[key]:
                    condensed = str(item).replace(' ', '')
                    graphs_hash_list1.append(get_hash(condensed))
                print ("\n")
                for item in dict2[key]:
                    condensed = str(item).replace(' ', '')
                    graphs_hash_list2.append(get_hash(condensed))
                print (yaml.dump(graphs_hash_list1))
                print (yaml.dump(graphs_hash_list2))
                for obj in range(0, len(graphs_hash_list1)):
                    if str(graphs_hash_list1[obj]) == str(graphs_hash_list2[obj]):
                        print ("Hash Match", obj)
                    else:
                        result['update'] = True
                        # print ("No Match", obj, dict1[key][obj], "\n", dict2[key][obj])
                        CHANGES.update({
                            "Stored_Graph": dict1[key][obj],
                            "Deployed_Graph": dict2[key][obj]
                            })
                        result.update(CHANGES)
            if key == "template_variables":
                tv_hash_list1 = []
                tv_hash_list2 = []
                for item in dict1[key]:
                    condensed = str(item).replace(' ', '')
                    tv_hash_list1.append(get_hash(condensed))
                for item in dict2[key]:
                    condensed = str(item).replace(' ', '')
                    tv_hash_list2.append(get_hash(condensed))
                print (tv_hash_list1)
                print (tv_hash_list2)
        else:
            # print ("Key Dict1: %s , Value Dict1: %s , Type Dict1: %s"
            #        % (key, value, value.__class__.__name__))
            hash_value_1 = get_hash(value)
            hash_value_2 = get_hash(dict2[key])
            # print ("Dict1 Hash for %s: %s " % (key, hash_value_1))
            # print ("Key Dict2: %s , Value Dict2: %s , Type Dict2: %s"
            #        % (key, dict2[key], value.__class__.__name__))
            # print ("Dict2 Hash for %s: %s \n" % (key, hash_value_2))
            if hash_value_1 != hash_value_2:
                result['update'] = True
                old_key = "Old_" + key
                new_key = "New_" + key
                old_value = dict2[key]
                new_value = dict1[key]
                CHANGES.update({old_key: old_value, new_key: new_value})
                # result[kname]["old_value"] = old_value
                # result[kname]["new_value"] = new_value
                result.update(CHANGES)
            print (result)
    return result

def deprecated_monitor_hash_check(configobj, deployobj):
    """ Check hash for Name and Query strings to see if update or skip """
    # print ("Config object: %s" % (configobj))
    # print ("Deploy object: %s" % (deployobj))
    # sleep(30)
    confignamehash = get_hash(configobj['name'])
    deploynamehash = get_hash(deployobj['name'])
    configqueryhash = get_hash(str(configobj['query']))
    deployqueryhash = get_hash(str(deployobj['query']))
    configmessagehash = get_hash(configobj['message'])
    deploymessagehash = get_hash(deployobj['message'])
    # configoptionshash = get_hash(configobj['options'])
    # deployoptionshash = get_hash(deployobj['options'])

    # print ("config options:\n %s\ndeploy options:\n %s" % (configobj['options'], deployobj['options']))
    # print ("config options hash:\n %s\ndeploy options hash:\n %s" % (configoptionshash, deployoptionshash))
    updateobj = False

    if confignamehash != deploynamehash:
        updateobj = True
        print ("Name from config: %s\nHash: %s" % (configobj['name'], confignamehash))
        print ("Name from deploy: %s\nHash: %s" % (deployobj['name'], deploynamehash))
    if configqueryhash != deployqueryhash:
        updateobj = True
        print ("Query from config: %s\nHash: %s" % (configobj['query'], configqueryhash))
        print ("Query from deploy: %s\nHash: %s" % (deployobj['query'], deployqueryhash))
    if configmessagehash != deploymessagehash:
        updateobj = True
        print ("Message from config: %s\nHash: %s" % (configobj['message'], configmessagehash))
        print ("Message from deploy: %s\nHash: %s" % (deployobj['message'], deploymessagehash))
    return updateobj

def dd_deploy(args):
    """
    Main deploy argument function where we decide if we are creating
    a new monitor or updating an existing monitor.
    """
    global CHANGES
    dd_initialize(args.profile)
    # with open('environments.yaml') as env_dict:
    #     env_dict_obj = yaml.load(env_dict, Loader=RoundTripLoader)
    if args.objectType.lower() == "monitors":
        with open(args.yamlFile) as data:
            data_obj = yaml.load(data, Loader=RoundTripLoader)
            data_obj = scrub_monitor(data_obj)
        api_result = {}
        for key in data_obj:
            key_monitor = build_monitor(key, args.environment.upper())
            deploy_name = key_monitor['name']
            deploy_tags = key_monitor['tags']
            deploy_type = key_monitor['type']
            deploy_query = key_monitor['query']
            deploy_message = key_monitor['message']
            deploy_options = key_monitor['options']

            api_obj = scrub_monitor(api.Monitor.get_all(name=deploy_name))
            print ("\nChecking if updated required for : %s" % (deploy_name))
            CHANGES = {}
            if api_obj:
                changeresult = dict_compare(key_monitor, api_obj[0])
                updatemonitor = changeresult['update']
                print ("Decide to update was: %s" % (updatemonitor))
                if not updatemonitor:
                    print ("Monitor exists and requires no update:\n%s\n" % (deploy_name))
                    api_result[deploy_name] = "Skipped"
                else:
                    print ("Update required for monitor:\n%s\n" % (deploy_name))
                    print (json.dumps(CHANGES, indent=4, sort_keys=True))
                    deploy_id = api_obj[0]['id']
                    if args.forceupdate:
                        update_result = api.Monitor.update(deploy_id, query=deploy_query,
                                                           name=deploy_name, message=deploy_message,
                                                           options=deploy_options)
                        print ("Result from api:\n%s\n" % (update_result))
                        api_result[deploy_name] = "Updated"
                    else:
                        print ("Specify --forceupdate if want to deploy the changes")
                        api_result[deploy_name] = "Update required, Skipped"
            else:
                try:
                    print("Creating monitor:\n%s" % (deploy_name))
                    mon_result = api.Monitor.create(
                        type=deploy_type,
                        query=deploy_query,
                        name=deploy_name,
                        message=deploy_message,
                        tags=deploy_tags,
                        options=deploy_options
                        )
                    api_result[deploy_name] = "Created"
                except Exception as e:
                    print ("Monitor %s couldn't be created for some reason: %s\n"
                           % (deploy_name, e))
                    api_result[deploy_name] = "Errored"
                    continue
                print("Created monitor with ID: %s\n" % (mon_result['id']))
        return api_result
    elif args.objectType.lower() == "timeboards":
        dd_initialize("srmain")
        with open(args.yamlFile) as data:
            data_obj = yaml.load(data, Loader=yaml.Loader)
            # print (json.dumps(data_obj['dash']['title'], indent=4), "\n",
            #        json.dumps(data_obj['dash']['id'], indent=4))
        api_result = {}
        # print (len(data_obj))
        for key in data_obj:
            if "dash" in key:
                # print ("\n", key)

                dash_title = data_obj[key]['title']
                # print (dash_title)

                dash_desc = data_obj[key]['description']
                # print (dash_desc)

                try:
                    dash_read_only = data_obj[key]['read_only']
                except:
                    dash_read_only = False
                # print (dash_read_only)

                dash_graphs = data_obj[key]['graphs']
                # print (dash_graphs)

                # try:

                if 'template_variables' in data_obj[key].keys():
                    dash_tvs = data_obj[key]['template_variables']
                else:
                    dash_tvs = ''

                print (dash_tvs)
                # except:
                #     dash_tvs = ''
                #     print (dash_tvs)
                #     continue

                if dash_tvs != '':
                    print("Creating Timeboard with TVs")
                    api_result = api.Timeboard.create(
                        title=dash_title,
                        description=dash_desc,
                        graphs=dash_graphs,
                        template_variables=dash_tvs,
                        read_only=dash_read_only
                        )
                    # print (api_result)
                else:
                    print ("creating timeboard with no TVs")
                    api_result = api.Timeboard.create(
                        title=dash_title,
                        description=dash_desc,
                        graphs=dash_graphs,
                        read_only=dash_read_only
                        )
                    print (api_result)
                # if data_obj[key]['id']:
                #     api_obj = api.Timeboard.get(data_obj[key]['id'])
                #     CHANGES = {}
                #     changeresult = dict_compare(data_obj[key], api_obj['dash'])
                #     print (changeresult)
                # print (json.dumps(data_obj['dash'], indent=4))
        

def build_monitor(my_monitor, environment):
    """
    Build a monitor object from configuration file
    and substitution from environments.yaml file.
    """
    with open('environments.yaml') as env_dict:
        env_dict_obj = yaml.load(env_dict, Loader=RoundTripLoader)
    # print ("Environments: ", env_dict_obj['environment'][environment])

    result = {}
    for element in my_monitor:
        if element == "name":
            result[element] = env_dict_obj['environment'][environment]['name'] + my_monitor[element]
        elif element == "tags":
            tags = []
            for tag in my_monitor[element]:
                tags.append(tag.replace(
                    "ACCOUNT", str(env_dict_obj['environment'][environment]['account'])
                    )
                           )
            result[element] = tags
        elif element == "query":
            result[element] = (
                str(my_monitor[element]).replace(
                    "ACCOUNT",
                    str(env_dict_obj['environment'][environment]['account'])
                    )
            )
        elif element == "message":
            result[element] = (
                my_monitor[element] +
                env_dict_obj['environment'][environment]['notifications']
            )
        elif element == "type":
            result[element] = my_monitor[element]
        elif element == "options":
            mon_opts = {}
            for opt in my_monitor[element]:
                if opt == "thresholds":
                    mon_thresholds = {}
                    for threshold in my_monitor[element][opt]:
                        if my_monitor[element][opt][threshold].__class__.__name__ == "CommentedMap":
                            # mapvalue = my_monitor[element][opt][threshold][environment]
                            critvalue = my_monitor[element][opt]['critical'][environment]
                            mon_thresholds[threshold] = (
                                my_monitor[element][opt][threshold][environment]
                                )
                            # print("Found a map for %s and got value: %s" % (threshold, mapvalue))
                        else:
                            # print("Threshold for %s is a: %s" %
                                #   (threshold,
                                #    my_monitor[element][opt][threshold].__class__.__name__))
                            # mapvalue = my_monitor[element][opt][threshold]
                            critvalue = my_monitor[element][opt]['critical']
                            mon_thresholds[threshold] = my_monitor[element][opt][threshold]
                    mon_opts[opt] = mon_thresholds
                    my_monitor['query'] = my_monitor['query'].replace("CRITICAL", str(critvalue))
                elif opt == "silenced":
                    silenced = {}
                    mon_opts[opt] = silenced
                # elif opt == "evaluation_delay":
                #     print ("option evaluation_delay found.")
                #     mon_opts[opt] = unicode(mon_opts[opt]).encode("utf-8")
                else:
                    mon_opts[opt] = my_monitor[element][opt]
            result[element] = mon_opts
        else:
            result[element] = my_monitor[element]
    return result

def get_parser():
    """get the parsers dict"""
    parsers = {}
    parsers['super'] = argparse.ArgumentParser(
        description=("An extraction tool for Datadog Timeboards(Dashboards)"
                     "and Monitors. This tool will save your configurations"
                     " to a yaml file in your local directory."))
    parsers['super'].add_argument("--profile", type=str, nargs='?', const='main',
                                  help=("Specify the datadog profile you want to"
                                        " list from"))
    parsers['super'].set_defaults(profile='main')
    subparsers = parsers['super'].add_subparsers(help='Try commands like '
                                                 '"{name} get -h" or "{name} '
                                                 'put --help" to get each '
                                                 'sub command\'s options'
                                                 .format(name=sys.argv[0]))
    
    # Parser list action
    action = 'list'
    parsers[action] = subparsers.add_parser(action,
                                            help="List timeboards or monitors "
                                            "available for export")
    parsers[action].add_argument("objectType", type=str,
                                 help="monitors/timeboards")
    parsers[action].add_argument("stringMatch", type=str, nargs='?',
                                 help="For monitors provide a string to filter results.  "
                                 "Must match from start of string and be in \"\""
                                 " e.g. \"SR PROD:\" For timeboards use the ID of a timeboard.")
    parsers[action].set_defaults(action=action, objectType="monitors")

    # Parser save action
    action = 'save'
    parsers[action] = subparsers.add_parser(action, help="Save timeboards or monitors")
    parsers[action].add_argument("objectType", type=str, help='monitors/timeboards')
    parsers[action].add_argument('stringMatch', type=str, nargs='?',
                                 help='Provide a string to filter results. Must match'
                                 'from start of string and be in \"\"'
                                 ' e.g. \"SR PROD:\"')
    parsers[action].add_argument("--profile", type=str, nargs='?', const='main',
                                 help="Specify the datadog profile you want to save" "from")
    parsers[action].set_defaults(action=action, profile='main')

    # Parser deploy action
    action = 'deploy'
    parsers[action] = subparsers.add_parser(action,
                                            help="Deploy timeboard(s)/monitor(s) to datadog")
    parsers[action].add_argument("objectType", type=str, help='monitors/timeboards')
    parsers[action].add_argument("environment", type=str,
                                 help=("Which environment are you deploying to.\n"
                                       "e.g. PROD, QA, DEV"))
    parsers[action].add_argument("yamlFile", type=str,
                                 help="The name of the yaml file to deploy")
    parsers[action].add_argument("--forceupdate", action='store_true',
                                 help="Force an update if deployed doesn't match config file."
                                 "  Otherwise just report the changes")
    parsers[action].set_defaults(action=action)


    # Parser setup action
    action = 'setup'
    parsers[action] = subparsers.add_parser(action,
                                            help='setup datadog credentials.')
    parsers[action].add_argument("section", type=str, nargs='?',
                                 help="specify a new section if not setting up the default.")
    parsers[action].set_defaults(section='main', action=action)
    return parsers

def main():
    """
       Main function where we do something with the arguments provided.
    """
    parsers = get_parser()
    args = parsers['super'].parse_args()

    if "action" in vars(args):

        if args.action == "list":
            print(args)
            if args.objectType == "monitors":
                result = dd_list(args)
                # scrubbed_result = scrub_monitor(result)
                # print(json.dumps(scrubbed_result))
                print (yaml.dump(result, Dumper=yaml.RoundTripDumper))
            elif args.objectType == "timeboards" and args.stringMatch:
                result = dd_list(args)
                print (yaml.dump(result, Dumper=yaml.RoundTripDumper))
            elif args.objectType == "timeboards":
                print("You are requesting all timeboards.  This can take a while.")
                result = dd_list(args)
                print (yaml.dump(result, Dumper=yaml.RoundTripDumper))
            else:
                print ("Not sure what to do here.  Try adding --help to your command.")
            return

        if args.action == "deploy":
            print ("Deploying %s" % (args.yamlFile))
            result = dd_deploy(args)
            print ("\nLast status from deploy was:\n%s" % (yaml.dump(result, Dumper=yaml.RoundTripDumper)))
            return

        if args.action == "save":
            if args.objectType == "timeboards" and args.stringMatch:
                print("Saving timeboard with ID: %s." % (args.stringMatch))
                boards = dd_list(args)
                result = save_object(boards, args)
            elif args.objectType == "timeboards":
                print("Saving all timeboards.  This can take a minute...")
                boards = dd_list(args)
                result = save_object(boards, args)
            else:
                print ("Saving monitors.")
                monitors = dd_list(args)
                result = save_object(monitors, args)
            print ("Saved your %s in %s" % (args.objectType, result))
            return

        if args.action == "setup":
            print(args)
            setup(args.section)
            return

    else:
        parsers['super'].print_help()

if __name__ == '__main__':
    main()
