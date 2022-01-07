#!/bin/sh
[ -d venv ] || ./gen_venv.sh
exec ./ledmatrixd.py -f /usr/share/fonts/misc/ter-x20b.pcf.gz -M 127.0.0.1
