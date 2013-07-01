# Folsom -> Grizzly Upgrade

Updating a cluster from Folsom to Grizzly has some issues.  Lack of
versionized RPC and direct database access require that the entire
cluster be upgraded as a single unit.

From Grizzly to Havana, the situation will likely be different.  RPC
versions have been introduced, all DB access is now done through the
nova conductor service, so it possible that the Havana upgrade will be
able to be performed as a rolling upgrade rather than an
all-or-nothing upgrade.

But that's vapor, and the problem in front of us is Folsom to Grizzly.

Thanks to the hard work of Canonical's OpenStack packaging team, and
the magic of Chef, much of the hard work of doing an upgrade from
Folsom to Grizzly can be automated (assuming a deployment on Ubuntu
12.04 using the RCBOps chef cookbooks).

Our general strategy will be this:

* Stop chef-client on all of the nodes to ensure ordering
* Upload the new grizzly cookbooks
* Update the environment to indicate that upgrade should be performed
* Stop all openstack services on secondary infrastructure nodes if applicable.
* Run chef client on the infra nodes
* Run chef client on the compute nodes

There are some general notes and caveats:

* Upgrading keystone will make it not work until 2013.1.1 makes it
  into the ubuntu cloud archive repository
  (https://bugs.launchpad.net/keystone/+bug/1167421)
* Issues with image uploading requires that glance image uploading be
  disabled in the chef cookbooks

## Step 1

Checkout (or switch branches) the rcbops grizzly cookbooks:

~~~~
    /root# git clone https://github.com/rcbops/chef-cookbooks
    /root# cd chef-cookbooks
    /root/chef-cookbooks# git checkout v4.0.0
    /root/chef-cookbooks# git submodule init
    /root/chef-cookbooks# git submodule update
~~~~

With the grizzly cookbooks checked out, upload the cookbooks and roles
to the chef server:

~~~~
    /root/chef-cookbooks# knife cookbook upload -a -o cookbooks
       ... uploadage snipped ...
    /root/chef-cookbooks# knife role from file roles/*rb
       ... roleage snipped ...
~~~~


## Step 2

Update the environment in question.  Forcing the package upgrades can
be done by setting the osops/do_package_upgrades boolean to true:

~~~~
    "override_attributes": {
      "osops": {
        "do_package_upgrades": true
      },
      ....
~~~~

This will cause packages to be updated after the grizzly package
repository is added.

There have been issues with image uploading as well.  It might be
worth disabling image uploads:

~~~~
    "override_attributes": {
      "glance": {
        "image_upload": false
      },
      ...
~~~~

## Step 3

In the case of HA infra nodes, first stop all openstack services running on the secondary node, beginning with monit.  
monit, keystone, nova, glance, cinder, haproxy, and keepalived should all be stopped.  

Run chef client on the primary infrastructure node, followed by any secondary nodes if applicable.

Caveat:

Until keystone >= 2013.1.1 is uploaded into the ubuntu cloud archive
repository, upgrading glance may cause users and tenants to be
disabled.

These tenants and users must be re-enabled manually.  Assuming no
tenants or users were disabled before the migration, they can be
re-enabled en masse using the mysql command-line utility:

~~~~
    /root# mysql -u keystone -p keystone -e "update user set enabled=1"
    /root# mysql -u keystone -p keystone -e "update project set enabled=1"
~~~~

You can find the keystone db password in the node attributes of the
keystone server in keystone/db/password.

## Step 4

Now, run chef-client on each of the compute nodes, either serially or
in parallel.

## Step 5

There is no step 5!
