#TODO: add description

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
    parser.add_argument("--ytp", help="YTP file", required=True)
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to '../test/test.lic' if not provided)",
        required=False,
        default="../test/test.lic")
    args = parser.parse_args()

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

    # E.G.
    # imnts = [
    #     "ADA-USD",
    #     "BTC-USD",
    #     "ETH-BTC",
    # ]

    # E.G.
    # markets = [
    #     "coinbase",
    #     "binance"
    # ]

    channels = []
    mktimnt = []
    db_fields_imnt_create = ""
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"]
            mktimnt += [f"{mkt}_{imnt}".replace("-", "_" )]
            db_fields_imnt_create += f"{mkt}_{imnt} NUMERIC NOT NULL,".replace("-", "_" )

    db_fields_imnt_create = db_fields_imnt_create.rstrip(db_fields_imnt_create[-1])

    cur = conn.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS vwap
    (
        vwap_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        {db_fields_imnt_create}
    )
    """)

    def print_vwap(x):
        #TODO: separate instruments
        print(x)
        table_pandas = x.as_pandas()
        vwap = table_pandas['vwap'][0]
        cur.execute(f"""
        INSERT INTO vwap ({mktimnt[0]}) VALUES
        ({vwap})
        """)
        conn.commit()
    
    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

    bars = bars_lib.bars_L3_live(op, args.ytp, "feed_handler", channels, date.today(), period=timedelta(seconds=1))
    for bar in bars:
        graph.callback(bar, print_vwap)

    graph.stream_ctx().run_live()
