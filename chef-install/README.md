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

This appropriatly named command can be used to install the rcbops
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

If installing from the Opscode, don't forget to [set up a user](http://docs.opscode.com/chef/install_workstation.html]!

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

This can perhaps best be illustrated with an example environment:

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
