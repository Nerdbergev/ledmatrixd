#!/bin/bash
# 'strict' mode
set -euo pipefail
IFS=$'\n\t'

if ! [ -d ./venv ] ; then
	virtualenv ./venv
	./venv/bin/pip install pillow asyncio-mqtt aiohttp pygame
fi

exec ./venv/bin/python ledmatrixd.py \
	-S -f  modd-iso8859-1-06x11.bdf modd-iso8859-1-06x11-bold.bdf 5x7.pcf.gz \
	-M 127.0.0.1 -t 8080
