import argparse
import extractor
from yamal import ytp
from datetime import timedelta, datetime
import os
import time
import psycopg2
import math
import functools

bbos_descr = (("bidprice", extractor.Decimal64),
              ("askprice", extractor.Decimal64),
              ("bidqty", extractor.Int32),
              ("askqty", extractor.Int32),
              ("receive", extractor.Time64))

trade_descr = (("price", extractor.Decimal64),
               ("qty", extractor.Int32),
               ("side", extractor.Int32),
               ("receive", extractor.Time64))

def extractor2psqlfield(name, t):
    if t == extractor.Time64:
        return f'{name} TIMESTAMP WITHOUT TIME ZONE'
    elif t == extractor.Decimal64 or t == extractor.Int32 or t == extractor.Float64:
        return f'{name} NUMERIC NOT NULL'
    else:
        return f'{name} VARCHAR(32)'

def extractor2psqlvalue(val):
    if isinstance(val, timedelta):
        return f"'{val + datetime(1970, 1, 1)}'"
    elif math.isnan(val):
        return '0.0'
    else:
        return str(val)

def print_trades(x):
    print(x)

def print_bbos(x):
    print(x)

class Universe:
    def __init__(self, universe_keys):
        self.universe_keys = universe_keys

    def get(self, name):
        if name != "all":
            raise LookupError("unknown universe name")
        return self.universe_keys

class Symbology:
    def __init__(self, symb_table):
        self.imnts = symb_table

    def info(self, id):
        return self.imnts[id]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    parser.add_argument("--ytp", help="YTP file", required=True)
    parser.add_argument("--peer", help="YTP peer reader", required=False, default="feed_handler")
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--levels", help="Number of levels to display", type=int, required=False, default=1)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to '../test/test.lic' if not provided)",
        required=False,
        default="../test/test.lic")
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
    
    db_fields_array_bbos = []
    db_fields_create_bbos = ''
    for field in bbos_descr:
        db_fields_array_bbos += [field[0]]
        db_fields_create_bbos += extractor2psqlfield(field[0], field[1]) + ','
    db_fields_create_bbos = db_fields_create_bbos[:-1]
    db_fields_str_bbos = ",".join(db_fields_array_bbos)
    db_fields_array_trades = []
    db_fields_create_trades  = ''
    for field in trade_descr:
        db_fields_array_trades += [field[0]]
        db_fields_create_trades += extractor2psqlfield(field[0], field[1]) + ','
    db_fields_create_trades = db_fields_create_trades[:-1]
    db_fields_str_trades = ",".join(db_fields_array_trades)

    # Create database table to store book
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS book
    (
        book_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        market VARCHAR(32),
        imnt VARCHAR(32),
        {db_fields_create_bbos}
    )
    """)
    conn.commit()
    # Create database table to store trades
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS trades
    (
        trade_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        market VARCHAR(32),
        imnt VARCHAR(32),
        {db_fields_create_trades}
    )
    """)
    conn.commit()

    def book2db(x, market, imnt):
        print(market)
        print(imnt)
        print(x)
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array_bbos]
        values_str = ",".join(values)
        cur.execute(f"""
        INSERT INTO book (market,imnt,{db_fields_str_bbos}) VALUES
        ('{market}','{imnt}',{values_str})
        """)
        conn.commit()
        
    def trades2db(x, market, imnt):
        print(market)
        print(imnt)
        print(x)
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array_trades]
        values_str = ",".join(values)
        cur.execute(f"""
        INSERT INTO trades (market,imnt,{db_fields_str_trades}) VALUES
        ('{market}','{imnt}',{values_str})
        """)
        conn.commit()

    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

    # E.G.
    # symb_table = {
    #     1: {"ticker": "ADA-USD"},
    #     2: {"ticker": "BTC-USD"},
    #     3: {"ticker": "ETH-BTC"},
    # }
    symb_table = {}
    i = 1
    for imnt in args.imnts.split(','):
        symb_table[i] = {"ticker": imnt}
        i += 1
    symbology = Symbology(symb_table)
    universe = Universe(symb_table.keys())

    # E.G.
    # markets = [
    #     "coinbase",
    #     "binance"
    # ]
    markets = args.markets.split(',')
    
    seq = ytp.sequence(args.ytp, readonly=True)
    peer = seq.peer(args.peer)
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    for imnt in universe.get("all"):
        ticker = symbology.info(imnt)["ticker"]
        bbos_book = []
        trades = []
        cum_trades = []
        statuses = []
        for mkt in markets:
            ch = peer.channel(1000, f"ore/imnts/{mkt}/{ticker}")  # E.G. "ore/imnts/coinbase/BTC-USD"
            bookupd = op.ore_ytp_decode(ch)
            decoded = op.decode_data(bookupd)
            bbo_book = op.book_build(decoded, args.levels)

            book_receive = op.decode_receive(bookupd)
            bbo_receive = op.asof(book_receive, bbo_book)

            bidqty_int32 = op.convert(op.round(bbo_book.bid_shr_0), extractor.Int32)
            askqty_int32 = op.convert(op.round(bbo_book.ask_shr_0), extractor.Int32)
            bbo_book_combined = op.combine(
                bbo_book, (
                    ("bid_prx_0", "bidprice"),
                    ("ask_prx_0", "askprice")
                ),
                bidqty_int32, (("bid_shr_0", "bidqty"),),
                askqty_int32, (("ask_shr_0", "askqty"),),
                bbo_receive, (("time", "receive"),)
            )
            graph.callback(bbo_book_combined, functools.partial(book2db, market=mkt, imnt=ticker))

            trade = op.book_trades(decoded)  # change
            trade_receive = op.asof(book_receive, trade)

            bid, ask, unk = op.split(trade.decoration, 'decoration', ('b', 'a', 'u'))
            bid_val = op.constant(bid, ('side', extractor.Int32, 0))
            ask_val = op.constant(ask, ('side', extractor.Int32, 1))
            unk_val = op.constant(unk, ('side', extractor.Int32, 2))
            side = op.join(
                bid_val, ask_val, unk_val, 'decoration', extractor.Array(
                    extractor.Char, 1), ('b', 'a', 'u')).side

            qty_decimal64 = op.round(trade.qty)
            qty_int32 = op.convert(qty_decimal64, extractor.Int32)

            trade_combined = op.combine(
                trade, (("trade_price", "price"),),
                qty_int32, (("qty", "qty"),),
                trade_receive, (("time", "receive"),),
                side, (("side", "side"),)
            )
            graph.callback(trade_combined, functools.partial(trades2db, market=mkt, imnt=ticker))

    graph.stream_ctx().run_live()
