# VMDK Conversion

There are generally two pieces to the VMDK conversion, the first being
image format conversions, and the second being making the resulting
image bootable on OpenStack.

Our biased installation of OpenStack is based on KVM, so we'll target
that for a conversion.

In this directory is a shell script (convert.sh) that will do
conversion from vmdk to qcow2 with no other effort at conversion.
This approach will work for pretty much all the linux, as most linux
from this generation have proper kvm/virtio drivers and whatnot.  So
just converting format to qcow2 is probably enough to boot a windows
box on OpenStack.

Windows, of course, is a different train wreck.  For some reason,
Microsoft hasn't seen fit to add the KVM virtio drivers to the Windows
base install (why not?!?!), so it is necessary to inject those drivers
into the converted image.

The script convert.py is a start on that process.  It is not yet
complete, but is sufficient to inject drivers and make a system image
bootable.  It does not yet do glance uploads.
