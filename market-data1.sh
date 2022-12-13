#!/usr/bin/env bash

HOST="${POSTGRES_HOST:=host.docker.internal}"
PORT="${POSTGRES_PORT:=9200}"

cd /opt
yamal-run -c /opt/bulldozer_coinbase.ini -s main || >&2 echo "yamal-run failed" && kill -9 $$ &
python3 bulldozer2elasticsearch.py --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp || >&2 echo "bulldozer2elasticsearch.py failed" && kill -9 $$ &
python3 bars2postgresql.py --host ${POSTGRES_HOST} --port ${POSTGRES_PORT} --ytp /opt/ore_coinbase_l2.ytp --markets "coinbase" --imnts "BTC-USD,ETH-USD,DOGE-USD,USDT-USD" --period ${BARS_PERIOD} || >&2 echo "bars2postgresql.py failed"
