Openstack Havana Tools
######################
:date: 2013-12-14 09:51
:tags: rackspace, quantum, neutron, openstack, tools, havana
:category: \*nix


database_backup.sh: 
  Backup all databases found in *MySQL* as individual files. The backup is performed using ``mysqldump`` and all files will be saved in a user configurable ``database_backup`` directory.

quantum-upgrade.sh: 
  This script restores the quantum database when upgrading from **Grizzly** to **Havana**. This tool assumes that you, the administrator, has a backup of your quantum database saved as ``quantum.sql`` in your ``database_backup`` directory. 


It is recommended that a recent backup be made of all Openstack databases prior to performing the any package upgrades. This backup process is easily facilitated by the ``database_backup.sh`` script.
