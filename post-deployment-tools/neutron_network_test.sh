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

# Test an attach neutron network and ping the Gateway
# This script will build 1 instance per network then it will ping the 
# Network gateway from within the network namespace.

# Variables:
#   FLAVOR=The flavor size ID, defaults to 2.
#   IMAGE=Image ID, defaults to the first found image ID.
#   KEYNAME=Name of a keypair, defaults to "PrivateCloudTest".


if [ ! -f "/tmp/test-key" ];then
  ssh-keygen -t rsa -f /tmp/test-key -N ''
fi

if [ ! -f "$(pwd)/openrc" ];then
  echo "No OpenRC File found"
  exit 1
else
  source openrc
fi

BASE_IMAGE="$(nova image-list | awk '/ACTIVE/ {print $2}' | head -n 1)"

FLAVOR=${FLAVOR:-2}
IMAGE=${IMAGE:-${BASE_IMAGE}}
KEYNAME=${KEYNAME:-"PrivateCloudTest"}


echo "Creating Key"
if [ ! "$(nova keypair-list | grep ${KEYNAME})" ];then
  nova keypair-add PrivateCloudTest --pub-key /tmp/test-key.pub
fi


echo "Creating Servers"
for i in $(neutron net-list | awk '{print $2}' | grep -v id)
  do 
    nova boot --image=${IMAGE} \
              --flavor=${FLAVOR} \
              --key-name=PrivateCloudTest \
              --nic net-id=$i \
              $i-PrivateCloudTest > /dev/null \
                && echo BUILD SUCCESS $i || echo BUILD FAIL "$i"
done
sleep 5


echo "Testing Networks"
for i in $(ip netns | grep qdhcp)
  do 
    GW=$(ip netns exec $i ip r | awk '/default/ {print $3}')
    (ip netns exec $i ping -c 2 ${GW} > /dev/null \
      && echo PING SUCCESS "$i" "${GW}") || echo PING FAIL "$i" "${GW}"
done

echo "Removing Test KeyPair"
nova keypair-delete ${KEYNAME}

echo "Removing Testing Instances"
for i in $(nova list | awk '/PrivateCloudTest/ {print $2}')
  do
    nova delete $i
done
