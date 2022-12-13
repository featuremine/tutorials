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
 * @file bars2elasticsearch.py
 * @date 20 Oct 2022
 * @brief Populate a elasticsearch database with bars data from extractor
 */
"""
import argparse
import os
import functools
import extractor
from yamal import ytp
from datetime import timedelta, date, datetime
from elasticsearch import Elasticsearch
import time
import math
from time import time_ns

# YTP channels prefix
prefix = "ore/imnts"

def extractor2elasticsvalue(val):
    if isinstance(val, str):
        f"'{val}'"
    if isinstance(val, timedelta):
        return val + datetime(1970, 1, 1)
    else:
        return float(val)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="Elasticsearch database host", required=False, default="127.0.0.1")
    parser.add_argument("--port", help="Elasticsearch database port", required=False, default="9200")
    parser.add_argument("--ytp", help="YTP file with market data in ORE format", required=True)
    parser.add_argument("--peer", help="YTP peer reader", required=False, default="feed_handler")
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--period", help="Bar period in seconds", required=False, default=10)
    parser.add_argument("--levels", help="Book levels to display", required=False, default=1)

    args = parser.parse_args()

    bars_descr = (("open_time", extractor.Time64),
                  ("close_time", extractor.Time64),
                  ("close_askpx", extractor.Decimal128),
                  ("close_asksz", extractor.Decimal128),
                  ("close_bidpx", extractor.Decimal128),
                  ("close_bidsz", extractor.Decimal128),
                  ("high_askpx", extractor.Decimal128),
                  ("high_asksz", extractor.Decimal128),
                  ("high_bidpx", extractor.Decimal128),
                  ("high_bidsz", extractor.Decimal128),
                  ("low_askpx", extractor.Decimal128),
                  ("low_asksz", extractor.Decimal128),
                  ("low_bidpx", extractor.Decimal128),
                  ("low_bidsz", extractor.Decimal128),
                  ("open_askpx", extractor.Decimal128),
                  ("open_asksz", extractor.Decimal128),
                  ("open_bidpx", extractor.Decimal128),
                  ("open_bidsz", extractor.Decimal128),
                  ("close_px", extractor.Decimal128),
                  ("close_sz", extractor.Decimal128),
                  ("high_px", extractor.Decimal128),
                  ("high_sz", extractor.Decimal128),
                  ("low_px", extractor.Decimal128),
                  ("low_sz", extractor.Decimal128),
                  ("open_px", extractor.Decimal128),
                  ("open_sz", extractor.Decimal128),
                  ("notional", extractor.Decimal128),
                  ("vwap", extractor.Decimal128))

    trade_descr = (("price", extractor.Decimal128),
                   ("qty", extractor.Decimal128),
                  #("side", extractor.Array(extractor.Char, 1)),
                   ("receive", extractor.Time64))

    # Wait until the YTP file is created
    while not os.path.exists(args.ytp):
        time.sleep(0.1)

    # Connect to Elasticsearch database
    es = Elasticsearch([f"http://{args.host}:{args.port}"])

    db_fields_array = [field[0] for field in bars_descr]

    def bar2db(x, market, imnt):
        print(x)
        if x[0].vwap == extractor.Decimal128(0):
            return
        # Populate the market data parameters into the database
        doc = {
            'timestamp': datetime.utcnow(),
            'market': f"'{market}'",
            'imnt': f"'{imnt}'",
        }
        for f in db_fields_array:
            doc[f] = extractor2elasticsvalue(getattr(x[0], f))
        res = es.index(index="market_data", document=doc)
        # TODO: UPSERT (ON CONFLICT)

    graph = extractor.system.comp_graph()
    op = graph.features

    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair

    def compute_bar(op, quote, trade, vendor_time):
        close_time = op.data_bar(vendor_time, timedelta(seconds=int(args.period)))
        open_time = op.tick_lag(close_time, 1)
        close_quote = op.left_lim(quote, close_time)
        open_quote = op.tick_lag(op.asof(quote, close_time), 1)

        high_quote = op.left_lim(op.asof(quote, op.max(quote.bidprice, close_time)), close_time)
        low_quote = op.left_lim(op.asof(quote, op.min(quote.askprice, close_time)), close_time)

        notional = op.left_lim(op.cumulative(trade.price * trade.qty), close_time)
        shares = op.left_lim(op.cumulative(trade.qty), close_time)
        prev_notional = op.tick_lag(notional, 1)
        prev_shares = op.tick_lag(shares, 1)
        notional = notional - prev_notional
        shares = shares - prev_shares

        first_trade = op.first_after(trade, close_time)
        open_trade_there = op.asof(first_trade, close_time)
        close_trade = op.asof(trade, close_time)
        no_trades = op.is_zero(shares)
        open_trade = op.cond(no_trades, close_trade, open_trade_there)

        high_trade_there = op.asof(op.asof(trade, op.max(trade.price, first_trade)), close_time)
        low_trade_there = op.asof(op.asof(trade, op.min(trade.price, first_trade)), close_time)

        high_trade = op.cond(no_trades, close_trade, high_trade_there)
        low_trade = op.cond(no_trades, close_trade, low_trade_there)

        # TODO: use mid price if no trade price exists yet
        vwap = op.cond(op.is_zero(shares), op.asof(trade.price, close_time), notional / shares)

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
            vwap, ("vwap",),
            notional, ("notional",),
            open_time, (("start", "open_time"),),
            close_time, (("start", "close_time"),),
            )
        
        # TODO: need to skip bars that have missing data
        return op.filter_unless(close_time.skipped, combined)

    def compute_bars(op, quotes, trades, times):
        return [compute_bar(op, quote, trd, ven) for quote, trd, ven, in zip(quotes, trades, times)]

    seq = ytp.sequence(args.ytp)
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer(args.peer)
    upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]

    levels = [op.book_build(upd, args.levels) for upd in upds]
    times = [op.book_vendor_time(upd) for upd in upds]

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

    bars = compute_bars(op, quotes, trades, times)

    # Add a callback for each bar that corresponds to a market/instrument pair
    for bar, mi, trade in zip(bars, mktimnt, trades):
       graph.callback(bar, functools.partial(bar2db, market=mi[0], imnt=mi[1]))

    # Run the extractor blocking
    graph.stream_ctx().run_live()
