#!/usr/bin/env python

import getopt
import logging
import os
import struct
import subprocess
import sys
import tempfile

import glanceclient
import guestfs
import hivex
from keystoneclient.v2_0 import client as kc


def glance_upload(image_path, name):
    """
    there should probably be some more glance utility functions,
    or output and input paths should probably be expressible as
    glance urls or something like that.  meh.

    in truth, this is likely better done in bash using the glance
    client cli, but for some reason people aren't happy with
    chaining together multiple tools -- they want a single
    monolithic tool that works poorly.  So here you go -- this is
    that.  You're welcome.
    """

    # we'll assume that credentials and whatnot are expressed
    # in the environment already.
    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    tenant = os.environ['OS_TENANT_NAME']
    auth_url = os.environ['OS_AUTH_URL']

    # we'll just plain flat ignore the case where you
    # have an environment token and not user/pass
    kcli = kc.Client(username=username,
                     password=password,
                     tenant_name=tenant,
                     auth_url=auth_url)

    auth_token = kcli.auth_token
    glance_url = kcli.service_catalog.url_for(service_type='image')

    # this is sort of stupid
    decomposed_url = glance_url.split('/')
    if decomposed_url[-1] == 'v1':
        decomposed_url.pop(-1)
    glance_url = '/'.join(decomposed_url)

    # push the image
    gcli = glanceclient.Client('1', endpoint=glance_url,
                               token=auth_token)

    gimage = gcli.images.create(name=name, disk_format='qcow2',
                                container_format='bare',
                                is_public=False)

    gimage.update(data=open(image_path, 'rb'))



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

        self.logger.debug('setting %s%s to %s' %
                          (self.current_path, key, str(value)))

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


class ConversionDriver(object):
    def __init__(self, gfs):
        self.gfs = gfs

        classname = self.__class__.__name__.lower()
        if __name__ != '__main__':
            self.logger = logging.getLogger('%s.%s' % (__name__, classname))
        else:
            self.logger = logging.getLogger(classname)

        roots = self.gfs.inspect_get_roots()
        self.root = roots[0]
        self.ostype = self.gfs.inspect_get_type(self.root)
        self.arch = self.gfs.inspect_get_arch(self.root)

        self.tmpdir = tempfile.mkdtemp()

    def cleanup(self):
        shutil.rmtree(self.tmpdir)

    def convert(self):
        raise NotImplementedError('Base class!')

    def _upload_directory(self, src_dir, dst_dir, recursive=True):
        """
        given a directory of files, upload them to the guest at the
        destination directory.

        If the directory does not exist, it will be created
        """

        self.logger.debug('Uploading "%s" to "%s"' %
                          (src_dir, dst_dir))

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

            elif os.path.isdir(dst_file):
                if recursive is True:
                    self._upload_directory(src_file, dst_file)
            # otherwise skip it!


