#!/usr/bin/env python

import logging
import os
import struct
import subprocess
import tempfile

import guestfs
import hivex


class SimpleHivex(object):
    """
    Simple hivex class to make it easier to jank around hives
    """
    # Just a key without a value
    REG_NONE = 0
    # A Windows string (encoding is unknown, but often UTF16-LE)
    REG_SZ = 1
    # A Windows string that contains %env% (environment variable expansion)
    REG_EXPAND_SZ = 2
    # A blob of binary
    REG_BINARY = 3
    # DWORD (32 bit integer), little endian
    REG_DWORD = 4
    # DWORD (32 bit integer), big endian
    REG_DWORD_BIG_ENDIAN = 5
    # Symbolic link to another part of the registry tree
    REG_LINK = 6
    # Multiple Windows strings.  See http://blogs.msdn.com/oldnewthing/archive/2009/10/08/9904646.aspx
    REG_MULTI_SZ = 7
    # Resource list
    REG_RESOURCE_LIST = 8
    # Resource descriptor
    REG_FULL_RESOURCE_DESCRIPTOR = 9
    # Resouce requirements list
    REG_RESOURCE_REQUIREMENTS_LIST = 10
    # QWORD (64 bit integer), unspecified endianness but usually little endian
    REG_QWORD = 11

    def __init__(self, hive_path):
        self.h = hivex.Hivex(hive_path, write=True)
        self.at_root = True
        self.current_node = self.h.root()
        self.current_path = '/'

        classname = self.__class__.__name__.lower()
        if __name__ != '__main__':
            self.logger = logging.getLogger('%s.%s' % (__name__, classname))
        else:
            self.logger = logging.getLogger(classname)

        select = self.h.node_get_child(self.current_node, 'Select')
        if select is None:
            self.ccs = 'CurrentControlSet'
            self.logger.debug('Not a system hive')
        else:
            ccs = self.h.node_get_value(select, 'Current')
            self.ccs = 'ControlSet%03d' % (self.h.value_dword(ccs))
            self.logger.debug('System hive: CCS: %s' % self.ccs)

    def navigate_to(self, key_path, create=False):
        keys = key_path.split('/')
        if keys[0] == '':
            keys.pop(0)
            self.at_root = True
            self.current_node = self.h.root()
            self.current_path = '/'

        if self.at_root is True:
            # transparently replace ccs with the actual
            # control set
            if keys[0].lower() == 'currentcontrolset':
                keys[0] = self.ccs

        for key in keys:
            next_node = self.h.node_get_child(self.current_node, key)
            if next_node is None:
                if create is True:
                    self.add_subkey(key)
                else:
                    raise ValueError('No key %s' % key)
            else:
                self.current_node = next_node
                self.at_root = False

            self.current_path += key + '/'

    def has_subkey(self, name):
        sk = self.h.node_get_child(self.current_node, name)
        if sk is None:
            return False
        return True

    def delete_subkey(self, name):
        if not self.has_subkey(name):
            return

        self.logger.debug('deleting subkey %s%s' % (self.current_path, name))

        gone = self.h.node_get_child(self.current_node, name)
        self.h.node_delete_child(gone)

    def add_subkey(self, name):
        if self.has_subkey(name):
            self.navigate_to(name)
        else:
            self.logger.debug('adding subkey %s%s' % (self.current_path, name))
            sk = self.h.node_add_child(self.current_node, name)
            if sk is None:
                raise RuntimeError('Cannot add subkey: %s' % (name, ))

            self.current_node = sk
            self.at_root = False

    def _add_value(self, value_type, key, value):
        val = None

        if value_type == SimpleHivex.REG_SZ:
            val = value.encode('utf-16le') + '\0\0'
        elif value_type == SimpleHivex.REG_EXPAND_SZ:
            val = value.encode('utf-16le') + '\0\0'
        elif value_type == SimpleHivex.REG_DWORD:
            val = struct.pack('I', value)
        else:
            raise ValueError('Unknown value type: %s' % (value_type, ))

        new_value = {'key': key,
                     't': value_type,
                     'value': val}

        self.logger.debug('setting %s%s to %s' % (
                self.current_path, key, str(value)))

        self.h.node_set_value(self.current_node, new_value)

    def has_value(self, key):
        if self.h.node_get_value(self.current_node, key) is None:
            return False
        return True

    def _get_val(self, what, key):
        val = self.h.node_get_value(self.current_node, key)
        if val is None:
            return None

        if what == SimpleHivex.REG_SZ:
            return self.h.value_string(val)
        elif what == SimpleHivex.REG_DWORD:
            return self.h.value_dword(val)
        else:
            raise ValueError('Unknown type: %d' % what)

    def get_string(self, key):
        return self._get_val(SimpleHivex.REG_SZ, key)

    def get_dword(self, key):
        return self._get_val(SimpleHivex.REG_DWORD, key)

    def add_reg_sz(self, key, value):
        return self._add_value(SimpleHivex.REG_SZ, key, value)

    def add_reg_expand_sz(self, key, value):
        return self._add_value(SimpleHivex.REG_EXPAND_SZ, key, value)

    def add_reg_dword(self, key, value):
        return self._add_value(SimpleHivex.REG_DWORD, key, value)

    def commit(self):
        self.h.commit(None)


