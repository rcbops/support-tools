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
# $:./quantum-upgrade.sh

# Overview:
# If the Neutron Database is corrupted during the upgrade process this is a tool
# to correct the corruption using a backup database. This tool will Restore your
# "quantum" database stamp it as Grizzly and then upgrade it to Havana. This
# tool assumes the pre-upgrade script was used to backup the databases prior to
# the upgrade run.

# Available Overrides:
#     DB_BACKUP_DIR="/Directory/Name"
#     NCONF="/Path/to/Neutron/Config/file"
#     NPLUGIN="/Path/to/Neutron/Plugin/file"


set -e
set -u

MYSQL=$(which mysql)

# If a my.cnf file is not found, force the user to enter the mysql root password
if [ ! -f "${HOME}/.my.cnf" ];then
    echo -e "No \".my.cnf\" in \"${HOME}\". You are going to need the MySQL" \
            "Root password."
    MYSQL="${MYSQL} -u root -p"
fi

# Set the Backup Directory
DB_BACKUP_DIR=${DB_BACKUP_DIR:-"/root/database_backups"}
if [ ! -d "${DB_BACKUP_DIR}" ];then
    echo "Backup directory \"${DB_BACKUP_DIR}\" was not found," \
         " Maybe Try Setting: \"export DB_BACKUP_DIR=/path/to/dir\""
    exit 1
fi

# Set the name of the neutron service
NEUTRON_SERVICE=$(ls /etc/init.d/ | grep -E "neutron-server")

# if the quantum database file is not found exit
if [ ! -f "${DB_BACKUP_DIR}/quantum.sql" ];then
    echo "The Quantum Database File was not found."
    exit 1
fi

# Set neutron.conf
NCONF=${NCONF:-"/etc/neutron/neutron.conf"}

# If the file is not found Exit
if [ ! -f "${NCONF}" ];then
    echo "\"${NCONF}\" was not found. We can not upgrade your Quantum Setup"
    exit 1
fi

# Set neutron plugin
NPLUGIN=${NPLUGIN:-"/etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini"}

# If the file is not found Exit
if [ ! -f "${NPLUGIN}" ];then
    echo "\"${NPLUGIN}\" was not found. We can not upgrade your Quantum Setup"
    exit 1
fi

# Stop the Neutron Service
if [ "$(service ${NEUTRON_SERVICE} status | grep 'start/running')" ];then
    service ${NEUTRON_SERVICE} stop
fi

# Drop the current Quantum Database
${MYSQL} -e "drop database quantum"

# Recreate the Quantum Database
${MYSQL} -e "create database quantum"

# ReImport the Quantum Database
pushd ${DB_BACKUP_DIR}
${MYSQL} -o quantum < quantum.sql
popd

# STAMP THE QUANTUM DB AS GRIZZLY. THIS IS A MUST DO!
neutron-db-manage --config-file ${NCONF} \
                  --config-file ${NPLUGIN} \
                  stamp grizzly

# Upgrade Neutron Database to havana
neutron-db-manage --config-file ${NCONF} \
                  --config-file ${NPLUGIN} \
                  upgrade havana

# Start Neutron Service
if [ "$(service ${NEUTRON_SERVICE} status | grep 'stop/waiting')" ];then
    service ${NEUTRON_SERVICE} start
fi

exit 0