class WindowsConversionDriver(ConversionDriver):
    """
    shared utility functions for windows converters
    """
    def __init__(self, gfs):
        super(WindowsConversionDriver, self).__init__(gfs)

        self.logger.debug('Current mounts: %s' % (self.gfs.mounts(), ))

        # # !??!
        # self.gfs.mount('/dev/sda1', '/')

        self.systemroot = self.gfs.inspect_get_windows_systemroot(self.root)

        self.system_hive = self._download_hive('system', self.tmpdir)
        self.software_hive = self._download_hive('software', self.tmpdir)

        self.logger.debug('System hive in %s' % (self.system_hive, ))
        self.logger.debug('Software hive in %s' % (self.software_hive, ))

        self.major = self.gfs.inspect_get_major_version(self.root)
        self.minor = self.gfs.inspect_get_minor_version(self.root)
        self.product = self.gfs.inspect_get_product_name(self.root)
        self.variant = self.gfs.inspect_get_product_variant(self.root)


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
        here, we'll fix up the boot stuff and any other thing that is
        hypervisor agnostic.
        """
        self._disable_processor_drivers()
        self._set_auto_reboot(0)

    def _set_auto_reboot(self, value):
        h = SimpleHivex(self.system_hive)

        h.navigate_to('/CurrentControlSet/Control/CrashControl', True)
        h.add_reg_dword('AutoReboot', value)

        h.commit()

    def _disable_processor_drivers(self):
        """
        Not strictly necessary, perhaps, but worth doing anyway, I think.

        http://blogs.msdn.com/b/virtual_pc_guy/archive/2005/10/24/484461.aspx
        """

        h = SimpleHivex(self.system_hive)

        h.navigate_to('/CurrentControlSet/Services')
        h.delete_subkey('Processor')
        h.delete_subkey('Intelppm')

        h.commit()

    def _install_service(self, service_path, display_name):
        """
        Install a service on a dead windows disk
        """

        # http://support.microsoft.com/kb/103000
        #
        # [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\services\<name>]
        # "Type"=dword:00000010 (service controlled service)
        # "Start"=dword:00000002 (scm autoload)
        # "ErrorControl"=dword:00000001
        # "ImagePath"="..."
        # "DisplayName"="..."
        # "ObjectName"="LocalSystem"

        h = SimpleHivex(self.system_hive)

        service_name = display_name.replace(' ', '_').lower()

        h.navigate_to('/CurrentControlSet/services/%s' % service_name, True)
        h.add_reg_dword('Type', 0x10)
        h.add_reg_dword('Start', 0x02)
        h.add_reg_dword('ErrorControl', 0x01)
        h.add_reg_sz('ImagePath', service_path)
        h.add_reg_sz('DisplayName', display_name)
        h.add_reg_sz('ObjectName', 'LocalSystem')

        h.commit()

class KvmWindowsConversion(WindowsConversionDriver):
    def __init__(self, gfs):
        super(KvmWindowsConversion, self).__init__(gfs)

    def _stub_viostor(self):
        """
        Jank in the settings to force the system to PnP the virtio
        storage driver.  This is basically cribbed from
        http://support.microsoft.com/kb/314082

        viostor is a scsi class adaptor, so GUID is
        4D36E97B-E325-11CE-BFC1-08002BE10318, unlike the kb article,
        which specifies atapi
        """

        h = SimpleHivex(self.system_hive)

        # First, pump in the pci vid/did stuff

        # [HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\CriticalDeviceDatabase\pci#ven_1af4&dev_1001]
        # "ClassGUID"="{4D36E97B-E325-11CE-BFC1-08002BE10318}"
        # "Service"="viostor"

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

        h.add_subkey('PnpInterface')
        h.add_reg_dword('5', 1)

        h.navigate_to('/CurrentControlSet/Services/viostor/Enum', True)
        h.add_reg_sz('0', 'PCI\\VEN_1AF4&DEV_1001&SUBSYS_00021AF4&REV_00\\3&13c0b0c5&0&28')
        h.add_reg_dword('Count', 1)
        h.add_reg_dword('NextInstance', 1)
        h.commit()

    def _upload_virtio(self, virtio_base):
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
        h = SimpleHivex(self.software_hive)
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

    def convert(self):
        """
        This is the actual conversion to kvm for windows
        """
        self._windows_common_fixups()

        if self._upload_virtio('virtio') is False:
            raise ValueError('No virtio drivers for this version')

        self._stub_viostor()

        self._upload_hive(self.system_hive)
        self._upload_hive(self.software_hive)


class XenWindowsConversion(WindowsConversionDriver):
    def convert(self):
        raise NotImplementedError('Xen?')


class LinuxConversionDriver(ConversionDriver):
    """
    shared utility functions for linux converters
    """
    def __init__(self, gfs):
        super(LinuxConversionDriver, self).__init__(gfs)

        self.distro = self.gfs.inspect_get_distro(self.root)
        self.mountpoints = dict(self.gfs.inspect_get_mountpoint(self.root))


class KvmLinuxConversion(LinuxConversionDriver):
    def init(self, gfs):
        super(KvmLinuxConversionDriver, self).__init__(gfs)

    def convert(self):
        """
        actual conversion of linux images to kvm.  This could verify
        proper kernel and whatnot, but I expect there aren't many
        (any?) distros running non-virtio enabled kernels.  Largely,
        the only thing to be done here is fix up fstab if it's got
        xenish looking mounts in it.
        """
        pass


class XenLinxuConversion(LinuxConversionDriver):
    def convert(self, gfs):
        raise NotImplementedError


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

        return dict([x, getattr(self, x)] for x in ['arch', 'distro', 'fs',
                                                    'format', 'hostname',
                                                    'major', 'minor', 'ostype',
                                                    'product', 'variant',
                                                    'disk_format',
                                                    'mountpoints'])

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

        conversion_class = "%s%sConversion" % (
            destination_hypervisor.lower().title(),
            self.ostype.lower().title())

        cc = globals().get(conversion_class, None)
        if cc is None:
            raise ValueError('No converter to "%s" for platform "%s"' %
                             (destination_hypervisor, self.ostype))

        self.logger.debug('Initializing converter')
        cvrt = cc(self.gfs)
        self.logger.debug('Starting conversion')
        result = cvrt.convert()
        self.logger.debug('Conversion complete')
        return result


    @active_guestfs
    def to_qcow2(self, destination_path=None):
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
        #
        # self.logger.debug('Converting disk of type "%s" to qcow2' %
        #                   (self.disk_format, ))
        #
        # # generate an empty qcow2 with preallocated meta
        # self.logger.debug('Creating empty sparse qcow2 at %s' %
        #                   (destination_path, ))
        #
        #
        # root_device = self._dev_from_root()
        #
        # src_size = self.gfs.blockdev_getsize64(root_device)
        # self.logger.debug('Source device size: %d bytes' % (src_size, ))
        #
        # # qemu-img create -f qcow2 -o preallocation-metadata "path" "size"
        # result = subprocess.call(['qemu-img', 'create',
        #                           '-f', 'qcow2', '-o',
        #                           'preallocation=metadata',
        #                           destination_path,
        #                           str(src_size)])
        #
        #
        # # okay...we have a qcow.  Spin up a new instance with both
        # # drives mounted and copy the stuffs
        # gfs_new = guestfs.GuestFS()
        #
        # # guestfs guarantees this will be /dev/sda
        # gfs_new.add_drive_opts(self.image_path, readonly=1)
        # gfs_new.add_drive_opts(destination_path, readonly=0)
        #
        # self.logger.debug('Launching conversion guest')
        # gfs_new.launch()
        #
        # self.logger.debug('Converting image')
        # gfs_new.copy_device_to_device('/dev/sda', '/dev/sdb')
        #
        # gfs_new.close()

        # note, can't preallocate metadata and compress
        # at the same time (despite the fact it would
        # be useful)
        result = subprocess.call(['qemu-img', 'convert',
                                  '-c', '-O', 'qcow2',
                                  self.image_path, destination_path])

        return destination_path


if __name__ == "__main__":
    def usagequit(program):
        print >>sys.stderr, 'Usage: %s [options]\n' % program
        print >>sys.stderr, 'Options:'
        print >>sys.stderr, '-i, --input <path>     image to convert'
        print >>sys.stderr, '-o, --output <path>    output file name (qcow2)'
        print >>sys.stderr, '-n, --name <name>      glance name (if uploading)'
        print >>sys.stderr, '-u, --upload           enable glance upload'
        print >>sys.stderr, '-s, --sysprep          sysprep windows image'
        print >>sys.stderr, '-d, --debug <1-5>      debuglevel (5 is verbose)'
        sys.exit(1)

    image = None
    output = None
    name = None
    upload = False
    sysprep = False
    debuglevel = 2

    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'i:o:n:usd:', ['input=', 'output=', 'name=',
                                         'upload', 'sysprep',
                                         'debug='])
    except getopt.GetoptError as err:
        print str(err)
        usagequit(sys.argv[0])

    for o, a in opts:
        if o in ['-i', '--input']:
            image = a
        elif o in ['-o', '--output']:
            output = a
        elif o in ['-n', '--name']:
            name = a
        elif o in ['-u', '--upload']:
            upload = True
        elif o in ['-s', '--sysprep']:
            sysprep = True
        elif o in ['-d', '--debug']:
            a = int(a)
            a = a if a < 5 else 4
            a = a if a > 0 else 1
            debuglevel = a
        else:
            print >>sys.stderr, 'Unhandled option: %s' % o

    logging.basicConfig(level=[None,
                               logging.ERROR,
                               logging.WARNING,
                               logging.INFO,
                               logging.DEBUG][debuglevel])

    if image is None:
        print >>sys.stderr, 'input image (-i, --image) required'
        sys.exit(1)

    if output is None:
        if '.' in image:
            base = image.rsplit('.', 1)[0]
            output = '%s.qcow2' % base
        else:
            output = '%s.qcow2' % image

    if name is None:
        name = os.path.basename(image).rsplit('.',1)[0]

    if upload:
        for key in ['OS_USERNAME', 'OS_PASSWORD', 'OS_TENANT_NAME',
                    'OS_AUTH_URL']:
            fail = False
            if key not in os.environ:
                fail = True
                print >>sys.stderr, 'missing nova environment (%s)' % key

        if fail is True:
            sys.exit(1)

    # let's do this thing.
    working_image_path = image

    # the function to inspect image format is curiously
    # absent from python-guestfs, so we'll use the poor-man's
    # image detection method...
    if not image.lower().endswith('.qcow2'):
        logging.getLogger().info('Converting to qcow2 format')
        i = Image(image, readonly=True)
        working_image_path = i.to_qcow2(destination_path=output)
        i = None

    # image is in qcow2 now, let's do the v2v migration
    logging.getLogger().info('Performing v2v actions')
    conv = Image(working_image_path, readonly=False)
    conv.convert()
    conf = None

    # now we need to upload the thing.
    if upload:
        logging.getLogger().info('Performing image upload')
        glance_upload(working_image_path, name=name)
