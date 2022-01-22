#!/bin/sh

virtualenv ./venv
./venv/bin/pip install pillow pyusb asyncio-mqtt

exec ./ledmatrixd.py \
	-f /usr/share/fonts/misc/ter-x20b.pcf.gz \
		/usr/share/fonts/misc/5x7.pcf.gz \
	-M 127.0.0.1
