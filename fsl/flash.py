import binascii
import datetime
import itertools
import os
import shutil
import struct
import sys
import tempfile
import time
import zipfile

import libusb1
import usb1

# From mtdparts, update when flash partitions change.
# Unfortunately you can't just give a partition name when flashing, have to know the offset

OFFSETS = { 'fcb-area': '0x00000000', 'uboot': '0x00040000', 'uboot-var': '0x000C0000', 'fdt': '0x000E0000', 'kernel-image': '0x00100000', 'user-data': '0x00900000', 'rootfs': '0x01100000' }
#BOOTSTRAP_ADDR = 0x3f408000
BOOTSTRAP_ADDR = 0x3f4078e8
UBOOTENV_SIZE = 0x20000

class CBW:
    SIGNATURE = 0x43425355

    def __init__(self, cmd, tag, datalen=0, is_data_in=False, lun=0):
        self.cmd = cmd
        self.tag = tag
        self.datalen = datalen
        self.direction = 0x80 if is_data_in else 0x00
        self.lun = lun

    def __str__(self):
        return 'CBW -- tag: 0x{0:08x}, transfer length: 0x{1:08x}, flags: 0x{2:02x}, lun: 0x{3:02x}, cb_length: 0x{4:02x}, cb: 0x{5}'.format(
                self.tag, self.datalen, self.direction, self.lun, len(self.cmd), ''.join('{0:02x}'.format(ord(c)) for c in self.cmd))

    def pack(self):
        cbw = struct.pack('<IIIBBB', CBW.SIGNATURE, self.tag, self.datalen, self.direction, self.lun, len(self.cmd))
        cbw += self.cmd
        return cbw

    @classmethod
    def unpack(klass, data):
        (signature, tag, datalen, direction, lun, cmdlen, cmd) = struct.unpack('<IIIBBB16s', data)
        if signature != CBW.SIGNATURE:
            raise IOError('Received bad CBW data')
        is_data_in = bool(direction & 0x80)
        return klass(cmd, tag, datalen, is_data_in, lun)


class CSW:
    SIGNATURE = 0x53425355

    def __init__(self, tag, residue, status):
        self.tag = tag
        self.residue = residue
        self.status = status

    def __str__(self):
        return 'CSW -- tag: 0x{0:08x}, residue: 0x{1:08x}, status: 0x{2:02x}'.format(self.tag, self.residue, self.status)

    def pack(self):
        return struct.pack('<IIIB', CSW.SIGNATURE, self.tag, self.residue, self.status)

    @classmethod
    def unpack(klass, data):
        (signature, tag, residue, status) = struct.unpack('<IIIB', data)
        if signature != CSW.SIGNATURE:
            raise IOError('Received bad CSW data')
        return klass(tag, residue, status)


class UTP:
    UTP_POLL = 0
    UTP_EXEC = 1
    UTP_GET  = 2
    UTP_PUT  = 3

    def __init__(self, msg_type, tag, param=0):
        self.msg_type = msg_type
        self.tag = tag
        self.param = param

    def __str__(self):
        return 'UTP -- type: 0x{0:02x}, tag: 0x{1:08x}, param: 0x{2:016x}'.format(self.msg_type, self.tag, self.param)

    def pack(self):
        return struct.pack('>BBIQH', 0xF0, self.msg_type, self.tag, self.param, 0)

    @classmethod
    def unpack(klass, data):
        (_, msg_type, tag, param) = struct.unpack('>BBIQ', data)
        return klass(msg_type, tag, param)


