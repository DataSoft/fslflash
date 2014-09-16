#!/usr/bin/python3

import sys

with open(sys.argv[1], 'rb') as f:
    chksum = f.read(4)
    env = f.read().replace(b'\x00', b'\n').rstrip()
    print(env.decode('ascii'))
