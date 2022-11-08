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
from yamal import ytp
from datetime import timedelta, date, datetime
import psycopg2
import time
import math
from time import time_ns

# YTP channels prefix
prefix = "ore/imnts"

def extractor2psqlfield(name, t):
    if t == extractor.Time64:
        return f'{name} TIMESTAMP WITHOUT TIME ZONE'
    elif t == extractor.Decimal64:
        return f'{name} NUMERIC NOT NULL'
    elif t == extractor.Float64:
        return f'{name} NUMERIC NOT NULL'
    elif t == extractor.Decimal128:
        return f'{name} NUMERIC NOT NULL'
    elif t == extractor.Int32:
        return f'{name} INT NOT NULL'
    else:
        return f'{name} VARCHAR(32)'

def extractor2psqlvalue(val):
    if isinstance(val, str):
        f"'{val}'"
    if isinstance(val, timedelta):
        return f"'{val + datetime(1970, 1, 1)}'"
    else:
        return str(val)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    parser.add_argument("--host", help="postgreSQL database host", required=False, default="127.0.0.1")
    parser.add_argument("--port", help="postgreSQL database port", required=False, default="5432")
    parser.add_argument("--ytp", help="YTP file with market data in ORE format", required=True)
    parser.add_argument("--peer", help="YTP peer reader", required=False, default="feed_handler")
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--period", help="Bar period in seconds", required=False, default=10)
    parser.add_argument("--levels", help="Book levels to display", required=False, default=5)

    args = parser.parse_args()

    bars_descr = (("close_time", extractor.Time64),
                ("close_askpx", extractor.Decimal64),
                ("close_asksz", extractor.Decimal64),
                ("close_bidpx", extractor.Decimal64),
                ("close_bidsz", extractor.Decimal64),
                ("close_px", extractor.Decimal64),
                ("close_sz", extractor.Decimal64),
                ("high_askpx", extractor.Decimal64),
                ("high_asksz", extractor.Decimal64),
                ("high_bidpx", extractor.Decimal64),
                ("high_bidsz", extractor.Decimal64),
                ("high_px", extractor.Decimal64),
                ("high_sz", extractor.Decimal64),
                ("low_askpx", extractor.Decimal64),
                ("low_asksz", extractor.Decimal64),
                ("low_bidpx", extractor.Decimal64),
                ("low_bidsz", extractor.Decimal64),
                ("low_px", extractor.Decimal64),
                ("low_sz", extractor.Decimal64),
                ("notional", extractor.Decimal64),
                ("open_askpx", extractor.Decimal64),
                ("open_asksz", extractor.Decimal64),
                ("open_bidpx", extractor.Decimal64),
                ("open_bidsz", extractor.Decimal64),
                ("open_px", extractor.Decimal64),
                ("open_sz", extractor.Decimal64),
                ("shares", extractor.Float64),
                ("ticker", extractor.Array(extractor.Char, 16)),
                # ("tw_askpx", extractor.Float64),
                # ("tw_asksz", extractor.Float64),
                # ("tw_bidpx", extractor.Float64),
                # ("tw_bidsz", extractor.Float64),
                ("vwap", extractor.Float64))

    trade_descr = (("price", extractor.Decimal64),
                   ("qty", extractor.Decimal64),
                  #("side", extractor.Array(extractor.Char, 1)),
                   ("receive", extractor.Time64))

    # Wait until the YTP file is created
    while not os.path.exists(args.ytp):
        time.sleep(0.1)

    # Connect to PostgreSQL database
    tries = 10
    while True:
        try:
            conn = psycopg2.connect(database=args.database,
                                    user=args.user, password=args.password,
                                    host=args.host, port=args.port)
            break
        except psycopg2.OperationalError as e:
            if tries > 0:
                tries -= 1
            else:
                raise
        time.sleep(1)
    cur = conn.cursor()

    db_fields_array = []
    db_fields_create = ''
    for field in bars_descr:
        if field[0] == 'ticker':
            continue
        db_fields_array += [field[0]]
        db_fields_create += extractor2psqlfield(field[0], field[1]) + ','
    db_fields_create = db_fields_create[:-1]
    db_fields_str = ",".join(db_fields_array)

    db_fields_array_trades = []
    db_fields_create_trades  = ''
    for field in trade_descr:
        db_fields_array_trades += [field[0]]
        db_fields_create_trades += extractor2psqlfield(field[0], field[1]) + ','
    db_fields_create_trades = db_fields_create_trades[:-1]
    db_fields_str_trades = ",".join(db_fields_array_trades)

    # Create database table to store market data
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS market_data
    (
        bars_id SERIAL PRIMARY KEY NOT NULL,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
        market VARCHAR(32),
        imnt VARCHAR(32),
        {db_fields_create}
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

    def bar2db(x, market, imnt):
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array]
        values_str = ",".join(values)
        cmd = f"""
        INSERT INTO market_data (market,imnt,{db_fields_str}) VALUES
        ('{market}','{imnt}',{values_str})
        """
        print(cmd)
        #cur.execute(cmd)
        #conn.commit()

    def trades2db(x, market, imnt):
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array_trades]
        values_str = ",".join(values)
        cmd = f"""
        INSERT INTO trades (market,imnt,{db_fields_str_trades}) VALUES
        ('{market}','{imnt}',{values_str})
        """
        print(cmd)
        cur.execute(cmd)
        conn.commit()

    # Set the extractor's license
    graph = extractor.system.comp_graph()
    op = graph.features

    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair



    def compute_bar(op, bbo, trade, vendor_time):
        close = op.data_bar(vendor_time, timedelta(seconds=args.period))
        quote = op.fields(bbo, ("bidprice", "askprice", "bidqty", "askqty"))
        quote_bid = op.field(bbo, "bidprice")
        quote_ask = op.field(bbo, "askprice")
        close_quote = op.left_lim(quote, close)
        open_quote = op.tick_lag(close_quote, 1) # this needs to be fixed to skip

        high_quote = op.left_lim(op.asof(quote, op.max(quote_ask, close)), close)
        low_quote = op.left_lim(op.asof(quote, op.min(quote_bid, close)), close)

        #tw_quote = op.average_tw(quote, close) # this one need to be fixed so as not to depend on system time
        trade = op.fields(trade, ("price", "qty"))
        trade_px = trade.price
        trade_qty = trade.qty
        first_trade = op.first_after(trade, close) #todo: make sure it accounts for first AT or after
        open_trade = op.last_asof(first_trade, close)
        close_trade = op.last_asof(trade, close)
        high_trade = op.last_asof(op.asof(trade, op.max(trade_px, first_trade)), close)
        low_trade = op.last_asof(op.asof(trade, op.min(trade_px, first_trade)), close)

        total_notional = op.left_lim(op.cumulative(trade_px * trade_qty), close)
        total_shares = op.left_lim(op.cumulative(trade_qty), close)
        prev_total_notional = op.tick_lag(total_notional, 1)
        prev_total_shares = op.tick_lag(total_shares, 1)
        notional = total_notional - prev_total_notional
        shares = total_shares - prev_total_shares
        vwap = op.cond(op.is_zero(shares), open_trade.price, notional / shares)

        combined = op.combine(
            open_trade, (("price", "open_px"),
                        ("qty", "open_sz")),
            close_trade, (("price", "close_px"),
                        ("qty", "close_sz")),
            high_trade, (("price", "high_px"),
                        ("qty", "high_sz")),
            low_trade, (("price", "low_px"),
                        ("qty", "low_sz")),
            open_quote, (("bidprice", "open_bidpx"),
                        ("askprice", "open_askpx"),
                        ("bidqty", "open_bidsz"),
                        ("askqty", "open_asksz")),
            close_quote, (("bidprice", "close_bidpx"),
                        ("askprice", "close_askpx"),
                        ("bidqty", "close_bidsz"),
                        ("askqty", "close_asksz")),
            high_quote, (("bidprice", "high_bidpx"),
                        ("askprice", "high_askpx"),
                        ("bidqty", "high_bidsz"),
                        ("askqty", "high_asksz")),
            low_quote, (("bidprice", "low_bidpx"),
                        ("askprice", "low_askpx"),
                        ("bidqty", "low_bidsz"),
                        ("askqty", "low_asksz")),
            # tw_quote, (("bidprice", "tw_bidpx"),
            #         ("askprice", "tw_askpx"),
            #         ("bidqty", "tw_bidsz"),
            #         ("askqty", "tw_asksz")),
            vwap, ("vwap",),
            notional, ("notional",),
            shares, ("shares",),
            close, (("start", "close_time"),))
        return combined

    def compute_bars(op, quotes, trades, times):
        return [compute_bar(op, quote, trd, ven) for quote, trd, ven, in zip(quotes, trades, times)]

    seq = ytp.sequence(args.ytp, readonly=True)
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer(args.peer)
    upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]

    levels = [op.book_build(upd, 5) for upd in upds]
    quotes = [op.combine(level,
                    (("bid_prx_0", "bidprice"),
                     ("bid_shr_0", "bidqty"),
                     ("ask_prx_0", "askprice"),
                     ("ask_shr_0", "askqty")))
            for level in levels]

    trades = [op.combine(op.book_trades(upd),
                        (("trade_price", "price"),
                         ("vendor", "receive"),
                         ("qty", "qty"),
                         ("decoration", "side")))
                for upd in upds]

    times = [op.book_vendor_time(upd) for upd in upds]
    bars = compute_bars(op, quotes, trades, times)

    # Add a callback for each bar that corresponds to a market/instrument pair
    for bar, mi, trade in zip(bars, mktimnt, trades):
        graph.callback(bar, functools.partial(bar2db, market=mi[0], imnt=mi[1]))
       # graph.callback(trade, functools.partial(trades2db, market=mi[0], imnt=mi[1]))

    # Run the extractor blocking
    graph.stream_ctx().run_live()

    conn.close()
