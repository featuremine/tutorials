#!/usr/bin/env bash

cd /opt
yamal-run -c /usr/local/lib/yamal/modules/bulldozer/samples/coinbase_l2_ore_ytp.ini -s main &
#yamal-run -m syncer -o syncer --config /opt/syncer-source.ini --section main