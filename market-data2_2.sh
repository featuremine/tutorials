#!/usr/bin/env bash

HOST="${POSTGRES_HOST:=host.docker.internal}"
PORT="${POSTGRES_PORT:=5432}"

cd /opt
yamal-run -m syncer -o syncer --config /opt/syncer-sink.ini --section main &
python3 bulldozer2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp &
python3 bars2postgresql.py --database ${POSTGRES_USER} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-BTC,ADA-USD"
