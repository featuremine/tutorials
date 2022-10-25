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
import extractor as e
from yamal import ytp
from datetime import timedelta, date, datetime
import psycopg2
import time
import math
from time import time_ns

# YTP channels prefix
prefix = "ore/imnts"

def extractor2psqlfield(name, t):
    if t == e.Time64:
        return f'{name} TIMESTAMP WITHOUT TIME ZONE'
    elif t == e.Decimal64 or t == e.Float64:
        return f'{name} NUMERIC NOT NULL'
    elif t == e.Int32:
        return f'{name} INT NOT NULL'
    else:
        return f'{name} VARCHAR(32)'

def extractor2psqlvalue(val):
    if isinstance(val, timedelta):
        return f"'{val + datetime(1970, 1, 1)}'"
    elif math.isnan(val):
        return '0.0'
    else:
        return str(val)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", help="postgreSQL database name", required=True)
    parser.add_argument("--user", help="postgreSQL user name", required=True)
    parser.add_argument("--password", help="postgreSQL database password", required=False, default="")
    parser.add_argument("--ytp", help="YTP file with market data in ORE format", required=True)
    parser.add_argument("--peer", help="YTP peer reader", required=False, default="feed_handler")
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--period", help="Bar period in seconds", required=False, default=10)
    parser.add_argument("--levels", help="Book levels to display", required=False, default=5)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to 'test.lic' if not provided)",
        required=False,
        default="test.lic")

    args = parser.parse_args()

    bars_descr = (("close_time", e.Time64),
                ("close_askpx", e.Decimal64),
                ("close_asksz", e.Decimal64),
                ("close_bidpx", e.Decimal64),
                ("close_bidsz", e.Decimal64),
                ("close_px", e.Decimal64),
                ("close_sz", e.Decimal64),
                ("high_askpx", e.Decimal64),
                ("high_asksz", e.Decimal64),
                ("high_bidpx", e.Decimal64),
                ("high_bidsz", e.Decimal64),
                ("high_px", e.Decimal64),
                ("high_sz", e.Decimal64),
                ("low_askpx", e.Decimal64),
                ("low_asksz", e.Decimal64),
                ("low_bidpx", e.Decimal64),
                ("low_bidsz", e.Decimal64),
                ("low_px", e.Decimal64),
                ("low_sz", e.Decimal64),
                ("notional", e.Decimal64),
                ("open_askpx", e.Decimal64),
                ("open_asksz", e.Decimal64),
                ("open_bidpx", e.Decimal64),
                ("open_bidsz", e.Decimal64),
                ("open_px", e.Decimal64),
                ("open_sz", e.Decimal64),
                ("shares", e.Float64),
                ("ticker", e.Array(e.Char, 16)),
                ("tw_askpx", e.Float64),
                ("tw_asksz", e.Float64),
                ("tw_bidpx", e.Float64),
                ("tw_bidsz", e.Float64),
                ("vwap", e.Float64))

    bbos_descr = [("close_time", e.Time64)] + \
                sum([[(f"bid_prx_{i}", e.Decimal64),
                        (f"bid_shr_{i}", e.Decimal64),
                        (f"ask_prx_{i}", e.Decimal64),
                        (f"ask_shr_{i}", e.Decimal64)] for i in range(0, args.levels)])

    trade_descr = (("price", e.Decimal64),
                ("qty", e.Decimal64),
                ("side", e.Int32),
                ("receive", e.Time64))

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

    db_fields_array = []
    db_fields_create = ''
    for field in bars_descr:
        if field[0] == 'ticker':
            continue
        db_fields_array += [field[0]]
        db_fields_create += extractor2psqlfield(field[0], field[1]) + ','
    db_fields_create = db_fields_create[:-1]
    db_fields_str = ",".join(db_fields_array)

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

    def marketdata2db(x, market, imnt):
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array]
        values_str = ",".join(values)
        cur.execute(f"""
        INSERT INTO market_data (market,imnt,{db_fields_str}) VALUES
        ('{market}','{imnt}',{values_str})
        """)
        conn.commit()

    def book2db(x, market, imnt):
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array_bbos]
        values_str = ",".join(values)
        cur.execute(f"""
        INSERT INTO book (market,imnt,{db_fields_str_bbos}) VALUES
        ('{market}','{imnt}',{values_str})
        """)
        conn.commit()
        
    def trades2db(x, market, imnt):
        # Populate the market data parameters into the database
        values = [extractor2psqlvalue(getattr(x[0], f)) for f in db_fields_array_trades]
        values_str = ",".join(values)
        cur.execute(f"""
        INSERT INTO trades (market,imnt,{db_fields_str_trades}) VALUES
        ('{market}','{imnt}',{values_str})
        """)
        conn.commit()

    # Set the extractor's license
    e.set_license(args.license)
    graph = e.system.comp_graph()
    op = graph.features

    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair


    close = op.timer(timedelta(seconds=args.period))

    def compute_bar(op, bbo, trade):
        def quote_side_float64(quote, name):
            return op.cond(op.is_zero(op.field(quote, name)),
                        op.nan(quote),
                        op.convert(quote, e.Float64))

        def quote_float64(quote):
            bid_quote = op.fields(quote, ("bidprice", "bidqty"))
            ask_quote = op.fields(quote, ("askprice", "askqty"))
            return op.combine(quote_side_float64(bid_quote, "bidqty"), tuple(),
                            quote_side_float64(ask_quote, "askqty"), tuple())


        quote = op.fields(bbo, ("bidprice", "askprice", "bidqty", "askqty"))
        quote_bid = op.field(bbo, "bidprice")
        quote_ask = op.field(bbo, "askprice")
        open_quote = op.op._prev(quote, close)
        close_quote = op.left_lim(quote, close)
        high_quote = op.left_lim(op.op.(quote, op.max(quote_ask, close)), close)
        low_quote = op.left_lim(op.asof(quote, op.min(quote_bid, close)), close)

        tw_quote = op.average_tw(quote_float64(quote), close)
        trade = op.fields(trade, ("price", "qty"))
        trade_px = op.field(trade, "price")
        first_trade = op.first_after(trade, close)
        open_trade = op.last_asof(first_trade, close)
        close_trade = op.last_asof(trade, close)
        high_trade = op.last_asof(op.asof(trade, op.max(trade_px, first_trade)), close)
        low_trade = op.last_asof(op.asof(trade, op.min(trade_px, first_trade)), close)

        ftrade_px = op.convert(trade_px, e.Float64)
        ftrade_qty = op.convert(trade.qty, e.Float64)
        total_notional = op.left_lim(op.cumulative(ftrade_px * ftrade_qty), close)
        total_shares = op.left_lim(op.cumulative(ftrade_qty), close)
        prev_total_notional = op.tick_lag(total_notional, 1)
        prev_total_shares = op.tick_lag(total_shares, 1)
        notional = total_notional - prev_total_notional
        shares = total_shares - prev_total_shares
        vwap = op.cond(op.is_zero(shares), op.convert(open_trade.price, e.Float64), notional / shares)

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
            tw_quote, (("bidprice", "tw_bidpx"),
                    ("askprice", "tw_askpx"),
                    ("bidqty", "tw_bidsz"),
                    ("askqty", "tw_asksz")),
            vwap, ("vwap",),
            notional, ("notional",),
            shares, ("shares",),
            close, (("actual", "close_time"),))
        return combined

    def compute_bars(op, quotes, trades):
        return [compute_bar(op, quote, trd) for quote, trd in zip(quotes, trades)]

    def filter_quote(op, quote, maximum_spread_ratio=0.1):
        max_spread_ratio = op.constant(("max_spread_ratio", e.Float64, maximum_spread_ratio))
        midpx_multiplier = op.constant(("price", e.Float64, 0.5))
        cleanbidpx = op.filter_unless(op.is_zero(quote.bidqty), op.convert(quote.bidprice, e.Float64))
        cleanaskpx = op.filter_unless(op.is_zero(quote.askqty), op.convert(quote.askprice, e.Float64))
        spread = cleanaskpx - cleanbidpx
        raw_fairpx = midpx_multiplier * (cleanbidpx + cleanaskpx)
        bad_spread = spread / raw_fairpx > max_spread_ratio
        return op.filter_unless(bad_spread, quote)

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
                         ("qty", "qty")))
                for upd in upds]

    bars = compute_bars(op, quotes, trades)
    sampled_levels = op.asof(levels, close)

    # Add a callback for each bar that corresponds to a market/instrument pair
    for level, bar, mi in zip(sampled_levels, bars, mktimnt):
        graph.callback(bar, functools.partial(marketdata2db, market=mi[0], imnt=mi[1]))
        graph.callback(level, functools.partial(book2db, market=mi[0], imnt=mi[1]))

    # Run the extractor blocking
    graph.stream_ctx().run_live()

    conn.close()
