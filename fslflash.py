#!/usr/bin/env python

import itertools
import struct
import sys

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
    UTP_POLL = 0
    UTP_EXEC = 1
    UTP_GET  = 2
    UTP_PUT  = 3

    def __init__(self):
        self.ctx = usb1.USBContext()
        self.handle = self.ctx.openByVendorIDAndProductID(0x066f, 0x37ff)
        self.tag = itertools.count(start=1)
        if self.handle is None:
            raise IOError('Failed to find Vybrid')
        self.handle.setAutoDetachKernelDriver(True)
        self.handle.claimInterface(0)

    def do_ping(self):
        print('Sending UTP_POLL to Vybrid')
        utp = UTP(UTP.UTP_POLL, self.tag.next())
        cbw = CBW(utp.pack(), self.tag.next())
        self.handle.bulkWrite(1, cbw.pack())
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def do_exec(self, cmd):
        print('Executing "{0}" on Vybrid'.format(cmd))
        utp = UTP(UTP.UTP_EXEC, self.tag.next())
        cbw = CBW(utp.pack(), self.tag.next(), len(cmd))
        self.handle.bulkWrite(1, cbw.pack())
        self.handle.bulkWrite(1, cmd)
        csw = CSW.unpack(self.handle.bulkRead(1, 13))

    def do_put(self, data, offset, length):
        print('Sending {0} bytes to Vybrid at offset {1}'.format(length, offset))
        utp = UTP(UTP.UTP_PUT, self.tag.next(), offset)
        cbw = CBW(utp.pack(), self.tag.next(), length)
        self.handle.bulkWrite(1, cbw.pack())
        self.handle.bulkWrite(1, data[offset:offset+length])
        csw = CSW.unpack(self.handle.bulkRead(1, 13))


if __name__ == '__main__':
    try:
        partition = sys.argv[1]
        filename = sys.argv[2]
    except:
        print('\nUsage:\n\t{0} partition filename\n'.format(sys.argv[0]))
        sys.exit(1)

    if not offsets.has_key(partition):
        print('\nNo such partition {0}\n'.format(partition))

    filedata = open(filename).read()

    vybrid = Vybrid()
    vybrid.do_ping()

    if partition == 'uboot':
        vybrid.do_exec('ubootcmd nand erase.part fcb-area')

    vybrid.do_exec('ubootcmd nand erase.part {0}'.format(partition))
    vybrid.do_ping()
    vybrid.do_exec('pipenand addr={0}'.format(offsets[partition]))

    offset = 0
    while offset < len(filedata):
        chunk_size = min(65536, len(filedata) - offset)
        vybrid.do_ping()
        vybrid.do_put(filedata, offset, chunk_size)
        offset += chunk_size

    if partition == 'uboot':
        vybrid.do_exec('nandinit addr={0}'.format(offsets[partition]))

    vybrid.do_exec('$ !')

