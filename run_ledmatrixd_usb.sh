#!/bin/bash
# 'strict' mode
set -euo pipefail
IFS=$'\n\t'

if ! [ -d ./venv ] ; then
	virtualenv ./venv
	./venv/bin/pip install pillow asyncio-mqtt aiohttp
fi

if ! [ -d ./venv/lib/python3.11/site-packages/usb ] ; then
	./venv/bin/pip install pyusb
fi

exec ./ledmatrixd.py \
	-f ter-x20b.pcf.gz 5x7.pcf.gz \
	-M 127.0.0.1
