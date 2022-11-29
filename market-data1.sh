#!/usr/bin/env bash

HOST="${POSTGRES_HOST:=host.docker.internal}"
PORT="${POSTGRES_PORT:=5432}"
NAME="${POSTGRES_NAME:=${POSTGRES_USER}}"
PERIOD="${BARS_PERIOD:=10}"

cd /opt
yamal-run -c /opt/bulldozer_coinbase.ini -s main &
python3 bulldozer2postgresql.py --database ${POSTGRES_NAME} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp &
python3 bars2postgresql.py --database ${POSTGRES_NAME} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-USD,DOGE-USD,USDT-USD" --period ${BARS_PERIOD}
