INTRODUCTION
============
Script that does a diff against the input YAML file with existing Datadog monitors for a service and creates/updates accordingly 
in the targeted environment.


CONTENTS
========
- manual.txt: a list of the --help options available when calling ddtool.py -h
- ddtool.py: main tool use -h or --help for syntax
  - setup: stores datadog credentials in users home folder as .ddtools/creds
    This supports storing multiple sets of "profiles" which can be named and called
    using the --profile [profilename] option.
  - list: outputs to the screen all monitors if no filter string is given or provide a filter string
    in quotes to view a subset of monitors.  The filter string only works on the [name] of the monitor
  - save: stores all monitors or a subseet of monitors in a YAML file in the execution folder.
    e.g. python ddtool.py save "myfeed" will create a YAML file named ddf_myfeed_main.yaml
  - deploy: takes the input of a template file and generates the monitor then queries datadog for the
    name of the generated monitor if it exists.  If it does not it creates that monitor.  If it does exist
    it generates a diff against the name, query string and message block to see if there were any changes.
    If no changes detected it skips and moves to the next monitor in the template file.  If a change is
    detected it does an update of the monitor passing in the changes for query, thresholds and the message
    block.  If the name changed it will create a new monitor and for now the user is responsible for deleting
    the old monitor.
- ddf_monitors_[servicename]_template.yaml: file that contains the monitor templates for a service
- environments.yaml: a dictionary of account names, the account numbers and notification strings


RUN SCRIPT
==========
To setup your credentials for first time use get your API and Application ready from the Datadog portal.
By default if no profile name is supplied it will be stored as 'main'.
- python ddtool.py setup

To add a new set of credentials and store them as a different profile:
- python ddtooly.py setup newprofilename
   
To create/update monitors:
- python ddtool.py deploy [ENVIRONMENT] ddf_monitors_[servicename]_template.yaml

Get all existing datadog monitors that contain the string "PROD" in the name into ddf_monitors_main_PROD.yaml
- python ddtool.py save monitors "PROD"

Get all exisiting datadog monitors into ddf_monitors_main.yaml
- python ddtool.py save monitors

List monitors to your screen
- python ddtool.py list "PROD all aws.dynamodb.write"
Jenkins job for Datadog: https://jenkinscd.tools.sr.roku.com/job/sr-zoo-datadog/

**YAML files contain monitors**

BETA
=====
- Currently deleting monitors if name changed is not supported but enable creating and updating
- Monitors support differing thresholds by account to support monitor testing within accounts other than PROD
- ddtool.py has a setup function to store API/Integration keys in users home folder under .ddtools/creds
- ddtool.py can be used to list monitors, save them to a YAML file and deploy(create/update) monitors
- run ddtool.py -h or --help for 

Features
============
- Create all monitor in YAML that are in YAML file
- Update all current monitors to the parameters specified in YAML file
- Mark for delete the older version of monitors **FUTURE**

REQUIREMENTS
============
- If running locally you need to run setup once and provide an API and Application key
  You can get these on the datadog portal under Integrations > APIs
- A YAML file with completed parameters

TROUBLESHOOTING
===============
- If you get unforeseen errors please open a request and I'll take a look at it.


FUTURE
==============
- Scan for services that have no monitors deployed for staging and production.
- Fail a monitor or ignore a monitor that has no recipients?

