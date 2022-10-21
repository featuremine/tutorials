#!/usr/bin/env python3
"""
/******************************************************************************

        COPYRIGHT (c) 2022 by Featuremine Corporation.
        This software has been provided pursuant to a License Agreement
        containing restrictions on its use.  This software contains
        valuable trade secrets and proprietary information of
        Featuremine Corporation and is protected by law.  It may not be
        copied or distributed in any form or medium, disclosed to third
        parties, reverse engineered or used in any manner not provided
        for in said License Agreement except with the prior written
        authorization from Featuremine Corporation.

 *****************************************************************************/
"""

"""
 * @file bars2postgresql.py
 * @date 20 Oct 2022
 * @brief Populate a PostgreSQL database with bars data from extractor
 */
"""
import argparse
import os
import functools
import extractor
from datetime import timedelta, date
import psycopg2
import time
import bars as bars_lib

# YTP channels prefix
prefix = "ore/imnts"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    parser.add_argument("--ytp", help="YTP file with market data in ORE format", required=True)
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to 'test.lic' if not provided)",
        required=False,
        default="test.lic")
    args = parser.parse_args()
   
    # Wait until the YTP file is created
    while not os.path.exists(args.ytp):
        time.sleep(0.1)

    # Connect to PostgreSQL database
    tries = 10
    while True:
        try:
            conn = psycopg2.connect(database = args.database, user = args.user, password = args.password, host = "127.0.0.1", port = "5432")
            break
        except psycopg2.OperationalError as e:
            if tries > 0:
                tries -= 1
            else:
                raise
        time.sleep(1)
    cur = conn.cursor()

    # Markets and instruments examples
    # E.G.
    # imnts = [
    #     "ADA-USD",
    #     "BTC-USD",
    #     "ETH-BTC",
    # ]

    # E.G.
    # markets = [
    #     "coinbase"
    # ]

    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair

    # Create database table to store market data
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS vwap
    (
        vwap_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        market VARCHAR(32),
        imnt VARCHAR(32),
        value NUMERIC NOT NULL DEFAULT 0.00
    )
    """)
    conn.commit()

    def vwap2db(x, market, imnt):
        # Get the vwap
        table_pandas = x.as_pandas()
        vwap = table_pandas['vwap'][0]
        # Populate the vwap into the database
        cur.execute(f"""
        INSERT INTO vwap (market,imnt,value) VALUES
        ('{market}','{imnt}',{vwap})
        """)
        conn.commit()
    
    # Set the extractor's license
    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

    # Get the bars frames with the market data from the bars module
    bars = bars_lib.bars_L3_live(op, args.ytp, "feed_handler", date.today(), period=timedelta(seconds=1), channels=channels)
    
    # Add a callback for each bar that corresponds to a market/instrument pair
    for bar, mi in zip(bars, mktimnt):
        graph.callback(bar, functools.partial(vwap2db, market=mi[0], imnt=mi[1]))

    # Run the extractor blocking
    graph.stream_ctx().run_live()

    conn.close()
