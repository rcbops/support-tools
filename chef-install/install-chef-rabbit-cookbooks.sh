#!/usr/bin/env bash
set -e 
set -u

# Copyright [2013] [Rackspace US, Inc]
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

# This script was created to streamline the way support deploys chef-server,
# RabbitMQ and the RPC cookbooks. 

# This script will install several bits:
# The Latest Stable Chef Server
# Chef Client
# RabbitMQ 

# Once the bits hit the disk, these things will be setup:
# The rbops cookbooks will be uploaded to chef-server
# Knife will be configured for use on the host


# Here are the script Override Values.
# Any of these override variables can be exported as environment variables.

# Set this to override the chef default password, DEFAULT is "Random Things"
# CHEF_PW=""

# Set this to override the URL to download chef-server
# CHEF_URL=""

# Set to override the download URI for chef
# CHEF_SERVER_PACKAGE_URL=""

# Enable nightly builds of chef, true or false, default false
# CHEF_NIGHTLIES=""

# Enable pre-release builds of chef, true or false, default false
# CHEF_PRERELEASE=""

# Set this to override the PATH to the cookbooks on the local disk
# COOKBOOK_PATH=""

# Set this to override the Cookbook version, DEFAULT is "v4.1.2"
# COOKBOOK_VERSION=""

# Set this to override the RabbitMQ Password, DEFAULT is "Random Things"
# RMQ_PW=""

# Set this to override the URL to download RabbitMQ
# RABBIT_URL=""

# Set this to override the URL path to the release of RabbitMQ
# RABBIT_RELEASE=""

# Set this to override the URI for RabbitMQ
# RABBITMQ_PACKAGE_URL=""

# Begin the Install Process
# ============================================================================

# Chef Settings
CHEF_PW=${CHEF_PW:-$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 9)}
CHEF_URL=${CHEF_URL:-"https://www.opscode.com"}
CHEF_SERVER_VERSION=${CHEF_SERVER_VERSION:-"11.0.10-1"}
CHEF_CLIENT_VERSION=${CHEF_CLIENT_VERSION:-"11.10.4-1"}
CHEF_PRERELEASE=${CHEF_PRERELEASE:-"false"}
CHEF_NIGHTLIES=${CHEF_NIGHTLIES:-"false"}
COOKBOOK_PATH=${COOKBOOK_PATH:-"/opt/rpcs"}

# Rabbit Settings
RMQ_PW=${RMQ_PW:-"guest"}
RABBIT_URL=${RABBIT_URL:-"http://www.rabbitmq.com"}
RELEASE="${RABBIT_URL}/releases/rabbitmq-server/v3.1.5"
RABBIT_RELEASE=${RABBIT_RELEASE:-$RELEASE}

# Set Cookbook Version
COOKBOOK_VERSION=${COOKBOOK_VERSION:-v4.2.2}

# Make the system key used for bootstrapping self
ssh-keygen -t rsa -f /root/.ssh/id_rsa -N ''
pushd /root/.ssh/
cat id_rsa.pub | tee -a authorized_keys
popd


# Package Install
# ==========================================================================
# Build the omni truck API url for installing chef
function build_chef_url() {
  CHEF_PATH="${CHEF_URL}/chef/${CHEF_DISTRO}"
  CHEF_OPTIONS="&v=${CHEF_SERVER_VERSION}&prerelease=${CHEF_PRERELEASE}&nightlies=${CHEF_NIGHTLIES}"
  CHEF="${CHEF_PATH}${CHEF_OPTIONS}"
  export CHEF_SERVER_PACKAGE_URL=${CHEF_SERVER_PACKAGE_URL:-$CHEF}

}


