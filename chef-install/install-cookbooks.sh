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

# if we haven't logged off yet, and our path doesn't point to
# /opt/whatever/bin, we'll try and make it go by sourcing
# the profile we bumped it into
#
if [ -e ${HOME}/.bash_profile ]; then
    source ${HOME}/.bash_profile
fi

set -e
set -u
set -x

COOKBOOK_BRANCH=${COOKBOOK_BRANCH:-v4.1.2}

# Figure out what OS we are running, to decide if we
# are going to run apt or yum, basically.  Cut/pasted out of the
# chef installer script.
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

# we are going to assume that we are running as the user
# that has knife provisioned, so we'll dump the cookbooks
# in ~/chef-cookbooks, unless otherwise specified.
COOKBOOK_PATH=${COOKBOOK_PATH:-${HOME}/chef-cookbooks}
if [[ $OS_TYPE = "ubuntu" ]] || [[ $OS_TYPE = "debian" ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y --force-yes git
else
    yum install -y git
fi

git clone https://github.com/rcbops/chef-cookbooks ${COOKBOOK_PATH}

# and then checkout the cookbooks, upload the roles and
# the recipes.

pushd ${COOKBOOK_PATH}
git checkout ${COOKBOOK_BRANCH}
git submodule init
git submodule update

knife role from file roles/*.rb
knife cookbook upload -a -o cookbooks

popd

# done and done
