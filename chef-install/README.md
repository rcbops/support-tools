README
======


These are utilities for installing a chef server against rcbops
OpenStack cookbooks.  They may be useful in some other context as
well.  You break it, you bought it.  Objects in mirror may be closer
than they appear.  Significant settling may occur during shipping.  Etc.

install-chef-server
-------------------

This (surprisingly) installs a chef server, using the Opscode /opt
based packaging.  Distros this should work on:

* Ubuntu 12.04 (tested)
* Ubuntu > 12.04 (untested, but likely works)
* Centos 6 (tested)
* RHEL 6 (untested, but probably works)

It could almost certainly be made to work on Fedora.  I don't use
Fedora or have enough interest in fedora to suss out the right
platform detection stuff.  Patches welcome.

By default, this script installs chef 11.0.4-1 with randomly generated
passwords, and a knife config set up for the root user.

The following environment variables can control the behavior of the
installation:

* CHEF_SERVER_VERSION (defaults to 11.0.4-1)
* CHEF_URL (defaults to https://<ip of default gw iface>:443)
* CHEF_WEBUI_PASSWORD (randomly generated)
* CHEF_AMQP_PASSWORD (randomly generated)
* CHEF_POSTGRESQL_PASSWORD (randomly generated)
* CHEF_POSTGRESQL_RO_PASSWORD (randomly generated)
* CHEF_UNIX_USER (user to set up knife in (default "root"))

Of these, CHEF_SERVER_VERSION and CHEF_URL are likely the most
interesting.

You must log off and back on as the target user in order to be able to
use "knife" commands

install-cookbooks
-----------------

This appropriately named command can be used to install the rcbops
cookbooks. You should log off and back on to ensure your knife command
works, if you got to this point by running the above command.

By default, it installs and uploads the "grizzly" cookbooks to the
currently knife configured chef server. Make sure you are pointing to
the right place. This script makes no attempt to protect you from
yourself. You have been warned.

Interesting environment variables:

* COOKBOOK_BRANCH (folsom | grizzly, defaults to grizzly)
* COOKBOOK_PATH (defaults to ${HOME}/chef-cookbooks)

You probably want to make an environment at this point.

install-chef-client
-------------------

This is a bit hackish, and makes a couple of naive assumptions. It
assumes that the user you are logged in with has passwordless ssh key
auth set up (or you are willing to push the appropriate buttons when
prompted) and is sudo NOPASSWD:ALL.

This is likely not true on your systems, so perhaps this script is
more useful as an example, and not so much as The Right Way To Do It.

It also assumes that you are running the script from the chef server,
(unless CHEF_URL is overridden) as it derives the CHEF_URL the same
way it's defaulted in "install-chef-server.sh" (443 on the ip of the
same interface that the default gateway is on).

Interesting environment variables:

* CLIENT_VERSION: defaults to 11.2.0-1
* ENVIRONMENT: defaults to _default
* CHEF_URL: defaults to same as install-chef-server.sh

INSTALLING WITH RCBOPS
======================

The goal of all these scripts is to install OpenStack using the
cookbooks provided by rcbops.  They help streamline the most painful
part of the installation -- bootstrapping a configuration management
system.  In this section, a typical installation of OpenStack
"grizzly" will be detailed, with pointers to more information on
customizing or modifying your installation.


Overview
--------

