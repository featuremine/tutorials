#!/usr/bin/env bash

DB_NAME="${POSTGRES_DB:-${POSTGRES_USER}}"
yamal-run -c /usr/local/lib/yamal/modules/bulldozer/samples/coinbase_l2_ore_ytp.ini -s main &
python3 bulldozer2postgresql.py --database ${DB_NAME} --user ${POSTGRES_USER} --ytp /opt/ore_coinbase_l2.ytp &
python3 bars2postgresql.py --license /opt/test.lic --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD" --database ${DB_NAME} --user ${POSTGRES_USER} &
python3 book2postgresql.py --license /opt/test.lic --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD" --database ${DB_NAME} --user ${POSTGRES_USER} &
