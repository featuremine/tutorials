#!/usr/bin/env bash

cd /opt
yamal-run -c /opt/bulldozer_coinbase.ini -s main || >&2 echo "yamal-run bulldozer failed" && kill -9 $$ &
sleep 1
yamal-run -m syncer -o syncer --config /opt/syncer-source.ini --section main || >&2 echo "yamal-run syncer failed"
