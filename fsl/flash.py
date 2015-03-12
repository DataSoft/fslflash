import binascii
import datetime
import itertools
import struct
import sys
import time

import libusb1
import usb1

# From mtdparts, update when flash partitions change.
# Unfortunately you can't just give a partition name when flashing, have to know the offset

OFFSETS = { 'uboot': '0x00040000', 'uboot-var': '0x000C0000', 'fdt': '0x000E0000', 'kernel-image': '0x00100000', 'user-data': '0x00900000', 'rootfs': '0x01100000' }
BOOTSTRAP_ADDR = 0x3f408000
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
            self.load_image(partition, imagedata)

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
            self.load_image(imagedata)

    def load_image(self, imagedata):
        offset = 0
        chunk_size = 1024
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

    def close(self):
        try:
            self.handle.close()
        except libusb1.USBError:
            pass

def flash(bootstrap_file=None, uboot_file=None, fdt_file=None, kernel_file=None, rootfs_file=None, serial=None, reboot=False, statusio=sys.stdout):
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
                if not bootstrap_file:
                    raise RuntimeError('Vybrid in bootrom mode, no bootstrap file specified')
                handle = device.open()
                bootstrap = Bootstrap(handle, statusio)
                bootstrap.load_file(bootstrap_file)
                bootstrap.close()
                break
            if device.getVendorID() == Vybrid.VENDOR_ID and device.getProductID() == Vybrid.PRODUCT_ID:
                handle = device.open()
                vybrid = Vybrid(handle, statusio)
                break
        if not vybrid:
            time.sleep(1)
    statusio.write('Found Vybrid\n')

    if uboot_file:
        vybrid.do_exec('ubootcmd nand erase.part fcb-area')
        vybrid.do_ping()
        vybrid.do_exec('ubootcmd nand erase.part uboot-var')
        vybrid.do_ping()
        vybrid.load_file('uboot', uboot_file)
        vybrid.do_exec('nandinit addr={0}'.format(OFFSETS['uboot']))
        vybrid.do_ping()

    if serial:
        serialtext = '{0:06d}'.format(serial)
        macaddr = '{0}:{1}:{2}'.format(serialtext[:2], serialtext[2:4], serialtext[4:])
        dt = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
        vybrid.do_exec('ubootcmd mac id')
        vybrid.do_exec('ubootcmd mac num {0}'.format(serialtext))
        # Assign 4 mac addresses.
        # 0 and 1 go to fec0 and fec1 if used (fec1 used on RAP)
        # 2 and 3 go to the USB gadget host and dev side
        vybrid.do_exec('ubootcmd mac ports 4')
        vybrid.do_exec('ubootcmd mac 0 68:83:00:{0}'.format(macaddr))
        vybrid.do_exec('ubootcmd mac 1 68:83:01:{0}'.format(macaddr))
        vybrid.do_exec('ubootcmd mac 2 68:83:02:{0}'.format(macaddr))
        vybrid.do_exec('ubootcmd mac 3 68:83:03:{0}'.format(macaddr))
        vybrid.do_exec('ubootcmd mac date {0}'.format(dt))
        vybrid.do_exec('ubootcmd mac save')

    if fdt_file:
        vybrid.load_file('fdt', fdt_file)

    if kernel_file:
        vybrid.load_file('kernel-image', kernel_file)

    if rootfs_file:
        vybrid.load_file('rootfs', rootfs_file)

    if reboot:
        try:
            vybrid.do_exec('ubootcmd reset')
        except libusb1.USBError:
            # We get a USB error because there's no response to the reset..
            pass
    else:
        vybrid.do_exec('$ !')
