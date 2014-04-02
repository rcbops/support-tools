Tools used for in POST deployment
#################################
:date: 2014-04-02
:tags: rackspace, private cloud, qc
:category: \*nix


The tools within this directory were created to allow you to more rapidly 
ensure that the deployment is setup and working as expected. 

Tools
-----

*   ``keystone_user_create.sh``

    This tool was created to allow you to create users, tenants and roles for a 
    new deployment more rapidly
    
    Usage: 
    
    .. code-block:: bash
    
        export USER_NAME="new_user_name"
        export TENANT_NAME="new_tenant_name"
        export ROLE_NAME="new_role_name"
        
        bash keystone_user_create.sh

 
    When running the script, if a role is set that does not exist it will be created. 
    the script assumes that you have no conflicting usernames, tenant names, or role 
    names. When the script has completed an openrc-customer-$NAME will be saved in the
    current working directory. 
    
*   ``neutron_network_test.sh``

    This tool was created to allow you to test that all of the created neutron networks
    working as expected.  This is a test script that will build 1 instance per network 
    and will then attempt to ping the network gateway from within the network namespace
    of the neutron network. When the script is complete, the built instance(s) will be 
    removed. All output for the scirpt is printed to stdout in a human readable format.
    
    Usage: 
    
    .. code-block:: bash
    
        bash neutron_network_test.sh
