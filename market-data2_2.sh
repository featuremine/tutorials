#!/usr/bin/env bash

HOST="${POSTGRES_HOST:=host.docker.internal}"
PORT="${POSTGRES_PORT:=5432}"
NAME="${POSTGRES_NAME:=${POSTGRES_USER}}"
PERIOD="${BARS_PERIOD:=10}"

cd /opt
yamal-run -m syncer -o syncer --config /opt/syncer-sink.ini --section main || >&2 echo "yamal-run syncer failed" && shutdown now &
python3 bulldozer2postgresql.py --database ${POSTGRES_NAME} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp || >&2 echo "bulldozer2postgresql.py failed" && shutdown now &
python3 bars2postgresql.py --database ${POSTGRES_NAME} --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-USD,DOGE-USD,USDT-USD" --period ${BARS_PERIOD} || >&2 echo "bars2postgresql.py failed" && shutdown now
