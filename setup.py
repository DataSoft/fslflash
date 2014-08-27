import sys
from cx_Freeze import setup, Executable

base = None
if sys.platform == 'win32':
    base = 'Win32GUI'

options = {
    'build_exe': {
        'includes': 'atexit',
        'include_files': 'libusb-1.0.dll',
    }
}

executables = [
    Executable('fslflash.py', base=base)
]

setup(name='fslflash',
      version='1.0',
      description='Vybrid Flash Utility',
      options=options,
      executables=executables
      )

