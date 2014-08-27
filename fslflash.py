#!/usr/bin/env python3

import argparse
import itertools
import struct
import sys
import time

import libusb1
import usb1

# From mtdparts, update when flash partitions change.
# Unfortunately you can't just give a partition name when flashing, have to know the offset

offsets = { 'uboot': '0x00040000', 'kernel-image': '0x00100000', 'user-data': '0x00500000', 'rootfs': '0x08000000' }

class CBW(object):
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


class CSW(object):
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


class UTP(object):
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


class Vybrid(object):
    VENDOR_ID = 0x066f
    PRODUCT_ID = 0x37ff

    UTP_POLL = 0
    UTP_EXEC = 1
    UTP_GET  = 2
    UTP_PUT  = 3

    def __init__(self, ctx):
        self.tag = itertools.count(start=1)
        self.ctx = ctx

        self.handle = self.ctx.openByVendorIDAndProductID(Vybrid.VENDOR_ID, Vybrid.PRODUCT_ID)

        if self.handle is None:
            print('Waiting for Vybrid...')

        while self.handle is None:
            time.sleep(1)
            self.handle = self.ctx.openByVendorIDAndProductID(Vybrid.VENDOR_ID, Vybrid.PRODUCT_ID)

        print('Vybrid attached')
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)

    def do_ping(self):
        utp = UTP(UTP.UTP_POLL, next(self.tag))
        cbw = CBW(utp.pack(), next(self.tag))
        self.handle.bulkWrite(1, cbw.pack())
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def do_exec(self, cmd):
        print('Executing "{0}" on Vybrid'.format(cmd))
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

    def load_image(self, partition, imagefilename):
        print('\nLoading partition {0} from {1}'.format(partition, imagefilename))
        imagedata = open(imagefilename, 'rb').read()

        self.do_exec('ubootcmd nand erase.part {0}'.format(partition))
        self.do_ping()
        self.do_exec('pipenand addr={0}'.format(offsets[partition]))

        offset = 0
        num_chunks = len(imagedata)/65536
        if len(imagedata) % 65536 != 0:
            num_chunks += 1
        while offset < len(imagedata):
            chunk_size = min(65536, len(imagedata) - offset)
            sys.stdout.write('Uploading firmware image chunk {0}/{1}\r'.format(int(offset/65536+1), int(num_chunks)))
            sys.stdout.flush()
            self.do_ping()
            self.do_put(imagedata, offset, chunk_size)
            offset += chunk_size
        print('')

class Bootstrap(object):
    VENDOR_ID  = 0x15a2
    PRODUCT_ID = 0x006a

    READ_REGISTER  = 0x0101
    WRITE_REGISTER = 0x0202
    WRITE_FILE     = 0x0404
    ERROR_STATUS   = 0x0505
    DCD_WRITE      = 0x0A0A
    JUMP_ADDRESS   = 0x0B0B

    def __init__(self, ctx):
        self.ctx = ctx

        # If the flash is empty or bootrom can't boot, the bootrom will go 
        # into Serial Download Protocol mode and present itself as a USBHID
        # device at 15a2:006a.  Otherwise, uboot presents itself as a USB 
        # Mass Storage device at 066f:37ff for flashing.
        self.handle = self.ctx.openByVendorIDAndProductID(Bootstrap.VENDOR_ID, Bootstrap.PRODUCT_ID)
        while self.handle is None:
            time.sleep(1)
            self.handle = self.ctx.openByVendorIDAndProductID(Bootstrap.VENDOR_ID, Bootstrap.PRODUCT_ID)

        print('Vybrid bootstrap mode attached')
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)

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

    def load_image(self, image):
        imagedata = open(image, 'rb').read()
        offset = 0
        chunk_size = 1024
        self.do_cmd(Bootstrap.WRITE_FILE, 0x3f001000, len(imagedata))
        while offset < len(imagedata):
            sys.stdout.write('Uploading bootstrap image chunk {0}/{1}\r'.format(offset/chunk_size + 1, len(imagedata)/chunk_size))
            sys.stdout.flush()
            self.do_write(imagedata, offset, chunk_size)
            offset += chunk_size
        hab = self.handle.interruptRead(1, 5)
        print('\nReport ID {0} received: 0x{1:08x}'.format(*struct.unpack('>BI', hab)))
        complete = self.handle.interruptRead(1, 65)
        print('Report ID {0} received: 0x{1:08x}'.format(*struct.unpack('>BI60s', complete)))

        print('\nJumping to bootstrap image')
        self.do_cmd(Bootstrap.JUMP_ADDRESS, 0x3f001000, 0)
        hab = self.handle.interruptRead(1, 5)
        print('Report ID {0} received: 0x{1:08x}'.format(*struct.unpack('>BI', hab)))
        try:
            complete = self.handle.interruptRead(1, 65)
            print('Report ID {0} received: 0x{1:08x}'.format(*struct.unpack('>BI60s', complete)))
        except libusb1.USBError:
            # The second interrupt read fails unless there was an error jumping..
            pass

    def close(self):
        try:
            self.handle.close()
        except libusb1.USBError:
            pass

parser = argparse.ArgumentParser(description='Tool for flashing Freescale Vybrid SoM NAND Flash')
parser.add_argument('--bootstrap', help='u-boot.imx boostrap loader to download into memory')
parser.add_argument('--uboot',     help='u-boot nand image to flash for uboot partition')
parser.add_argument('--kernel',    help='kernel uImage file to flash for kernel-image partition')
parser.add_argument('--rootfs',    help='rootfs jffs2 file to flash for rootfs partition')
parser.add_argument('--userdata',  help='config jfss2 file to flash for user-data partition')
parser.add_argument('--reboot',    help='If set, reboot after flashing specified partitions', action='store_true')

args = parser.parse_args()

ctx = usb1.USBContext()

if args.bootstrap != None:
    bootstrap = Bootstrap(ctx)
    bootstrap.load_image(args.bootstrap)
    bootstrap.close()

vybrid = Vybrid(ctx)

if args.uboot != None:
    vybrid.do_exec('ubootcmd nand erase.part fcb-area')
    vybrid.do_ping()
    vybrid.load_image('uboot', args.uboot)
    vybrid.do_exec('nandinit addr={0}'.format(offsets['uboot']))
    vybrid.do_ping()

if args.kernel != None:
    vybrid.load_image('kernel-image', args.kernel)

if args.rootfs != None:
    vybrid.load_image('rootfs', args.rootfs)

if args.userdata != None:
    vybrid.load_image('user-data', args.userdata)

if args.reboot:
    try:
        vybrid.do_exec('ubootcmd reset')
    except libusb1.USBError:
        # We get a USB error because there's no response to the reset..
        pass
else:
    vybrid.do_exec('$ !')

