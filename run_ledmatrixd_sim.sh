#!/bin/sh
[ -d venv ] || ./gen_venv.sh
exec ./ledmatrixd.py \
	-S \
	-f /usr/share/fonts/misc/ter-x20b.pcf.gz \
		/usr/share/fonts/misc/5x7.pcf.gz \
	-M 127.0.0.1
