#!/usr/bin/env bash

set -e

# Exit on ^C
trap exit INT

# Set your controllers and computes here
controllers=(evinfra{1,2}) 
computes=(evcompute{1,2,4,5})

# Things to clean up
items="{apache,openvswitch,mysql,monit,rabbitmq,nova,glance,cinder,quantum,keystone,keepalived,memcached,haproxy,chef,rsyslog}"
temp=($(eval echo ${items}))
procs=$(IFS='|'; echo "(${temp[*]})")

_nuke() {
  echo "===== Nuking chef-server from orbit. It's the only way to be sure. ====="
  ./chef-uninstall
  ./install-chef-server.sh
  rm validation.pem
}

_clean() {
  echo "===== Cleaning boxes ====="
  parallel --tag --onall --sshlogin $(IFS=,; echo "${controllers[*]},${computes[*]}") :::: <<EOF || true
    mkdir -p tmp
    cd tmp
    pkill -9 "${procs}"
    pkill -9 -f "${procs}"
    ipvsadm -C
    DEBIAN_FRONTEND=noninteractive dpkg --configure -a
    DEBIAN_FRONTEND=noninteractive apt-get purge ${items}* -y -qq
    rm -rf /etc/${items}* /var/lib/${items}* /var/log/${items}* /root/.{erlang,my,chef}* /var/chef* /var/opt/chef*
    cd
    rmdir tmp
EOF
}

_reload() {
  echo "===== Reconfigure chef clients ====="
  parallel 'knife node delete {} -y; knife client delete {} -y; ./install-chef-client.sh {}' ::: "${controllers[@]}" "${computes[@]}"
}

_envs() {
  echo "===== Setting environments/waiting for solr commit ====="
  
  knife exec -E "nodes.search('chef_environment:_default') {|n| n.chef_environment('grizzly'); n.save}"
  sleep 5
  while [[ -n $(knife exec -E "nodes.search('chef_environment:_default') {|n| puts n.name}") ]]
  do
    echo -n .
    knife exec -E "nodes.search('chef_environment:_default') {|n| n.chef_environment('grizzly'); n.save}"
    sleep 5
  done; echo
}

_runlists() {
  echo "===== Setting runlists ====="
 
  # Setup controller runlists
  parallel --xapply knife node run_list add {1} {2} ::: "${controllers[@]}" ::: role[ha-controller{1,2}],role[single-network-node]

  # Setup compute runlists
  parallel knife node run_list add {} "role[single-compute]" ::: "${computes[@]}"
}

_controllers() {
  # Run chef-client on controllers in order
  echo "===== Chef'ing controllers ====="
  ssh ${controllers[0]} chef-client -l info
  ssh ${controllers[1]} chef-client -l info
  ssh ${controllers[0]} chef-client -l info
}

_computes() {  
  # Run chef-client on computes simultaneously
  echo "===== Chef'ing computes ====="
  parallel --tag --nonall --sshlogin $(IFS=,; echo "${computes[*]}") chef-client -l info
}

# Check ze args
for arg in $@
do
  case "${arg,,}" in
    nuke)
      # Nuke chef-server
      _nuke
      ;;
    clean)
      # Clean up boxes
      _clean
      ;;
    reload)
      # Reconfigure chef clients
      _reload
      ;;
    envs)
      # Setup environments
      _envs
      ;;
    runlists)
      # Setup runlists
      _runlists
      ;;
    controllers)
      # Chef controllers
      _controllers
      ;;
    computes)
      # Chef computes
      _computes
      ;;
    chef)
      # Needfuls
      _controllers; _computes
      ;;
    all)
      _clean; _reload; _envs; _runlists; _controllers; _computes
      ;;
  esac
done
