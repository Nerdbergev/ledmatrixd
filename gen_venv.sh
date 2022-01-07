#!/bin/sh

virtualenv ./venv
./venv/bin/pip install pillow pygame aiohttp asyncio-mqtt
