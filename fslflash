#!/usr/bin/env python3

import argparse
from fsl import flash

parser = argparse.ArgumentParser(description='Tool for flashing Freescale Vybrid SoM NAND Flash')
parser.add_argument('--bootstrap', help='u-boot.imx boostrap loader to download into memory')
parser.add_argument('--uboot',     help='u-boot nand image to flash for uboot partition')
parser.add_argument('--ubootenv',  help='u-boot environment template for setting the serial number')
parser.add_argument('--fdt',       help='flattened device tree file to flash for fdt partition')
parser.add_argument('--kernel',    help='kernel uImage file to flash for kernel-image partition')
parser.add_argument('--rootfs',    help='rootfs jffs2 file to flash for rootfs partition')
parser.add_argument('--userdata',  help='config jfss2 file to flash for user-data partition')
parser.add_argument('--serial',    help='serial number of device', type=int)
parser.add_argument('--reboot',    help='If set, reboot after flashing specified partitions', action='store_true')

args = parser.parse_args()

flash(args.bootstrap, args.uboot, args.ubootenv, args.fdt, args.kernel, args.rootfs, args.userdata, args.serial, args.reboot)

