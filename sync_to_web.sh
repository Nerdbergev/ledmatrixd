#!/bin/sh
git clean -x -f -d
rsync -av --delete . optiplex980:/srv/http/home/chris/ledmatrixd
