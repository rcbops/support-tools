#!/usr/bin/env bash

chef-server-ctl uninstall
dpkg -P chef-server
apt-get autoremove -y
apt-get purge -y
rm -rf /etc/chef-server /etc/chef /opt/chef-server /opt/chef /root/.chef /var/opt/chef-server/ /var/chef /var/log/chef-server/
sed -i '/export PATH=${PATH}:\/opt\/chef-server\/bin/d' /root/.bash_profile
pkill -9 -f /opt/chef
pkill -9 -f beam
pkill -9 -f postgres
