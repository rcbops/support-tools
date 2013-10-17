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

set -e
set -u
set -x

export DEBIAN_FRONTEND=noninteractive

pwgen() {
    local l=${1:-8}
    tr -dc A-Za-z0-9_ < /dev/urandom | head -c ${l} | xargs
}

if [ -e /etc/lsb-release ]; then
    source /etc/lsb-release
    OS_TYPE=${DISTRIB_ID~}
    OS_VER=${DISTRIB_RELEASE}
elif [ -f "/etc/system-release-cpe" ]; then
    OS_TYPE=$(cat /etc/system-release-cpe | cut -d ":" -f 3)
    OS_VER=6
else
    echo "Cannot determine operating system"
    exit 1
fi

if [ "$(uname -p)" != "x86_64" ]; then
    echo "Chef packages are only available for x86_64.  Try again."
    exit 1
fi

CHEF_SERVER_VERSION=${CHEF_SERVER_VERSION:-11.0.8-1}

if [[ $OS_TYPE = "ubuntu" ]]; then
    apt-get update -y --force-yes
    locale-gen en_US.UTF-8
    apt-get install -y --force-yes lsb-release curl wget
    cp /etc/resolv.conf /tmp/rc
    apt-get remove --purge resolvconf -y --force-yes
    cp /tmp/rc /etc/resolv.conf
elif [[ $OS_TYPE = "redhat" ]] || [[ $OS_TYPE = "centos" ]] || [[ $OS_TYPE = "fedora" ]]; then
    yum -y install curl wget
else
    echo "Your distribution is not supported"
    exit 1
fi

PRIMARY_INTERFACE=$(ip route list match 0.0.0.0 | awk 'NR==1 {print $5}')
MY_IP=$(ip addr show dev ${PRIMARY_INTERFACE} | awk 'NR==3 {print $2}' | cut -d '/' -f1)
CHEF_UNIX_USER=${CHEF_UNIX_USER:-root}
CHEF_UNIX_USER_PASSWORD=${CHEF_UNIX_USER_PASSWORD:-$(pwgen)}

# due to http://tickets.opscode.com/browse/CHEF-3849 CHEF_FE_PORT is not used yet
CHEF_FE_PORT=${CHEF_FE_PORT:-80}
CHEF_FE_SSL_PORT=${CHEF_FE_SSL_PORT:-443}
CHEF_URL=${CHEF_URL:-https://${MY_IP}:${CHEF_FE_SSL_PORT}}

if [ ! -e "/etc/chef-server/chef-server.rb" ]; then
  # defaults if not set
  CHEF_WEBUI_PASSWORD=${CHEF_WEBUI_PASSWORD:-$(pwgen)}
  CHEF_AMQP_PASSWORD=${CHEF_AMQP_PASSWORD:-$(pwgen)}
  CHEF_POSTGRESQL_PASSWORD=${CHEF_POSTGRESQL_PASSWORD:-$(pwgen)}
  CHEF_POSTGRESQL_RO_PASSWORD=${CHEF_POSTGRESQL_PASSWORD:-$(pwgen)}

  mkdir -p /etc/chef-server
  cat > /etc/chef-server/chef-server.rb <<EOF
node.override["chef_server"]["chef-server-webui"]["web_ui_admin_default_password"] = "${CHEF_WEBUI_PASSWORD}"
node.override["chef_server"]["rabbitmq"]["password"] = "${CHEF_AMQP_PASSWORD}"
node.override["chef_server"]["postgresql"]["sql_password"] = "${CHEF_POSTGRESQL_PASSWORD}"
node.override["chef_server"]["postgresql"]["sql_ro_password"] = "${CHEF_POSTGRESQL_RO_PASSWORD}"
node.override["chef_server"]["nginx"]["url"] = "${CHEF_URL}"
node.override["chef_server"]["nginx"]["ssl_port"] = ${CHEF_FE_SSL_PORT}
node.override["chef_server"]["nginx"]["non_ssl_port"] = ${CHEF_FE_PORT}
node.override["chef_server"]["nginx"]["enable_non_ssl"] = true
if (node['memory']['total'].to_i / 4) > ((node['chef_server']['postgresql']['shmmax'].to_i / 1024) - 2097152)
  # guard against setting shared_buffers > shmmax on hosts with installed RAM > 64GB
  # use 2GB less than shmmax as the default for these large memory machines
  node.override['chef_server']['postgresql']['shared_buffers'] = "14336MB"
else
  node.override['chef_server']['postgresql']['shared_buffers'] = "#{(node['memory']['total'].to_i / 4) / (1024)}MB"
end
EOF

    HOMEDIR=$(getent passwd ${CHEF_UNIX_USER} | cut -d: -f6)
    export HOME=${HOMEDIR}

    if [[ $OS_TYPE = "ubuntu" ]]; then
        if ! dpkg -s chef-server &>/dev/null; then
            curl -L "http://www.opscode.com/chef/download-server?p=ubuntu&pv=${OS_VER}&m=x86_64&v=${CHEF_SERVER_VERSION}" > /tmp/chef-server.deb
            dpkg -i /tmp/chef-server.deb
            chef-server-ctl reconfigure
            rm -f /tmp/chef-server.deb
        fi
    else
        if ! rpm -q chef-server &>/dev/null; then
            curl -L "http://www.opscode.com/chef/download-server?p=el&pv=${OS_VER}&m=x86_64&v=${CHEF_SERVER_VERSION}" > /tmp/chef-server.rpm
            rpm -ivh /tmp/chef-server.rpm
            chef-server-ctl reconfigure
            rm -f /tmp/chef-server.rpm
        fi
    fi

    mkdir -p ${HOMEDIR}/.chef
    cp /etc/chef-server/{chef-validator.pem,chef-webui.pem,admin.pem} ${HOMEDIR}/.chef
    chown -R ${CHEF_UNIX_USER}: ${HOMEDIR}/.chef

    if [[ ! -e ${HOMEDIR}/.chef/knife.rb ]]; then
        /opt/chef-server/embedded/bin/knife user create ${CHEF_UNIX_USER} --disable-editing \
        --user admin --key ${HOMEDIR}/.chef/admin.pem --server-url ${CHEF_URL} --admin \
        -f ${HOMEDIR}/.chef/${CHEF_UNIX_USER}.pem -p ${CHEF_UNIX_USER_PASSWORD}
       cat <<EOF | /opt/chef-server/embedded/bin/knife configure -i --key ${HOMEDIR}/.chef/${CHEF_UNIX_USER}.pem --user ${CHEF_UNIX_USER}
${HOMEDIR}/.chef/knife.rb
${CHEF_URL}
admin
${HOMEDIR}/.chef/admin.pem
chef-validator
${HOMEDIR}/.chef/chef-validator.pem

EOF
        # setup the path
        echo 'export PATH=${PATH}:/opt/chef-server/embedded/bin' >> ${HOMEDIR}/.bash_profile
    fi

    # these are only returned on a run where we actually install chef-server
fi