class Vybrid:
    VENDOR_ID = 0x066f
    PRODUCT_ID = 0x37ff

    UTP_POLL = 0
    UTP_EXEC = 1
    UTP_GET  = 2
    UTP_PUT  = 3

    def __init__(self, handle, statusio=sys.stdout):
        self.tag = itertools.count(start=1)
        self.handle = handle
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)
        self.statusio = statusio

    def do_ping(self):
        utp = UTP(UTP.UTP_POLL, next(self.tag))
        cbw = CBW(utp.pack(), next(self.tag))
        self.handle.bulkWrite(1, cbw.pack())
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def do_exec(self, cmd):
        self.statusio.write('Executing "{0}" on Vybrid\n'.format(cmd))
        utp = UTP(UTP.UTP_EXEC, next(self.tag))
        cbw = CBW(utp.pack(), next(self.tag), len(cmd))
        self.handle.bulkWrite(1, cbw.pack())
        self.handle.bulkWrite(1, cmd.encode())
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def do_put(self, data, offset, length):
        utp = UTP(UTP.UTP_PUT, next(self.tag), offset)
        cbw = CBW(utp.pack(), next(self.tag), length)
        self.handle.bulkWrite(1, cbw.pack())
        self.handle.bulkWrite(1, data[offset:offset+length])
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def load_file(self, partition, imagefilename):
        self.statusio.write('\nLoading partition {0} from {1}\n'.format(partition, imagefilename))
        with open(imagefilename, 'rb') as f:
            imagedata = f.read()
            return self.load_image(partition, imagedata)

    def load_image(self, partition, imagedata):
        self.do_exec('ubootcmd nand erase.part {0}'.format(partition))
        self.do_ping()
        self.do_exec('pipenand addr={0}'.format(OFFSETS[partition]))

        offset = 0
        num_chunks = len(imagedata)//65536
        if len(imagedata) % 65536 != 0:
            num_chunks += 1
        while offset < len(imagedata):
            chunk_size = min(65536, len(imagedata) - offset)
            self.statusio.write('Uploading firmware image chunk {0}/{1}\r'.format(offset//65536+1, num_chunks))
            self.statusio.flush()
            self.do_ping()
            self.do_put(imagedata, offset, chunk_size)
            offset += chunk_size
        self.statusio.write('\n')
        return True

    def load_uboot(self, uboot_file):
        self.do_exec('ubootcmd nand erase.part fcb-area')
        self.do_ping()
        self.do_exec('ubootcmd nand erase.part uboot-var')
        self.do_ping()
        self.load_file('uboot', uboot_file)
        self.do_exec('nandinit addr={0}'.format(OFFSETS['uboot']))
        self.do_ping()

    def load_bcb(self, bcb_file):
        self.load_file('fcb-area', bcb_file)

    def set_serial(self, serial):
        serialtext = '{0:06d}'.format(serial)
        macaddr = '{0}:{1}:{2}'.format(serialtext[:2], serialtext[2:4], serialtext[4:])
        dt = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
        self.do_exec('ubootcmd mac id')
        self.do_exec('ubootcmd mac num {0}'.format(serialtext))
        # Assign 4 mac addresses.
        # 0 and 1 go to fec0 and fec1 if used (fec1 used on RAP)
        # 2 and 3 go to the USB gadget host and dev side
        self.do_exec('ubootcmd mac ports 4')
        self.do_exec('ubootcmd mac 0 68:83:00:{0}'.format(macaddr))
        self.do_exec('ubootcmd mac 1 68:83:01:{0}'.format(macaddr))
        self.do_exec('ubootcmd mac 2 68:83:02:{0}'.format(macaddr))
        self.do_exec('ubootcmd mac 3 68:83:03:{0}'.format(macaddr))
        self.do_exec('ubootcmd mac date {0}'.format(dt))
        self.do_exec('ubootcmd mac save')

    def close(self):
        self.do_exec('$ !')

    def reboot(self):
        try:
            self.do_exec('ubootcmd reset')
        except libusb1.USBError:
            # We get a USB error because there's no response to the reset..
            pass

class Bootstrap:
    VENDOR_ID = 0x15a2
    PRODUCT_ID = 0x006a

    READ_REGISTER  = 0x0101
    WRITE_REGISTER = 0x0202
    WRITE_FILE     = 0x0404
    ERROR_STATUS   = 0x0505
    DCD_WRITE      = 0x0A0A
    JUMP_ADDRESS   = 0x0B0B

    def __init__(self, handle, statusio=sys.stdout):
        self.handle = handle
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)
        self.statusio = statusio

    def do_cmd(self, type, address, count):
        # SDP command, see page 895 of Vybrid Reference Manual
        data = struct.pack('>BHIBIIB', 1, type, address, 0, count, 0, 0)
        # Request = 0x09 (SET_REPORT), value = 0x0201 (ReportID 1, ReportType 2 (output)), index = 0 (interface)
        self.handle.controlWrite(
                libusb1.LIBUSB_ENDPOINT_OUT|libusb1.LIBUSB_TYPE_CLASS|libusb1.LIBUSB_RECIPIENT_INTERFACE,
                0x09, 0x0201, 0x0, data)

    def do_write(self, data, offset, length):
        chunk = b'\x02' + data[offset:offset+length]
        # Request = 0x09 (SET_REPORT), value = 0x0202 (ReportID 2, ReportType 2 (output)), index = 0 (interface)
        self.handle.controlWrite(
                libusb1.LIBUSB_ENDPOINT_OUT|libusb1.LIBUSB_TYPE_CLASS|libusb1.LIBUSB_RECIPIENT_INTERFACE,
                0x09, 0x0202, 0x0, chunk)

    def load_file(self, imagefilename):
        with open(imagefilename, 'rb') as f:
            imagedata = f.read()
            return self.load_image(imagedata)

    def load_image(self, imagedata):
        offset = 0
        chunk_size = 1024
        self.statusio.write('\nUsing bootstrap address {0:08x}\n'.format(BOOTSTRAP_ADDR))
        self.do_cmd(Bootstrap.WRITE_FILE, BOOTSTRAP_ADDR, len(imagedata))
        while offset < len(imagedata):
            self.statusio.write('Uploading bootstrap image chunk {0}/{1}\r'.format(offset//chunk_size + 1, len(imagedata)//chunk_size))
            self.statusio.flush()
            self.do_write(imagedata, offset, chunk_size)
            offset += chunk_size
        hab = self.handle.interruptRead(1, 5)
        self.statusio.write('\nReport ID {0} received: 0x{1:08x}\n'.format(*struct.unpack('>BI', hab)))
        complete = self.handle.interruptRead(1, 65)
        self.statusio.write('Report ID {0} received: 0x{1:08x}\n'.format(*struct.unpack('>BI60s', complete)))

        self.statusio.write('\nJumping to bootstrap image\n')
        self.do_cmd(Bootstrap.JUMP_ADDRESS, BOOTSTRAP_ADDR, 0)
        hab = self.handle.interruptRead(1, 5)
        self.statusio.write('Report ID {0} received: 0x{1:08x}\n'.format(*struct.unpack('>BI', hab)))
        self.statusio.write('Waiting for Vybrid...\n')
        try:
            complete = self.handle.interruptRead(1, 65)
            self.statusio.write('Report ID {0} received: 0x{1:08x}\n'.format(*struct.unpack('>BI60s', complete)))
            raise RuntimeError('Bootstrap image does not seem to be bootable..')
        except struct.error:
            pass
        except libusb1.USBError:
            # The second interrupt read fails unless there was an error jumping..
            pass
        return True

    def close(self):
        try:
            self.handle.close()
        except libusb1.USBError:
            pass

class DFU:
    CLASS_TUPLE = (libusb1.LIBUSB_CLASS_APPLICATION, 0x01)
    REQUEST_TYPE = libusb1.LIBUSB_TYPE_CLASS | libusb1.LIBUSB_RECIPIENT_INTERFACE

    DETACH = 0x00
    DNLOAD = 0x01
    UPLOAD = 0x02
    GET_STATUS = 0x03
    CLR_STATUS = 0x04
    GET_STATE = 0x05
    ABORT = 0x06
    COMMAND = 0x10

    STATUS_DICT = {
        0x00: 'No error condition is present.',
        0x01: 'File is not targeted for use by this device.',
        0x02: 'File is for this device but fails some vendor-specific verification test.',
        0x03: 'Device is unable to write memory.',
        0x04: 'Memory erase function failed.',
        0x05: 'Memory erase check failed.',
        0x06: 'Program memory function failed.',
        0x07: 'Programmed memory failed verification.',
        0x08: 'Cannot program memory due to received address that is our of range.',
        0x09: 'Received DFU_DNLOAD with wLength = 0, but device does not think it has all of the data yet.',
        0x0a: "Device's firmware is corrupt. It cannot return to run-time (non-DFU) operations.",
        0x0b: 'iString indicates a vendor-specific error.',
        0x0c: 'Device detected unexpected USB reset signaling.',
        0x0d: 'Device detected unexpected power on reset.',
        0x0e: 'Something went wrong, but the device does not know what is was.',
        0x0f: 'Device stalled a unexpected request.',
    }

    STATE_DICT = {
        0x00: 'APP_IDLE',
        0x01: 'APP_DETACH',
        0x02: 'DFU_IDLE',
        0x03: 'DFU_DNLOAD-SYNC',
        0x04: 'DFU_DNBUSY',
        0x05: 'DFU_DNLOAD-IDLE',
        0x06: 'DFU_MANIFEST-SYNC',
        0x07: 'DFU_MANIFEST',
        0x08: 'DFU_MANIFEST-WAIT-RESET',
        0x09: 'DFU_UPLOAD-IDLE',
        0x0a: 'DFU_ERROR',
    }

    STATE_APP_IDLE = 0
    STATE_APP_DETACH = 1
    STATE_DFU_IDLE = 2
    STATE_DFU_DNLOAD_SYNC = 3
    STATE_DFU_DNBUSY = 4
    STATE_DFU_DNLOAD_IDLE = 5
    STATE_DFU_MANIFEST_SYNC = 6
    STATE_DFU_MANIFEST = 7
    STATE_DFU_MANIFEST_WAIT_RESET = 8
    STATE_DFU_UPLOAD_IDLE = 9
    STATE_DFU_ERROR = 10

    def __init__(self, handle, statusio=sys.stdout):
        self.handle = handle
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)
        self.statusio = statusio
        self.partition_alt = {}
        # Descriptor type 0x21 is used for DFU Functional Descriptor or maybe HID descriptor..
        # libusb1 getExtra() is returning empty so manually send the control read request to
        # retrieve functional descriptor 0x21 (DFU spec 4.1.3)
        # Send GET_DESCRIPTOR request for descriptor 0x21, interface 0, length of 9 bytes
        functional = handle.controlRead(libusb1.LIBUSB_ENDPOINT_IN, 
                libusb1.LIBUSB_REQUEST_GET_DESCRIPTOR, (0x21 << 8), 0, 9, timeout=5000)
        # See 4.1.3 for details, all we care about for now is wTransferSize
        (_, _, self.transfer_size, _) = struct.unpack('<BHHH', functional[2:])
        for setting in handle.getDevice().iterSettings():
            if setting.getClassTuple() == (libusb1.LIBUSB_CLASS_APPLICATION, 0x01):
                index = setting.getDescriptor()
                desc = handle.getASCIIStringDescriptor(index)
                self.partition_alt[desc] = setting.getAlternateSetting()

    def control_write(self, bRequest, wValue, data):
        self.handle.controlWrite(DFU.REQUEST_TYPE, bRequest, wValue, 0, data, timeout=5000)

    def control_read(self, bRequest, wValue, length):
        return self.handle.controlRead(DFU.REQUEST_TYPE, bRequest, wValue, 0, length, timeout=5000)

    def do_exec(self, cmd):
        print('Sending cmd: {}'.format(cmd))
        try:
            self.control_write(DFU.COMMAND, 0, cmd.encode() + b'\0')
        except usb1.USBErrorPipe:
            pass

    def do_dnload(self, block_num, block_data):
        self.control_write(DFU.DNLOAD, block_num, block_data)

    def get_status(self):
        status = self.control_read(DFU.GET_STATUS, 0, 6)
        bStatus = status[0]
        bwPollTimeout = status[1] | (status[2] << 8) | (status[3] << 16)
        bState = status[4]
        return (bStatus, bwPollTimeout, bState)

    def check_idle(self):
        (status, timeout, state) = self.get_status()
        if state == DFU.STATE_DFU_IDLE:
            return True
        self.statusio.write('\nDFU device is in {} state, expected DFU_IDLE state.  Status: {}\n'.format(DFU.STATE_DICT[state], DFU.STATUS_DICT[status]))
        self.statusio.flush()
        return False

    def check_dnload(self):
        (status, timeout, state) = self.get_status()
        while state == DFU.STATE_DFU_DNBUSY:
            time.sleep(timeout / 1000)
            (status, timeout, state) = self.get_status()
        if state == DFU.STATE_DFU_DNLOAD_IDLE:
            return True
        self.statusio.write('\nDFU device is in {} state, expected DFU_DNLOAD-IDLE or DFU_DNBUSY state.  Status: {}\n'.format(DFU.STATE_DICT[state], DFU.STATUS_DICT[status]))
        self.statusio.flush()
        return False

    def complete_dnload(self):
        (status, timeout, state) = self.get_status()
        while state in (DFU.STATE_DFU_MANIFEST, DFU.STATE_DFU_MANIFEST_SYNC):
            time.sleep(timeout / 1000)
            (status, timeout, state) = self.get_status()
        if state == DFU.STATE_DFU_IDLE:
            return True
        self.statusio.write('\nDFU device is in {} state, expected DFU_IDLE.  Status: {}\n'.format(DFU.STATE_DICT[state], DFU.STATUS_DICT[status]))
        self.statusio.flush()
        return False

    def load_file(self, partition, imagefilename):
        self.statusio.write('\nLoading partition {0} from {1}\n'.format(partition, imagefilename))
        with open(imagefilename, 'rb') as f:
            imagedata = f.read()
            return self.load_image(partition, imagedata)

    def load_image(self, partition, imagedata):
        self.handle.setInterfaceAltSetting(0, self.partition_alt[partition])
        if not self.check_idle():
            return False
        offset = 0
        num_chunks = len(imagedata)//self.transfer_size
        old_percent = None
        if len(imagedata) % self.transfer_size != 0:
            num_chunks += 1
        while offset < len(imagedata):
            chunk_size = min(self.transfer_size, len(imagedata) - offset)
            chunk_index = offset//self.transfer_size
            percent = chunk_index * 100 // num_chunks
            if percent != old_percent:
                self.statusio.write('Uploading firmware image {}%\r'.format(percent))
                self.statusio.flush()
                old_percent = percent
            chunk = imagedata[offset:offset+chunk_size]
            offset += chunk_size
            self.do_dnload(chunk_index, chunk)
            if not self.check_dnload():
                return False
        # 0 length download request to finish
        self.do_dnload(num_chunks, b'')
        if not self.complete_dnload():
            return False
        self.statusio.write('Uploading firmware image 100%\n\n')
        self.statusio.flush()
        return True

    def load_uboot(self, imagefilename):
        self.do_exec('nand erase.part vf-bcb')
        self.do_exec('nand erase.part u-boot-env')
        self.load_file('u-boot', imagefilename)
        self.do_exec('writebcb {0}'.format(OFFSETS['uboot']))

    def load_bcb(self, imagefilename):
        return self.load_file('vf-bcb', imagefilename)

    def set_serial(self, serial):
        serialtext = '{0:06d}'.format(serial)
        macaddr = '{0}:{1}:{2}'.format(serialtext[:2], serialtext[2:4], serialtext[4:])
        dt = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
        self.do_exec('mac id')
        self.do_exec('mac num {0}'.format(serialtext))
        # Assign 4 mac addresses.
        # 0 and 1 go to fec0 and fec1 if used (fec1 used on RAP)
        # 2 and 3 go to the USB gadget host and dev side
        self.do_exec('mac ports 4')
        self.do_exec('mac 0 68:83:00:{0}'.format(macaddr))
        self.do_exec('mac 1 68:83:01:{0}'.format(macaddr))
        self.do_exec('mac 2 68:83:02:{0}'.format(macaddr))
        self.do_exec('mac 3 68:83:03:{0}'.format(macaddr))
        self.do_exec('mac date {0}'.format(dt))
        self.do_exec('mac save')

    def close(self):
        try:
            self.handle.close()
        except libusb1.USBError:
            pass

    def reboot(self):
        try:
            self.do_exec('reset')
        except libusb1.USBError:
            # We get a USB error because there's no response to the reset..
            pass
        self.close()

class FirmwareZip:
    def __init__(self, filename):
        partitions = {}
        self.zipfile = zipfile.ZipFile(filename, 'r')

    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp(prefix='fslflash')
        self.zipfile.extractall(self.tmpdir)

        with self.zipfile.open('manifest.txt') as manifest:
            for line in manifest:
                line = line.decode('UTF-8').rstrip()
                (partition, filename) = line.split(':')
                filename = os.path.join(self.tmpdir, filename)
                if partition == 'bootstrap':
                    self.bootstrap = filename
                elif partition == 'u-boot':
                    self.uboot = filename
                elif partition == 'vf-bcb':
                    self.bcb = filename
                elif partition == 'kernel-image':
                    self.kernel = filename
                elif partition == 'fdt':
                    self.fdt = filename
                elif partition == 'rootfs':
                    self.rootfs = filename
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

def get_vybrid(statusio, bootstrap_image=None):
    ctx = usb1.USBContext()
    vybrid = None
    statusio.write('Looking for Vybrid...\n')
    while not vybrid:
        devices = ctx.getDeviceList()
        # If the flash is empty or bootrom can't boot, the bootrom will go 
        # into Serial Download Protocol mode and present itself as a USBHID
        # device at 15a2:006a.  Otherwise, uboot presents itself as a USB 
        # Mass Storage device at 066f:37ff for flashing.
        for device in devices:
            if device.getVendorID() == Bootstrap.VENDOR_ID and device.getProductID() == Bootstrap.PRODUCT_ID:
                statusio.write('Found Vybrid in bootrom mode, loading bootstrap uboot\n')
                if not bootstrap_image:
                    raise RuntimeError('Vybrid in bootrom mode, no bootstrap file specified')
                handle = device.open()
                bootstrap = Bootstrap(handle, statusio)
                bootstrap.load_image(bootstrap_image)
                bootstrap.close()
                time.sleep(0.3)
                break
            if device.getVendorID() == Vybrid.VENDOR_ID and device.getProductID() == Vybrid.PRODUCT_ID:
                handle = device.open()
                if device[0][0][0].getClassTuple() == (0xfe, 0x01):
                    statusio.write('Found DFU Vybrid\n')
                    statusio.flush()
                    vybrid = DFU(handle, statusio)
                else:
                    statusio.write('Found UMS Vybrid\n')
                    statusio.flush()
                    vybrid = Vybrid(handle, statusio)
                break
        if not vybrid:
            time.sleep(0.1)
    return vybrid

def flash_package(zipfile, reboot=False, statusio=sys.stdout):
    with FirmwareZip(zipfile) as f:
        flash(f.bootstrap, f.bcb, f.uboot, f.fdt, f.kernel, f.rootfs, None, reboot, statusio)

def flash(bootstrap_file=None, bcb_file=None, uboot_file=None, fdt_file=None, kernel_file=None, rootfs_file=None, serial=None, reboot=False, statusio=sys.stdout):
    bootstrap_image = None
    if bootstrap_file:
        with open(bootstrap_file, 'rb') as f:
            bootstrap_image = f.read()

    vybrid = get_vybrid(statusio, bootstrap_image)

    if bcb_file:
        vybrid.load_bcb(bcb_file)

    # if u-boot provided, boot into it before continuing in case partitions have changed
    if uboot_file:
        vybrid.load_uboot(uboot_file)
        vybrid.reboot()
        time.sleep(0.3)
        vybrid = get_vybrid(statusio, bootstrap_image)

    if fdt_file:
        vybrid.load_file('fdt', fdt_file)

    if kernel_file:
        vybrid.load_file('kernel-image', kernel_file)

    if rootfs_file:
        vybrid.load_file('rootfs', rootfs_file)

    if serial:
        vybrid.set_serial(serial)

    if reboot:
        vybrid.reboot()
    else:
        vybrid.close()

