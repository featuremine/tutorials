#!/usr/bin/env bash

HOST="${DATABASE_HOST:=host.docker.internal}"
PORT="${DATABASE_PORT:=9200}"
PERIOD="${BARS_PERIOD:=10}"

cd /opt
yamal-run -m syncer -o syncer --config /opt/syncer-sink.ini --section main || >&2 echo "yamal-run syncer failed" && kill -9 $$ &
python3 bulldozer2elasticsearch.py --host ${DATABASE_HOST} --port ${DATABASE_PORT} --ytp /opt/ore_coinbase_l2.ytp || >&2 echo "bulldozer2elasticsearch.py failed" && kill -9 $$ &
python3 bars2elasticsearch.py --host ${DATABASE_HOST} --port ${DATABASE_PORT} --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-USD,DOGE-USD,USDT-USD" --period ${BARS_PERIOD} || >&2 echo "bars2elasticsearch.py failed"
