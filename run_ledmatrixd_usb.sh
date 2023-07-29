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
	-f /usr/share/fonts/misc/ter-x20b.pcf.gz \
		/usr/share/fonts/misc/5x7.pcf.gz \
	-M 127.0.0.1
