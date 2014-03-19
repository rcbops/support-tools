#!/usr/bin/env bash
#
# Copyright 2013 Rackspace US, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author Kevin.Carter@Rackspace.com

# Usage:
# $:./rax-nimbus-install.sh

# Overview:
# Install nimbus and set it up according to the installation methods described
# in the Support WIKI. This tool was created to allow for the rapid installation
# of nimbus on Rackspace Dedicated servers. To use the script, upload the
# "nimbus-installer.tar.gz" file to the "/tmp" directory then execute the script
# locally.

# Notes:
# This script makes the assumption that the server is using a dedicated publicly
# routable IP address. The script attempts to use "icanhazip.com" to retrieve the
# IP address. This is used in the nimbus setup script when registering the agent.
# The script also assumes that the "/root/.rackspace/" was setup correctly
# and contains the following files: customer_number, server_number, datacenter.
# The last action of this script is to change the run level of nimbus. The script
# will attempt to set it to "defaults 99" when ubuntu and "checkconfig on" when
# RHEL. All of the run levels will be overridden IF LSB headers are found in the
# Provided NIMBUS init script.

set -e
set -u


WORKING_DIR="/tmp"
NIMBUS_INSTALLER_TAR="${WORKING_DIR}/nimbus-installer.tar.gz"
NIMBUS_INIT="/etc/init.d/nimbus"


# Check for the nimbus file
if [[ ! -f "${NIMBUS_INSTALLER_TAR}" ]];then
  echo "The nimbus tar ball was not found at \"${NIMBUS_INSTALLER_TAR}\""
  exit 1
fi


# Install cURL if its not found
apt-get -y install curl || yum -y install curl


pushd /tmp
  tar -zxvf ${NIMBUS_INSTALLER_TAR}
popd


pushd ${WORKING_DIR}/nimbus-installer

  # If Nimbus is installed stop it
  if [[ -f "${NIMBUS_INIT}" ]];then
    ${NIMBUS_INIT} stop
  fi

  # Install Nimbus
  sudo python nimbusinstaller.py -A "$(cat /root/.rackspace/customer_number)" \
                                 -S "$(cat /root/.rackspace/server_number)" \
                                 -I "$(curl -s icanhazip.com)" \
                                 -D "$(cat /root/.rackspace/datacenter | tr [A-Z] [a-z] | tr [:digit:] ' ')"
popd


# Update the nimbus run levels.
if [[ "$(grep -i -e redhat -e centos /etc/redhat-release)" ]];then
  chkconfig nimbus on
elif [[ "$(grep -i ubuntu /etc/lsb-release)" ]];then
  update-rc.d nimbus start 99 2 3 4 5 . stop 99 0 1 6 .
fi


# Start the Nimbus Service
${NIMBUS_INIT} start


