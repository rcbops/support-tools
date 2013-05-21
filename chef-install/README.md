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
