#!/bin/bash
# 'strict' mode
set -euo pipefail
IFS=$'\n\t'

if ! [ -d ./venv ] ; then
	virtualenv ./venv
	./venv/bin/pip install pillow asyncio-mqtt aiohttp
fi

if ! [ -d ./venv/lib/python3.11/site-packages/pygame ] ; then
	./venv/bin/pip install pygame
fi

exec ./venv/bin/python ledmatrixd.py \
	-S -f ter-x20b.pcf.gz 5x7.pcf.gz \
	-M 127.0.0.1 -t 8080