function install_apt_packages() {
  apt-get update && apt-get install -y git curl erlang erlang-nox wget
  # Install RabbitMQ Repo
  RABBITMQ_KEY="http://www.rabbitmq.com/rabbitmq-signing-key-public.asc"
  wget -O /tmp/rabbitmq.asc ${RABBITMQ_KEY}
  apt-key add /tmp/rabbitmq.asc

  RABBITMQ="${RABBIT_RELEASE}/rabbitmq-server_3.1.5-1_all.deb"
  wget -O /tmp/rabbitmq.deb ${RABBITMQ_PACKAGE_URL:-$RABBITMQ}
  # Install Packages
  dpkg -i /tmp/rabbitmq.deb
  rm /tmp/rabbitmq.deb

  # Setup shared RabbitMQ
  rabbit_setup

  # Download/Install Chef
  export CHEF_DISTRO="download-server?p=ubuntu&pv=12.04&m=x86_64"
  build_chef_url
  wget -O /tmp/chef_server.deb ${CHEF_SERVER_PACKAGE_URL}
  dpkg -i /tmp/chef_server.deb
  rm /tmp/chef_server.deb

}


function install_yum_packages() {
  # Install BASE Packages
  IPTABLES_SAVE=${IPTABLES_SAVE:-"$(which iptables-save)"}
  IPTABLES=${IPTABLES:-"$(which iptables)"}
  
  if [ "${IPTABLES_SAVE}" ];then
    ${IPTABLES_SAVE} > /etc/iptables.original
  fi

  if [ "${IPTABLES}" ];then
    if [ ! $(${IPTABLES} -L | grep 4080) ];then
      ${IPTABLES} -I INPUT -m tcp -p tcp --dport 4080 -j ACCEPT
      service iptables save
    fi
    if [ ! $(${IPTABLES} -L | grep 4000) ];then
      ${IPTABLES} -I INPUT -m tcp -p tcp --dport 4000 -j ACCEPT
      service iptables save
    fi
  fi

  # Install Third Party Repositories
  pushd /tmp
  if [ ! "$(rpm -qa | grep epel-release-6)" ];then
    EPEL_URL="http://dl.fedoraproject.org/pub/epel/6/x86_64"
    wget ${EPEL_URL}/epel-release-6-8.noarch.rpm
    rpm -Uvh epel-release-6*.rpm
  fi
  if [ ! "$(rpm -qa | grep remi-release-6)" ];then
    REMI_URL="http://rpms.famillecollet.com/enterprise"
    wget ${REMI_URL}/remi-release-6.rpm
    rpm -Uvh remi-release-6*.rpm
  fi
  popd

  # Install Packages
  yum -y install git erlang wget curl

  # Install RabbitMQ
  RABBITMQ_KEY="${RABBIT_URL}/rabbitmq-signing-key-public.asc"
  rpm --import ${RABBITMQ_KEY}

  RABBITMQ="${RABBIT_RELEASE}/rabbitmq-server-3.1.5-1.noarch.rpm"
  wget -O /tmp/rabbitmq.rpm ${RABBITMQ_PACKAGE_URL:-$RABBITMQ}
  if [ ! "$(rpm -qa | grep rabbitmq-server)" ];then
    rpm -Uvh /tmp/rabbitmq.rpm
  fi
  chkconfig rabbitmq-server on
  /sbin/service rabbitmq-server start

  # Setup shared RabbitMQ
  rabbit_setup

  # Download/Install Chef
  export CHEF_DISTRO="download-server?p=el&pv=6&m=x86_64"
  build_chef_url
  wget -O /tmp/chef_server.rpm ${CHEF_SERVER_PACKAGE_URL}
  if [ ! "$(rpm -qa | grep chef-server)" ];then
    yum install -y /tmp/chef_server.rpm
  fi

}

function rabbit_setup() {
  if [ ! "$(rabbitmqctl list_vhosts | grep -w '/chef')" ];then
    rabbitmqctl add_vhost /chef
  fi

  if [ "$(rabbitmqctl list_users | grep -w 'chef')" ];then
    rabbitmqctl delete_user chef
  fi

  rabbitmqctl add_user chef "${RMQ_PW}"
  rabbitmqctl set_permissions -p /chef chef '.*' '.*' '.*'
  
  cat > /etc/rabbitmq/rabbitmq-env.conf <<EOF
NODE_IP_ADDRESS=0.0.0.0
NODE_PORT=5672
CONFIG_FILE=/etc/rabbitmq/rabbitmq
MNESIA_BASE=/var/lib/rabbitmq/mnesia
EOF
  /etc/init.d/rabbitmq-server stop
  sleep 2
  /etc/init.d/rabbitmq-server start

}

