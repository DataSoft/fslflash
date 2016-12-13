import platform
from cx_Freeze import setup, Executable

options = {
    'build_exe': {
        'includes': 'atexit',
    }
}

base = None

arch, os = platform.architecture()
if os == 'WindowsPE':
    base = 'Win32GUI'
    if arch == '64bit':
        print('Using 64bit libraries')
        options['build_exe']['include_files'] = 'amd64/libusb-1.0.dll'
    else:
        print('Using 32bit libraries')
        options['build_exe']['include_files'] = 'x86/libusb-1.0.dll'

executables = [
    Executable('fslflash'),
    Executable('fslflashgui', base=base)
]

setup(name='fslflash',
      version='2.1.2',
      description='Freescale Vybrid flashing utility',
      options=options,
      executables=executables
      )

