#!/usr/bin/env bash

cd /opt
yamal-run -c /usr/local/lib/yamal/modules/bulldozer/samples/coinbase_l2_ore_ytp.ini -s main &
python3 bulldozer2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host host.docker.internal --ytp /opt/ore_coinbase_l2.ytp &
python3 bars2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host host.docker.internal --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD"
