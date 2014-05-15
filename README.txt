Installation (linux):
1 - Make sure libusb1 is installed (not libusb 0.1): "sudo apt-get install libusb-1.0-0-dev"
2 - Install python libusb bindings: "pip install --user libusb1"
3 - Copy 91-vybrid-flash.rules to /etc/udev/rules.d/ and restart udev

Run:

For an empty flash:
fslflash.py --bootstrap u-boot.imx --uboot u-boot.nand --kernel uImage --rootfs rootfs.jffs2 --userdata userdata.jffs2

With recent u-boot already installed:
fslflash.py --uboot u-boot.nand --kernel uImage --rootfs rootfs.jffs2 --userdata userdata.jffs2

Specify only the partitions that need to be flashed.

You can (and probably should) run these commands before plugging in the vybrid, the script will wait for the device.

