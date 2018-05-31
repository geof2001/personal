Infra team scripts

# bud2 
    This tool will be deprecated on 7/31/2018
    Tool used for building and deploying phoenix compliant services.
    
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
    (--commit-message) - Optional commit message when updating config.yaml file.

    ---------------------------------------------------------------------------------------------------
    This will give you the latest info of the service(s) from Jenkins and the YAML file...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed

    ---------------------------------------------------------------------------------------------------
    You can input multiple service(s) as a command to gather info, build, update, deploy...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed myfeed/myfeed-contenteventcreator recsys/client

    ---------------------------------------------------------------------------------------------------
    This will do the traditional build, update, and deploy of the service(s)...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed recsys/recsys-api --build --envs dev qa --update --deploy

    ---------------------------------------------------------------------------------------------------
    Without the update flag (--update)(-u), calling deploy will just deploy whats currently on the config file...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed --envs dev qa --deploy

    ---------------------------------------------------------------------------------------------------
    You can input build numbers [AFTER] service names to update, deploy with that specific build #...
    (No number after defaults as the latest build of that service)
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed 1238 recsys/recsys-api 384 --envs dev qa --update --deploy

    ---------------------------------------------------------------------------------------------------
    This will take the latest existing Jenkins build of myfeed/api, update the YAML file, and deploy...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed --envs dev qa --update --deploy

    ---------------------------------------------------------------------------------------------------
    You can choose to build/deploy certain services by putting their names after their respective flags...
    By disregarding this, all services inputted will be built/deployed...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed recsys/recsys-api --build myfeed/api --envs dev qa --update --deploy

    (This will build myfeed/api only, but deploy both myfeed/api and recsys/client with their latest builds)

    ---------------------------------------------------------------------------------------------------
    You can deploy to specific regions with the --regions flag, note that default will be us-east-1 only...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed recsys/recsys-api --build --envs dev qa --update --deploy --regions us-east-1 eu-west-1

    ---------------------------------------------------------------------------------------------------
    If regression/smoke tests are setup and put on the CICD.yaml file, you can use run them through bud2
    as well with the flags --regression and/or --smoke...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed --envs dev qa --update --deploy --smoke

    ---------------------------------------------------------------------------------------------------
    To create a changeset when deploying, use the --changeset (-c) flag...
    ---------------------------------------------------------------------------------------------------

    ./bud2 myfeed/myfeed --envs dev qa --update --deploy --changeset

    ---------------------------------------------------------------------------------------------------
    
# elbv2pri
    
Tool used to list the priorities of application load balancers in a region/account or by specifying an explicity name of a ALB.
    
    usage: elbv2_priorities.py [-h] [--profile] [--region] [--arn] [--name]

    Shows the priorities of ELBV2 Listeners

    optional arguments:
      -h, --help       show this help message and exit
      --profile , -p   AWS Profile to use
      --region , -r    AWS Region to get listeners from
      --arn , -a       ELBV2 Arn that you want to get priorities for
      --name , -n      Name of ELBV2 you want to list priorities for
      
# pull

This tool lets you easily pull all or some of your cloned repositories in your $GITPATH

    Pull all, one or some of your cloned repo's with this command.

    ./pull
      -h --help			# shows this message
      --gitpath /git		# override your $GITPATH
      -s --status repo		# show status of the given repository
      repo1 repo2		# pull just the repo(s) specified
      all 			# To pull all repo's in your $GITPATH
      
# slacker

usage: slacker [-h] [-u] [-c] [-t] [-s]

CLI Slack client for issuing test commands or sending messages to a channel

    optional arguments:
    -h, --help  show this help message and exit
    -u          Slack User ID, @username or user@roku.com
    -c          Slack channel ID or #channel-name to post to.
    -t          If you are simply posting to a channel
                  provide text in quotes here.  If you are issuing a
                  command with -s then provide the parameters to
                  your /command here.
    -s          Slack slash command you want to run.
                  Make sure to prefix it with a '/'.

    Posting a comment to a channel:
            ./slacker -u @jscott -c sr-all -t "Hi everyone!"

    Run a command with parameters in a channel:
            ./slacker -u @jscott -c #sr-programming -s /bud -t "deploy help"
      