As a general overview, the rcbops-opinionated grizzly install is an
installation that is configured with
[Opscode's Chef](http://www.opscode.com).  A typical install consists
of one (or two) infrastructure controllers that host central services
(rabbitmq, mysql, dashboard, web api, etc), and one or more compute
servers that spin virtual machines.  The rcbops cookbooks generally
make the following assumptions:

 * DB for all services (nova, glance, etc) are in mysql
 * HA provided by VRRP
 * Load balancing provided by haproxy
 * KVM as hypervisor
 * Networking model of nova-network in flat-ha mode (quantum available)
 * Likely other things I've forgotten

The general strategy of installation will consist of:

1. Installing chef server
2. Uploading rcbops cookbooks and roles
3. Configuring client machines to talk to chef server
4. Creating and environment that describe the grizzly cluster
5. Profit!

Installing Chef Server
----------------------

Either find a machine accessible by the remainder of the
infrastructure and compute hosts on 443 and 80 and install the
open-source Chef server bits, or use Opscode hosted chef for managing
the chef configuration.

More information on leveraging Opscode Hosted Chef can be found on the
[Opscode Hosted Chef](http://www.opscode.com/hosted-chef/) page.

Details on installing the open source Chef server can be found in the
[Opscode Documentation](http://docs.opscode.com/install_server.html).
The "install-chef-server.sh" script in this repo can also be used to
install chef server.

If installing from the Opscode, don't forget to [set up a user](http://docs.opscode.com/chef/install_workstation.html)!

Uploading cookbooks
-------------------

Once a chef server has been installed and a management workstation has
been set up, the rcbops cookbooks must be uploaded to the chef server.
You can perform this step by hand, or you can use the script provided
in this repository named "install-cookbooks.sh".

The rcbops cookbooks are set up as git submodules and are hosted at
<http://github.com/rcbops/chef-cookbooks>, with individual cookbook
repositories at <http://github.com/rcbops-cookbooks>.

To download the full suite of rcbops cookbooks, use the following git
command:

~~~~
    /root# git clone https://github.com/rcbops/chef-cookbooks
~~~~

The cookbooks are branched based on OpenStack release.  To install
grizzly, check out the grizzly branch and update submodules:

~~~~
    /root# cd chef-cookbooks
    /root/chef-cookbooks# git checkout grizzly
    /root/chef-cookbooks# git submodule init
    /root/chef-cookbooks# git submodule update
~~~~

Note also that you are welcome to fork your own cookbooks, update your
submodules and pull-request fixes or enhancements to the rcbops
cookbooks -- your contributions make the cookbooks better for
everyone.

Once you have downloaded all the cookbooks from github, they should be
uploaded to the chef server, along with the defined roles:

~~~~
    /root/chef-cookbooks# knife cookbook upload -a -o cookbooks
      ... much cookbook uploadage ...
    /root/chef-cookbooks# knife role from file roles/*rb
      ... much role creation ...
~~~~

Installing chef client
----------------------

For all the machines in your proposed OpenStack cluster, you should
install chef-client and configure them to talk to the chef server you
have uploaded cookbooks to.

If using Opscode Hosted Chef, follow the directions provided with your
hosted chef account to configure additional nodes to communicate with
your hosted chef account.

One possible way to do this might be to use the
[knife bootstrap](http://docs.opscode.com/knife_bootstrap.html)
command to bootstrap a physical machine into your chef server.

Another way might be to use the "install-chef-client.sh" script
provided in this repository.

Regardless of the method used, all machines to be part of the
OpenStack cluster must have chef-client installed and registered to
the chef server.

Creating the Environment
------------------------

This is the most difficult part of the installation.  There are many
different ways to install OpenStack, even given the assumptions and
opinions we have expressed in the cookbooks.  This means that there is
a significant amount of configuration information that must be
specified, even in a relatively "vanilla" OpenStack install.

The biggest oddness of the environment file is the network
definitions.  Our assumptions on networking for OpenStack clusters is
that the IP addresses of infrastructure are fixed, that infrastructure
machines will have multiple network interfaces so as to split
management networks from VM networks and API networks, and that bind
endpoints for services are best described by what networks they are
connected to.

In the rcbops cookbooks, there exist definitions for three general
networks. One called "nova", where internal OpenStack services bind.
These are services that are required for OpenStack operation, but are
not necessary to be accessible by VM instances. Another network,
called "public", is the network that API services bind. These services
generally need to be publicly accessible, and on a different network
than the network that nova services such as rabbitmq run. The last
network is called "management", where management services such as
monitoring and syslog forwarding communicate.

These networks are defined by the cidr range that they encompass, and
any network interface with an address in the named cidr range are
assumed to be on the named network.

Networks can be folded together by specifying the same cidr for
multiple networks.  For example, by setting the same cidr for both the
"nova" network and the "management" network, syslog and rabbitmq will
both be listening on the same network.

This can perhaps best be illustrated with an example environment.  If
one were to make an environment with the following override_attributes:

~~~~
    "override_attributes": {
        "nova": {
            "networks": [
                {
                    "label": "public",
                    "bridge_dev": "eth1",
                    "dns2": "8.8.4.4",
                    "num_networks": "1",
                    "ipv4_cidr": "192.168.222.0/24",
                    "network_size": "255",
                    "bridge": "br100",
                    "dns1": "8.8.8.8"
                }
            ]
        },
        "mysql": {
            "allow_remote_root": true,
            "root_network_acl": "%"
        },
        "osops_networks": {
            "nova": "192.168.122.0/24",
            "public": "192.168.122.0/24",
            "management": "192.168.122.0/24"
        }
    }
~~~~

This environment would create a cluster that had all three networks
folded on to one physical network.  That network would be the network
that has an ip address in the 192.168.122.0/24 range.

All internal nova services, all API endpoints, and all monitoring and
management functions would run over the 192.168.122.0/24 network.

The nova/network section would cause VMs to be brought up on a
192.168.222.0 network on eth1 brought into a bridge called "br100".
Nova would bring up the bridge and insert eth1 itself, so the host
itself could (and should) have eth1 left unconfigured.

To create a cluster with this minimal configuration, the steps
required would be to create the environment expression this
configuration, assigning roles to nodes, and running chef to converge
the cluster.

### Creating an Environment

An environment can be simply created by using the "knife environment
create" command.  To create an environment named "grizzly", execute
the command "knife environment create grizzly".  This will allow
direct editing of the environment, and give the ability to enter the
"override_attributes" specified above.

### Setting Roles and Converging Cluster

In the simplest case, using a single non-HA infrastructure node, the
roles "single-controller" can be used.  Modify the infrastructure node
in chef to add it to the "grizzly" environment, and add the
"single-controller" role to that node's run_list using either the chef
web ui or the "knife node edit" command.

Once the role and environment are set, run "chef-client" on the
infrastructure node.  It will probably take a significant amount of
time to run the client, as there are many packages, configuration
changes, and dependencies to work through.

The infrastructure node must be installed before any compute nodes are
installed, however.  Until the infrastructure node has completed its
chef run, information about endpoints will not be published back to
chef, and compute nodes will not know locate and connect to
infrastructure services.

Once the infrastructure node has completed the installation, compute
nodes can be installed.  Add the compute nodes in question to the
environment, and add the role "single-compute" to the run_list.

Multiple compute nodes can be installed in parallel.

HA Infrastructure
-----------------

The HA infrastructure role changes the single infrastructure node into
a pair of infrastructure nodes that provide HA with VRRP, monitored by
keepalived. Every major service has a VIP of its own, and services are
failed over on a service-by-service basis.

One service includes haproxy.  This is used to load-balance (for those
web services in OpenStack that can be run in an active/active
configuration) or active/passive for those that cannot.  The front-end
ip of the haproxy pair is itself a VRRP VIP.

Another service is rabbitmq.  Until version 3.1 is generally available
from distribution vendors, we will be using a VRRP for HA (but not
fault tolerance -- some messages will be lost, likely resulting in
failures of Nova API actions).  Once better mirrored queue clustering
is available in rabbitmq 3.1, we will switch to native rabbitmq
clustering for HA and fault tolerance.

The last VIPped service is MySQL.  MySQL is configured by the
cookbooks in a master/master configuration with an active/passive
non-load balanced VIP.

To set up a configuration with a HA infra node, allocate ip addresses
for the three VIPs on an interface available on both infra nodes.
Then add the appropriate environment settings in override_attributes (in
addition to those specified above):

~~~~
    "override_attributes": {
        "vips": {
            "mysql-db": "<mysql vip>",
            "rabbitmq-queue": "<rabbit vip>",
            "nova-api": "<haproxy vip>",
            "nova-ec2-public": "<haproxy vip>",
            "keystone-admin-api": "<haproxy vip>",
            "keystone-service-api": "<haproxy vip>",
            "cinder-api": "<haproxy vip>",
            "glance-api": "<haproxy vip>",
            "glance-registry": "<haproxy vip>",
            "nova-novnc-proxy": "<haproxy vip>",
            "nova-xvpvnc-proxy": "<haproxy vip>",
            "horizon-dash": "<haproxy vip>",
            "horizon-dash_ssl": "<haproxy vip>"
        },
        "nova": {
            "networks": [
                {
                    "label": "public",
                    "bridge_dev": "eth1",
                    "dns2": "8.8.4.4",
                    "num_networks": "1",
                    "ipv4_cidr": "192.168.222.0/24",
                    "network_size": "255",
                    "bridge": "br100",
                    "dns1": "8.8.8.8"
                }
            ]
        },
        "mysql": {
            "allow_remote_root": true,
            "root_network_acl": "%"
        },
        "osops_networks": {
            "nova": "192.168.122.0/24",
            "public": "192.168.122.0/24",
            "management": "192.168.122.0/24"
        }
    }
~~~~

The only addition to this environment is the section called "vips".

Like the single-controller configuration, this configuration requires
specific ordering to allow chef to configure and publish cluster
information such that other nodes can find it.

Add the two infrastructure nodes to the appropriate environment, and
set the run_list of one to "ha-controller1" and the other to
"ha-controller2".

* Run chef-client on the node with the "ha-controller1" role
* Run chef-client on the "ha-controller2" node
* Run chef-client on the "ha-controller1" node again

This will configure the load balancing and VRRP on both sides, as well
as the MySQL master/master replication.

Once these steps have run successfully, compute nodes can be brought
online in parallel with the "single-controller" role, as in the
previous configuration.

Customizing the Environment
---------------------------

Almost every component of the OpenStack installation can be tweaked by
using environment settings. To a large degree, these customizations
are detailed in the README files of each individual cookbook, found
[on the github repo for that cookbook](http://github.com/rcbops-cookbooks).

That said, some of the customizations are more common than others.

Some override_attributes typically used include:

~~~~
    "rabbitmq": {
        "tcp_keepalive": true,
        "use_distro_version": true
    }
~~~~

These settings are used to fail client connections more rapidly on HA
failover, and to prefer the distro rabbitmq packaging over the
upstream rabbitmq vendor package.

~~~~
    "nova": {
        "config": {
            "ram_allocation_ratio": "1",
            "cpu_allocation_ratio": "16"
        },
        "libvirt": {
            "vncserver_listen": "0.0.0.0",
            "virt_type": "kvm"
        }
~~~~

The nova/config options allow specific overcommit ratios for ram and
CPU.  These might be adjusted for a particular workload.

The nova/libvirt/vncserver_listen option of "0.0.0.0" allows the vnc
listener to wildcard bind on the compute hosts. Unless strictly
controlling iptables, this could allow unexpected vnc access to VM
instances, but is necessary on the OpenStack Folsom release for
instance migration to work. It has not been verified yet if this
override is required for migration on the Grizzly release.

The last setting, nova/libvirt/virt_type will allow for switching from
"kvm" (the default libvirt virtualization type) to "qemu", which is
useful for installing a cluster in an environment without
virtualization (cloud in a cloud, or test clusters in desktop virt
products that do not expose nested vmx, for example).

~~~~
    "osops": {
         "do_package_upgrades": true
    }
~~~~

By default, the chef cookbooks will only install the OpenStack
packages, they will not upgrade them if they become available from the
upstream vendor repository.

Setting osops/do_package_upgrades to "true" will cause any updated
packages to be installed when they become available.  Note that (for
the Ubuntu cloud archive repository, anyway) this will likely not
cause wholesale upgrades between OpenStack releases ("Grizzly" to
"Havana" for example), but just point releases on the existing
version.

Be aware this has the possibility of making your cluster go sideways.

~~~~
    "glance": {
        "image_upload": true,
        "images": [
            "cirros", "precise"
        ]
    }
~~~~

By default, on initial installation, no images will be uploaded into
glance. Using the glance/image_upload setting, along with the
glance/images setting, some convenience images can be uploaded at the
time of installation. This can sometimes be convenient when spinning
up clusters for automated testing.

The chef cookbooks currently understand convenience images for
"cirros", "precise", "oneiric", and "natty".
