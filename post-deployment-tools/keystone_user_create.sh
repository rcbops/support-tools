#!/usr/bin/env bash

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

# Generating new Keystone Users 

# Variables:
#   TENANT_NAME=The name of an existing tenat that we will get the role from,
#               defaults to "demo".
#   USER_NAME=Set the name of the new Keystone User, will default to tenant
#             if not already created.
#   ROLE_NAME=The name of an existing role which your new user will be bound to.
#   PASSWD=Set the password, if not set it will be generated.

set -e -u

if [ ! -f "$(pwd)/openrc" ];then
  echo "No OpenRC File found in $(pwd)"
  exit 1
else
  source openrc
fi

TENANT_NAME=${TENANT_NAME:-"demo"}
USER_NAME=${USER_NAME:-$TENANT_NAME}
ROLE_NAME=${ROLE_NAME:-"demo"}
PASSWD=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 32)

# Get the role from a provided 
echo "Checking for role"
ROLE_ID=$(keystone role-list | grep -w ${ROLE_NAME} | awk '{print $2}')
if [[ -z "${ROLE_ID}" ]];then
  echo "Creating Role ${ROLE_NAME}"
  ROLE_ID=$(keystone role-create --name ${ROLE_NAME} | awk '/id/ {print $4}')
fi

# Creating the new tenant
echo "Creating Tenant ${TENANT_NAME}"
NEW_TENANT_ID=$(keystone tenant-create --name ${TENANT_NAME} | awk '/id/ {print $4}')

# Create the new User
echo "Creating User ${USER_NAME}"
USER_ID=$(keystone user-create --name ${USER_NAME} \
                               --pass ${PASSWD} \
                               --tenant_id ${NEW_TENANT_ID} \
                               --enabled true | awk '/id/ {print $4}')

# Creating the new user role
echo "Granting User ${USER_NAME} with Tenant ${TENANT_NAME} access to Role ${ROLE_NAME}"
keystone user-role-add --user_id ${USER_ID} \
                       --role_id ${ROLE_ID} \
                       --tenant_id ${NEW_TENANT_ID}

echo -e "
--------------------------------------
Here is the password, WRITE THIS DOWN!
--------------------------------------
Username: ${USER_NAME}
Tenant Name: ${TENANT_NAME}
Password: ${PASSWD}
"

cat > $(pwd)/openrc-customer2 <<EOF
# CUSTOMER OPENSTACK ENVS
export OS_USERNAME=${USER_NAME}
export OS_PASSWORD=${PASSWD}
export OS_TENANT_NAME=${TENANT_NAME}
export OS_AUTH_URL=${OS_AUTH_URL}
export OS_AUTH_STRATEGY=keystone
export OS_NO_CACHE=1
EOF