def active_guestfs(func):
    def f(self, *args, **kwargs):
        if self.gfs is None:
            self.gfs = guestfs.GuestFS()
            readonly = 0
            if self.readonly:
                readonly = 1

            self.gfs.add_drive_opts(self.image_path, readonly=readonly)
            self.logger.debug('Launching guestfs')
            self.gfs.launch()

        result = func(self, *args, **kwargs)
        return result

    return f


def registered_info(func):
    def f(self, *args, **kwargs):
        if getattr(self, 'disk_format', None) is None:
            info = self.info()
            self.logger.debug('Volume info: %s' % (info, ))

        result = func(self, *args, **kwargs)
        return result

    return f


def mounted_devices(func):
    def f(self, *args, **kwargs):
        current_mounts = self.gfs.mounts()

        def compare(a, b):
            return len(a) - len(b)

        for device in sorted(self.mountpoints.keys(), compare):
            if self.mountpoints[device] in current_mounts:
                continue

            self.logger.debug('Mounting device %s' % device)

            try:
                if self.readonly == 1:
                    self.gfs.mount_ro(self.mountpoints[device], device)
                else:
                    self.gfs.mount(self.mountpoints[device], device)

            except RuntimeError as msg:
                print '%s (ignored)' % msg

        self.logger.debug('Current mounts: %s' % (self.gfs.mounts(), ))
        result = func(self, *args, **kwargs)
        return result

    return f


