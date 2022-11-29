#!/usr/bin/env bash

cd /opt
yamal-run -c /opt/bulldozer_coinbase.ini -s main &
sleep 1
yamal-run -m syncer -o syncer --config /opt/syncer-source.ini --section main
