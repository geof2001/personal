elastic_plugin
---------------

To use (with caution), simply do::

    >>> from elastic_plugin import ElasticQuery
    >>> es = ElasticQuery(host="host.elastic.search.com")
    >>> es.get_latest_deployed_build(service="homescreen",env="prod",region="us-east-1")

API
---------------

=====================================================
get_build_history(service=None,branch=None,size=None)
=====================================================
`api build history information`

:service: name of service (e.g homescreen, search etc)
:branch: on which branch main or custom branch)
:size:   no of build
:return: list of builds


=================================
get_build_info(build_name=None):
=================================
`api for getting build info.`

:build_name: name of the build.
:return: list,build information list.


==============================================================================
get_deploy_history(region=None,env=None,service=None,changeset="false",size=1)
==============================================================================

`api for getting build deploy history.`

:param region: region (us-east-1,us-west-2)
:param env: on which environment (qa,dev,prod).
:param service: service name (homescreen, bifservice)
:param size: no of deployment.
:return: list

=============================================================================
get_latest_build(service=None, branch=None)
=============================================================================


=============================================================================
get_latest_deployed_build(service=None,env=None,region=None)
=============================================================================


=============================================================================
get_last_deploy_git_checkin(service=None,env=None,region=None)
=============================================================================

=============================================================================
get_test_history(service=None,env=None,size=1)
=============================================================================

=============================================================================
get_latest_test_status(service=None,env=None,size=1)
=============================================================================

=============================================================================
get_last_test_failed(service=None,env=None,size=1)
=============================================================================

=============================================================================
get_deployed_build_test_status(service=None,env=None,region=None)
=============================================================================