class Image(object):
    """
    Simple image class to simplify the tasks of image conversion
    and windows driver injection.
    """
    def __init__(self, image_path, readonly=True):
        self.image_path = image_path
        self.readonly = readonly
        self.gfs = None

        classname = self.__class__.__name__.lower()
        if __name__ != '__main__':
            self.logger = logging.getLogger('%s.%s' % (__name__, classname))
        else:
            self.logger = logging.getLogger(classname)

    @active_guestfs
    def info(self):
        roots = self.gfs.inspect_os()

        if len(roots) != 1:
            raise ValueError('Bad disk image: roots = %s' % len(roots))

        self.root = roots[0]

        self.disk_format = 'unknown'
        if self.image_path.endswith('.qcow2'):
            self.disk_format = 'qcow2'
        elif self.image_path.endswith('.vmdk'):
            self.disk_format = 'vmdk'

        self.distro = self.gfs.inspect_get_distro(self.root)
        self.arch = self.gfs.inspect_get_arch(self.root)
        self.fs = self.gfs.inspect_get_filesystems(self.root)
        self.format = self.gfs.inspect_get_format(self.root)
        self.hostname = self.gfs.inspect_get_hostname(self.root)
        self.major = self.gfs.inspect_get_major_version(self.root)
        self.minor = self.gfs.inspect_get_minor_version(self.root)
        self.ostype = self.gfs.inspect_get_type(self.root)
        self.product = self.gfs.inspect_get_product_name(self.root)
        self.variant = self.gfs.inspect_get_product_variant(self.root)
        self.mountpoints = dict(self.gfs.inspect_get_mountpoints(self.root))

        if self.ostype == 'windows':
            self.systemroot = self.gfs.inspect_get_windows_systemroot(self.root)


        return dict([x, getattr(self, x)] for x in ['arch', 'distro', 'fs',
                                                    'format', 'hostname',
                                                    'major', 'minor', 'ostype',
                                                    'product', 'variant',
                                                    'disk_format',
                                                    'mountpoints'])

    def _upload_directory(self, src_dir, dst_dir, recursive=True):
        """
        given a directory of files, flat plain upload thost
        files to the guest at the destination directory.

        If the directory does not exist, it will be created
        """

        self.logger.debug('Uploading "%s" to "%s"' % (
                src_dir, dst_dir))

        if not self.gfs.is_dir(dst_dir):
            self.gfs.mkdir_p(dst_dir)

        for f in os.listdir(src_dir):
            src_file = os.path.join(src_dir, f)
            dst_file = self.gfs.case_sensitive_path(dst_dir)
            dst_file = os.path.join(dst_file, f)

            if os.path.isfile(src_file):
                # upload it!
                self.logger.debug(" %s => %s" % (src_file, dst_file))
                self.gfs.upload(src_file, dst_file)

            elif os.path.isdir(fullpath):
                if recursive is True:
                    self._upload_directory(src_file, dst_file)
            # otherwise skip it!

    def _upload_virtio(self, virtio_base, software_hive=None):
        """
        determine what version of the virtio drivers the
        destination machine requires, and upload them onto
        the system.  Presumably to be installed at some later
        date.  (firstboot script, maybe?)
        """

        dest_path = '/v2v-virtio'

        version_map = {'6.2': 'WIN8',   # server 2k12
                       '6.1': 'WIN7',   # server 2k8r2
                       '6.0': 'WLH',    # server 2k8
                       '5.2': 'WNET'}   # server 2k3/2k3r2

        version = '%d.%d' % (self.major, self.minor)
        win_arch = {'x86_64': 'AMD64',
                    'i386': 'X86'}[self.arch]

        if not version in version_map:
            raise ValueError('No virtio drivers for version "%s"' % version)

        source_path = os.path.join(virtio_base,
                                   version_map[version],
                                   win_arch)

        self._upload_directory(source_path, dest_path)

        # we also need to handle viostor.sys specially --
        if self.gfs.is_file(self.gfs.case_sensitive_path(
                os.path.join(dest_path, 'viostor.sys'))):
            # must copy this to system32/drivers
            src_file = os.path.join(dest_path, 'viostor.sys')
            src_file = self.gfs.case_sensitive_path(src_file)

            dst_file = os.path.join(self.systemroot,
                                    'system32/drivers')
            dst_file = self.gfs.case_sensitive_path(dst_file)
            dst_file = os.path.join(dst_file, 'viostor.sys')

            self.logger.debug('Copying %s => %s' % (src_file, dst_file))
            self.gfs.cp(src_file, dst_file)

        # now, add dest_path to the drier search path
        if software_hive is not None:
            h = SimpleHivex(software_hive)
            h.navigate_to('/Microsoft/Windows/CurrentVersion')

            append_data = 'c:\\v2v-virtio'

            old_path = h.get_string('DevicePath')
            new_path = None

            if old_path is None:
                new_path = append_data
            elif append_data not in old_path:
                new_path = '%s;%s' % (old_path, append_data)

            if new_path is not None:
                h.add_reg_expand_sz('DevicePath', new_path)
                h.commit()

            h = None

        return True

    def _disable_auto_reboot(self, system_hive):
        h = SimpleHivex(system_hive)

        h.navigate_to('/CurrentControlSet/Control/CrashControl', True)
        h.add_reg_dword('AutoReboot', 0)

        h.commit()

    def _disable_processor_drivers(self, system_hive):
        """
        Not strictly necessary, perhaps, but worth doing anyway, I think.

        http://blogs.msdn.com/b/virtual_pc_guy/archive/2005/10/24/484461.aspx
        """

        h = SimpleHivex(system_hive)

        h.navigate_to('/CurrentControlSet/Services')
        h.delete_subkey('Processor')
        h.delete_subkey('Intelppm')

        h.commit()

    def _stub_viostor(self, system_hive):
        """
        Jank in the settings to force the system to PnP the virtio
        storage driver.  This is basically cribbed from
        http://support.microsoft.com/kb/314082

        viostor is a scsi class adaptor, so GUID is
        4D36E97B-E325-11CE-BFC1-08002BE10318, unlike the kb article,
        which specifies atapi
        """

        h = SimpleHivex(system_hive)

        # First, pump in the pci vid/did stuff

        # [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\CriticalDeviceDatabase\pci#ven_1af4&dev_1001]
        # "ClassGUID"="{4D36E97B-E325-11CE-BFC1-08002BE10318}"
        # "Service"="viostor"

        # for subkey in ['00000000', '00020000', '00021af4', '00021af4&rev_00']:
        #     h.navigate_to('/CurrentControlSet/Control/CriticalDeviceDatabase')
        #     h.add_subkey('pci#ven_1af4&dev_1001&subsys_%s' % (subkey, ))
        #     h.add_reg_sz('ClassGUID', '{4d36e97b-e325-11ce-bfc1-08002be10318}')
        #     h.add_reg_sz('Service', 'viostor')

        h.navigate_to('/CurrentControlSet/Control/CriticalDeviceDatabase')
        h.add_subkey('pci#ven_1af4&dev_1001&subsys_00021af4&rev_00')
        h.add_reg_sz('ClassGUID', '{4d36e97b-e325-11ce-bfc1-08002be10318}')
        h.add_reg_sz('Service', 'viostor')

        # Next, let's do the driver thing.  Should look like this
        # [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\viostor]
        # "ErrorControl"=dword:00000001
        # "Group"="SCSI miniport"
        # "Start"=dword:00000000
        # "Tag"=dword:00000021
        # "Type"=dword:00000001
        # "ImagePath"= (REG_EXPAND_SZ) "...path..."

        h.navigate_to('/CurrentControlSet/services/viostor', True)
        h.add_reg_dword('Type', 1)
        h.add_reg_dword('Start', 0)
        h.add_reg_dword('ErrorControl', 1)
        h.add_reg_dword('Tag', 64)
        h.add_reg_expand_sz('ImagePath', 'system32\\DRIVERS\\viostor.sys')
        h.add_reg_sz('Group', 'SCSI miniport')

        # Set up default parameters
        #
        # Probably don't need this if we are just going to turn around do the
        # real installation of the official drivers.  Oh well.
        #
        h.navigate_to('/CurrentControlSet/services/viostor/Parameters', True)
        h.add_reg_dword('BusType', 1)

        # h.add_subkey('MaxTransferSize')
        # h.add_reg_sz('ParamDesc', 'Maximum Transfer Size')
        # h.add_reg_sz('type', 'enum')
        # h.add_reg_sz('default', '0')

        # h.add_subkey('enum')
        # h.add_reg_sz('0', '64  KB')
        # h.add_reg_sz('1', '128 KB')
        # h.add_reg_sz('2', '256 KB')

        # h.navigate_to('/CurrentControlSet/Services/viostor/Parameters')
        h.add_subkey('PnpInterface')
        h.add_reg_dword('5', 1)

        h.navigate_to('/CurrentControlSet/Services/viostor/Enum', True)
        h.add_reg_sz('0', 'PCI\\VEN_1AF4&DEV_1001&SUBSYS_00021AF4&REV_00\\3&13c0b0c5&0&28')
        h.add_reg_dword('Count', 1)
        h.add_reg_dword('NextInstance', 1)
        h.commit()

    def _download_hive(self, hive, download_dir):
        remote_path = os.path.join(self.systemroot,
                                   'system32/config',
                                   hive)

        self.logger.debug('remote_path: %s' % remote_path)
        remote_path = self.gfs.case_sensitive_path(remote_path)
        local_path = os.path.join(download_dir, hive)

        self.logger.debug('Downloading hive "%s"' % (remote_path, ))
        self.gfs.download(remote_path, local_path)
        return local_path

    def _upload_hive(self, hive_path):
        what_hive = os.path.basename(hive_path)
        remote_path = os.path.join(self.systemroot,
                                   'system32/config',
                                   what_hive)
        remote_path = self.gfs.case_sensitive_path(remote_path)


        self.logger.debug('Uploading %s => %s' % (hive_path, remote_path))
        self.gfs.upload(hive_path, remote_path)

    def _windows_common_fixups(self, virtio_base='virtio'):
        """
        here, we'll inject the virtio drivers, fix up the boot stuff,
        and any other thing that is hypervisor agnostic.
        """
        tmpdir = tempfile.mkdtemp()
        system_hive = self._download_hive('system', tmpdir)
        software_hive = self._download_hive('software', tmpdir)

        self.logger.debug('Dropped system hive in %s' % (system_hive, ))

        if self._upload_virtio(virtio_base, software_hive) is False:
            raise ValueError('No virtio drivers for this version')

        self._stub_viostor(system_hive)
        # self._disable_processor_drivers(system_hive)
        self._disable_auto_reboot(system_hive)

        self._upload_hive(system_hive)
        self._upload_hive(software_hive)

    def _dev_from_root(self):
        """
        this is only true for devs like 'sdX'.  Other device
        types (nbdXpY) behave differently.  We might want to
        special-case in here by device name
        """

        root_dev = self.root
        while len(root_dev) > 0 and root_dev[-1] >= '0' and \
                root_dev[-1] <= '9':
            root_dev = root_dev[:-1]

        return root_dev

    @active_guestfs
    @registered_info
    @mounted_devices
    def convert(self, destination_hypervisor='kvm'):
        """
        Convert from whatever on disk format to the destination
        disk format.  This is not the format (vmdk vs. qcow2 or
        whatever), but rather the on-disk data.  Like, if you are
        trying to make a vmdk boot on Xen, you'll have to change
        root device and all that.

        I don't really care about Xen, because it's a fail, but
        someone with a less discerning taste than I could add it.

        Valid destination hypervisors:

          - kvm
          - xen

        """
        f = getattr(self, 'convert_%s_%s' % (destination_hypervisor,
                                             self.ostype), None)

        if f is None:
            raise ValueError('No converter to "%s" for platform "%s"' %
                             (destination_hypervisor, self.ostype))

        return f()

    @active_guestfs
    def convert_kvm_windows(self):
        """
        Several things we need to do.  We need to find the platform,
        inject the correct virtio drivers, and then fix up the boot
        device (apparently some kind of issue with head number or some
        such).  @see _fixheads()
        """

        self._windows_common_fixups()

    @active_guestfs
    def convert_xen_windows(self):
        raise NotImplementedError('Sorry.  No Xen specific conversion yet')

    @active_guestfs
    def convert_kvm_linux(self):
        # nothing to see here  :)
        return True

    @active_guestfs
    def convert_xen_linux(self):
        raise NotImplementedError('Sorry. No Xen specific conversion yet')

    @active_guestfs
    def to_qcow2(self,destination_path=None):
        """
        Convert an image from whatever native format it is in
        to qcow2 format.  Sparseness is in question.  Stoopid
        python-guestfs doesn't pass through sparseness options
        and whatnot, apparently.  The qemu2 format might be smart
        enough to sparse it appropriately.  We'll see.
        """

        if getattr(self, 'disk_format', None) is None:
            self.info()

        if self.disk_format == "qcow2":
            return None

        # we need to add a new disk image and dd it
        # over to the new disk.
        #
        # Sadly, python-guestfs does not expose the
        # sparse argument, so we can't well use this.
        # Back to the drawing board.

        # if destination_path is None:
        #     if '.' in self.image_path:
        #         base = self.image_path.rsplit('.')
        #         destination_path = '%s.qcow2' % (base, )
        #     else:
        #         destination_path = '%s.qcow2' % self.image_path

        # self.logger.debug('Converting disk of type "%s" to qcow2' %
        #                   (self.disk_format, ))

        # # generate an empty qcow2 with preallocated meta
        # self.logger.debug('Creating empty sparse qcow2 at %s' %
        #                   (destination_path, ))


        # root_device = self._dev_from_root()

        # src_size = self.gfs.blockdev_getsize64(root_device)
        # self.logger.debug('Source device size: %d bytes' % (src_size, ))

        # # qemu-img create -f qcow2 -o preallocation-metadata "path" "size"
        # result = subprocess.call(['qemu-img', 'create',
        #                           '-f', 'qcow2', '-o',
        #                           'preallocation=metadata',
        #                           destination_path,
        #                           str(src_size)])


        # # okay...we have a qcow.  Spin up a new instance with both
        # # drives mounted and copy the stuffs
        # gfs_new = guestfs.GuestFS()

        # # guestfs guarantees this will be /dev/sda
        # gfs_new.add_drive_opts(self.image_path, readonly=1)
        # gfs_new.add_drive_opts(destination_path, readonly=0)

        # self.logger.debug('Launching conversion guest')
        # gfs_new.launch()

        # self.logger.debug('Converting image')
        # gfs_new.copy_device_to_device('/dev/sda', '/dev/sdb')

        # gfs_new.close()

        # note, can't preallocate metadata and compress
        # at the same time (despite the fact it would
        # be useful)
        result = subprocess.call(['qemu-img', 'convert',
                                  '-c', '-O', 'qcow2',
                                  self.image_path, destination_path])

        return destination_path


logging.basicConfig(level=logging.DEBUG)

# foo = Image('/home/rpedde/vmware/player/Slim/Slim.vmdk')
# dest_path = foo.to_qcow2(destination_path='./win.qcow2')
# foo = Image(dest_path, readonly=False)

foo = Image('./win.qcow2', readonly=False)
foo.convert()
