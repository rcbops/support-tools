#!/bin/bash
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

if [ $# -eq 0 ]; then
   echo "Usage: $0 <HOST> <PORT>"
   echo
   echo "<PORT> will default to 22 if not specified."
   exit 1 
fi

HOST=$1
PORT=$2

# If PORT is not set, default to 22
: ${PORT:="22"}

CLIENT_VERSION=${CLIENT_VERSION:-"11.2.0-1"}
ENVIRONMENT=${ENVIRONMENT:-_default}

PRIMARY_INTERFACE=$(ip route list match 0.0.0.0 | awk 'NR==1 {print $5}')
MY_IP=$(ip addr show dev ${PRIMARY_INTERFACE} | awk 'NR==3 {print $2}' | cut -d '/' -f1)
CHEF_FE_SSL_PORT=${CHEF_FE_SSL_PORT:-443}
CHEF_URL=${CHEF_URL:-https://${MY_IP}:${CHEF_FE_SSL_PORT}}

cat > /tmp/install_$HOST.sh <<EOF
sudo apt-get install -y curl
curl -skS -L http://www.opscode.com/chef/install.sh | bash -s - -v ${CLIENT_VERSION}
mkdir -p /etc/chef

cp /tmp/validation.pem /etc/chef/validation.pem

cat <<EOF2 > /etc/chef/client.rb
Ohai::Config[:disabled_plugins] = ["passwd"]

chef_server_url "${CHEF_URL}"
chef_environment "${ENVIRONMENT}"
EOF2

cat <<EOF2 > /etc/chef/knife.rb
chef_server_url "${CHEF_URL}"
chef_environment "${ENVIRONMENT}"
node_name "${1}"
EOF2

EOF

if [ ! -e validation.pem ]; then
    sudo cp /etc/chef-server/chef-validator.pem ./validation.pem
    sudo chown ${USER}: ./validation.pem
fi

scp -P $PORT ./validation.pem $HOST:/tmp/validation.pem
scp -P $PORT /tmp/install_$HOST.sh $HOST:/tmp/install.sh

ssh -t -p $PORT $HOST sudo /bin/bash /tmp/install.sh
ssh -t -p $PORT $HOST sudo chef-client
