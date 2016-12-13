from distutils.core import setup

setup(name='fslflash',
      version='2.1.3',
      description='Freescale Vybrid flashing utility',
      author='Aaron Brice',
      author_email='aaron.brice@datasoft.com',
      packages=['fsl'],
      requires=['libusb1', 'usb1', 'PyQt5'],
      scripts=['fslflash', 'fslflashgui'],
      data_files=[('/lib/udev/rules.d/', ['data/91-vybrid-flash.rules'])]
      )

