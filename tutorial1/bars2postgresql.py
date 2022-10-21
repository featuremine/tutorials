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
import extractor
from datetime import timedelta, date
import psycopg2
import time
import bars as bars_lib

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
    db_fields_imnt_create = ""
    counters = {}
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"]
            db_field = f"{mkt}_{imnt}".replace("-", "_" )
            mktimnt += [db_field]
            db_fields_imnt_create += f"{db_field} NUMERIC NOT NULL DEFAULT 0.00,"
            counters[db_field] = 1 # db table id starts with 1

    db_fields_imnt_create = db_fields_imnt_create.rstrip(db_fields_imnt_create[-1])

    # Create database table to store market data
    cur = conn.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS vwap
    (
        vwap_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        {db_fields_imnt_create}
    )
    """)
    conn.commit()

    # Get the last id from the table if there was any
    cur.execute("""
    SELECT MAX(vwap_id) FROM vwap;
    """)
    last_id = cur.fetchall()
    if last_id[0][0]:
        for k, v in counters.items():
            counters[k] = last_id[0][0] + 1

    def print_vwap(x):
        print(x)
        table_pandas = x.as_pandas()
        ticker = table_pandas['ticker'][0]
        vwap = table_pandas['vwap'][0]
        cur.execute(f"""
        INSERT INTO vwap (vwap_id,{ticker}) VALUES
        ({counters[ticker]},{vwap})
        ON CONFLICT (vwap_id)
        DO UPDATE
        SET {ticker} = {vwap};
        """)
        conn.commit()
        counters[ticker] += 1
    
    # Set the extractor's license
    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

    # Get the bars frames with the market data from the bars module
    bars = bars_lib.bars_L3_live(op, args.ytp, "feed_handler", channels, date.today(), period=timedelta(seconds=1))
    
    # Append the ticker name to the corresponding bar frame
    out_stream = op.join(*bars, "ticker", extractor.Array(extractor.Char, 32),
                         tuple([ticker for ticker in mktimnt]))
    
    # Add a function callback for each new frame with the market data
    graph.callback(out_stream, print_vwap)

    # Run the extractor blocking
    graph.stream_ctx().run_live()
