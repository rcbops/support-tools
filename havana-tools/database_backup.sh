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
# $:./database_backup.sh

# Overview:
# When running a Grizzly to Havana Upgrade this should be the first step. The
# simple BASH script will Backup all of the your databases as found in MySQL.
# Note this only works with MySQL. The script saves a backup of all databases as
# individual files in a backup directory which can be customized by setting the
# "DB_BACKUP_DIR" environment variable. If the Backup directory does not exist
# it will be created. You will also need to either have a ".my.cnf" file set in
# your home directory with access to the root MySQL user or know the root MySQL
# password if the file does not exist.

# Available Overrides:
#     DB_BACKUP_DIR="/Directory/Name"


set -e
set -u

# Set the full path to the MYSQL commands
MYSQLDUMP=$(which mysqldump)
MYSQL=$(which mysql)

# If a my.cnf file is not found, force the user to enter the mysql root password
if [ ! -f "${HOME}/.my.cnf" ];then
    echo -e "No \".my.cnf\" in \"${HOME}\". You are going to need the MySQL" \
            "Root password."
    MYSQL="${MYSQL} -u root -p"
    MYSQLDUMP="${MYSQLDUMP} -u root -p"
fi

# return a list of databases to backup
DB_NAMES=$(${MYSQL} -Bse "show databases;" | grep -v -e "schema" -e "mysql")

# Set the backup directory
DB_BACKUP_DIR=${DB_BACKUP_DIR:-"/root/database_backups"}

# Make the database backup dir if not found
if [ ! -d "${DB_BACKUP_DIR}" ];then
    echo "Creating the backup directory ${DB_BACKUP_DIR}"
    mkdir -p "${DB_BACKUP_DIR}"
fi

# Go to the Database Backup Dir
pushd ${DB_BACKUP_DIR}

# Backup all databases individually
for db in ${DB_NAMES};do
    echo "Performing a Database Backup on ${db}"
    ${MYSQLDUMP} ${db} > ${db}.sql
done

popd

exit 0
