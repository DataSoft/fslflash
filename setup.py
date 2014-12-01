from distutils.core import setup

setup(name='fslflash',
      version='1.0',
      description='Freescale Vybrid flashing utility',
      packages=['fsl'],
      requires=['libusb1', 'usb1', 'PyQt5'],
      scripts=['fslflash.py', 'fslflashgui.py'],
      )