if [ "$(uname -p)" != "x86_64" ]; then
  echo "Chef packages are only available for x86_64.  Try again."
  exit 1
fi

# OS Check
if [ "$(grep -i -e redhat -e centos /etc/redhat-release)"  ]; then
  install_yum_packages
elif [ "$(grep -i -e ubuntu /etc/lsb-release)" ];then
  install_apt_packages
else
  echo "This is not a supported OS, So this script will not work."
  exit 1
fi

# Configure Chef Vars
if [ ! -d "/etc/chef-server" ];then
  mkdir -p "/etc/chef-server"
fi

cat > /etc/chef-server/chef-server.rb <<EOF
erchef['s3_url_ttl'] = 3600
nginx["ssl_port"] = 4000
nginx["non_ssl_port"] = 4080
nginx["enable_non_ssl"] = false
rabbitmq["enable"] = false
rabbitmq["password"] = "${RMQ_PW}"
rabbitmq['node_ip_address'] = "#{node['ipaddress']}"
rabbitmq['vip'] = "#{node['ipaddress']}"
chef_server_webui['enable'] = false
chef_server_webui['worker_processes'] = 1
chef_server_webui['web_ui_admin_default_password'] = "${CHEF_PW}"
bookshelf['url'] = "https://#{node['ipaddress']}:4000"
EOF

# Reconfigure Chef
chef-server-ctl reconfigure

# Install Chef Client
bash <(wget -O - http://opscode.com/chef/install.sh) -v ${CHEF_CLIENT_VERSION}

# Configure Knife
if [ ! -d "/root/.chef" ];then
  mkdir -p "/root/.chef"
fi

cat > /root/.chef/knife.rb <<EOF
log_level                :info
log_location             STDOUT
node_name                'admin'
client_key               '/etc/chef-server/admin.pem'
validation_client_name   'chef-validator'
validation_key           '/etc/chef-server/chef-validator.pem'
chef_server_url          'https://localhost:4000'
cache_options( :path => '/root/.chef/checksums' )
cookbook_path            [ "${COOKBOOK_PATH}/chef-cookbooks/cookbooks" ]
EOF

# Get RcbOps Cookbooks
if [ ! -d "${COOKBOOK_PATH}" ];then
  mkdir -p "${COOKBOOK_PATH}"
else
  rm -rf "${COOKBOOK_PATH}"
  mkdir -p "${COOKBOOK_PATH}"
fi
git clone git://github.com/rcbops/chef-cookbooks.git \
          ${COOKBOOK_PATH}/chef-cookbooks

pushd ${COOKBOOK_PATH}/chef-cookbooks
git checkout ${COOKBOOK_VERSION}
git submodule init
git submodule update

# Upload all of the RCBOPS Cookbooks
knife cookbook upload -o ${COOKBOOK_PATH}/chef-cookbooks/cookbooks -a

# Upload all of the RCBOPS Roles
knife role from file ${COOKBOOK_PATH}/chef-cookbooks/roles/*.rb

# Exit cookbook directory
popd

# go to root home
pushd /root
echo "export EDITOR=vim" | tee -a .bashrc
popd

# Get the contents of the ERLANG cookie
ERLANG_COOKIE=$(cat /var/lib/rabbitmq/.erlang.cookie)

# Tell users how to get started on the CLI
echo -e "
Installation Complete...

Note, if you are using more than one Controller server please use 
following erlang cookie on all of your RabbitMQ nodes:

erlang_cookie: ${ERLANG_COOKIE}

Within Chef and RPC you would set the Erlang cookie into the 
chef environment file as an override.  
" | tee /root/installation_complete.txt

# Exit Zero
exit 0

