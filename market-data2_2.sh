#!/usr/bin/env bash

DB_NAME="${POSTGRES_DB:-${POSTGRES_USER}}"
yamal-run -m syncer -o syncer --config /opt/syncer-sink.ini --section main &
python3 bulldozer2postgresql.py --database ${DB_NAME} --user ${POSTGRES_USER} --ytp /opt/ore_coinbase_l2.ytp &
python3 bars2postgresql.py --license /opt/test.lic --ytp /opt/ore_coinbase_l2.ytp --peer sink/source/feed_handler --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD" --database ${DB_NAME} --user ${POSTGRES_USER} &
python3 book2postgresql.py --license /opt/test.lic --ytp /opt/ore_coinbase_l2.ytp --peer sink/source/feed_handler --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD" --database ${DB_NAME} --user ${POSTGRES_USER} &
