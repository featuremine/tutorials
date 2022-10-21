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
 * @file bars.py
 * @author Maxim Trokhimtchouk
 * @date 10 Aug 2020
 * @brief Building bars from book updates
 */
"""
import extractor as e
from datetime import datetime, timedelta, date
import pytz
import os
import argparse
from time import time_ns


def epoch_delta(date):
    return date - pytz.timezone("UTC").localize(datetime(1970, 1, 1))


def UTC_time(year, mon, day, h=0, m=0, s=0):
    return epoch_delta(pytz.timezone("UTC").
                       localize(datetime(year, mon, day, h, m, s)))


def date_range(start, end, step):
    while start <= end:
        yield start
        start += step


L3_source = 's3://fm-trial-dist/ORE/coinbase_btc-usd_{:%Y-%m-%d}.ore'
bar_source = 's3://fm-trial-dist/derived/coinbase_btc-usd_{:%Y-%m-%d}.{}.bars.csv'
resid_source = 's3://fm-trial-dist/derived/coinbase_btc-usd_{:%Y-%m-%d}.{}.resid.csv'
tickers = ["ETH-BTC", "BTC-USD", "ADA-USD"]
weights = {"ETH-BTC": 0.5, "BTC-USD": 0.5, "ADA-USD": 0.5}
prefix = "ore_data/imnts/coinbase/"


def compute_bar(op, bbo, trade, start, stop, bar_period):
    def quote_side_float64(quote, name):
        return op.cond(op.is_zero(op.field(quote, name)),
                       op.nan(quote),
                       op.convert(quote, e.Float64))

    def quote_float64(quote):
        bid_quote = op.fields(quote, ("bidprice", "bidqty"))
        ask_quote = op.fields(quote, ("askprice", "askqty"))
        return op.combine(quote_side_float64(bid_quote, "bidqty"), tuple(),
                          quote_side_float64(ask_quote, "askqty"), tuple())

    close = op.clock_timer(start, stop, bar_period)

    quote = op.fields(bbo, ("bidprice", "askprice", "bidqty", "askqty"))
    quote_bid = op.field(bbo, "bidprice")
    quote_ask = op.field(bbo, "askprice")
    open_quote = op.asof_prev(quote, close)
    close_quote = op.left_lim(quote, close)
    high_quote = op.left_lim(op.asof(quote, op.max(quote_ask, close)), close)
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


def compute_bars(op, quotes, trades, start, stop, period):
    return [compute_bar(op, quote, trd, start, stop, period) for quote, trd in zip(quotes, trades)]


def filter_quote(op, quote, maximum_spread_ratio=0.1):
    max_spread_ratio = op.constant(("max_spread_ratio", e.Float64, maximum_spread_ratio))
    midpx_multiplier = op.constant(("price", e.Float64, 0.5))
    cleanbidpx = op.filter_unless(op.is_zero(quote.bidqty), op.convert(quote.bidprice, e.Float64))
    cleanaskpx = op.filter_unless(op.is_zero(quote.askqty), op.convert(quote.askprice, e.Float64))
    spread = cleanaskpx - cleanbidpx
    raw_fairpx = midpx_multiplier * (cleanbidpx + cleanaskpx)
    bad_spread = spread / raw_fairpx > max_spread_ratio
    return op.filter_unless(bad_spread, quote)


def quotes_from_L3(op, upds):
    levels = [op.book_build(upd, 1) for upd in upds]
    return [op.combine(level,
                       (("bid_prx_0", "bidprice"),
                        ("bid_shr_0", "bidqty"),
                        ("ask_prx_0", "askprice"),
                        ("ask_shr_0", "askqty")))
            for level in levels]


def trades_from_L3(op, upds):
    return [op.combine(op.book_trades(upd),
                       (("trade_price", "price"),
                        ("vendor", "receive"),
                        ("qty", "qty")))
            for upd in upds]


def bars_L3(op, upds, start, stop, period):
    quotes = quotes_from_L3(op, upds)
    trades = trades_from_L3(op, upds)
    quotes_filtered = [filter_quote(op, quote) for quote in quotes]
    return compute_bars(op, quotes_filtered, trades, start, stop, period)


def bars_L3_s3(op, date: date, period, version, inurl, outurl, residurl):
    prevdate = date - timedelta(days=1)
    start = UTC_time(prevdate.year, prevdate.month, prevdate.day, 0)
    stop = UTC_time(prevdate.year, prevdate.month, prevdate.day, 23, 59, 59)

    infile = "aws s3 cp {} - |".format(inurl).format(date)
    outfile = "| aws s3 cp - {}".format(outurl).format(date, version)

    upds = op.book_play_split(infile, tuple([tickers[1]]))
    bars = bars_L3(op, upds, start=start, stop=stop, period=period)
    out_stream = op.join(*bars, "ticker", e.Array(e.Char, 16), tuple([tickers[1]]))
    op.csv_record(out_stream, outfile)

    if residurl:
        vwaps = [bar.vwap for bar in bars]
        rets = [vwap - op.tick_lag(vwap, 1) for vwap in vwaps]
        ws = [op.constant(("weight", e.Float64, weights[ticker])) for ticker in [tickers[1]]]
        sector = op.sum(*[w * ret for ret, w in zip(rets, ws)])
        sector_mean = op.sma_tick_mw(sector, 10)
        sector_stdev = op.stdev_tick_mw(sector, 10)
        resids = [ret - sector for ret in rets]
        resids_means = [op.sma_tick_mw(resid, 10) for resid in resids]
        resids_stdev = [op.stdev_tick_mw(resid, 10) for resid in resids]

        out = op.combine(
            sector, ("sector",),
            sector_mean, ("sector_mean",),
            sector_stdev, ("sector_stdev",),
            *resids, *[(f"resid({tick})",) for tick in [tickers[1]]],
            *resids_means, *[(f"resid_mean({tick})",) for tick in [tickers[1]]],
            *resids_stdev, *[(f"resid_stdev({tick})",) for tick in [tickers[1]]]
        )

        op.csv_record(out, "| aws s3 cp - {}".format(residurl).format(date, version))


def bars_L3_live(op, yamal, peer_name, date: date, period, channels=None):
    start = UTC_time(date.year, date.month, date.day, 0)
    stop = UTC_time(date.year, date.month, date.day, 23, 59, 59)

    from yamal import ytp
    seq = ytp.sequence(yamal, readonly=True)
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer(peer_name)
    if channels:
        upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]
    else:
        upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), prefix + ch))) for ch in tickers]
    return bars_L3(op, upds, start=start, stop=stop, period=period)


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


def bars_csv(op, date: date, version: str, outurl: str):
    '''Usage:
       bars = bars_csv(op, date(2020,6,1), '1')
    '''
    bars_command = "aws s3 cp {} - |".format(outurl).format(date, version)
    raw_bars = op.csv_play(bars_command, bars_descr)
    return op.split(raw_bars, "ticker", tuple(tickers))


def bars_L3_generate(first: date, second: date, version: str, inurl: str, outurl: str, residurl: str, dump: bool = False):
    for d in date_range(first, second, timedelta(days=1)):
        cmd = "aws s3 ls {}".format(inurl).format(d)
        if not os.system(cmd):
            print("processing date {:%Y-%m-%d} ...".format(d))
            graph = e.system.comp_graph()
            op = graph.features
            bars_L3_s3(
                op,
                date=d,
                period=timedelta(
                    minutes=1),
                version=version,
                inurl=inurl,
                outurl=outurl,
                residurl=residurl)
            if dump:
                graph_dump(graph)
            graph.stream_ctx().run()
        else:
            print("skipping {:%Y-%m-%d}".format(d))


def bars_L3_visualize(d: date, version: str, inurl: str, outurl: str, residurl: str):
    graph = e.system.comp_graph()
    op = graph.features
    bars_L3_s3(op, date=d, period=timedelta(minutes=1), version=version, inurl=inurl, outurl=outurl, residurl=residurl)
    g = graph_viz(graph)
    g.render(view=True)


def vwap_trade_trigger(op, bar, threshold=0.0):
    '''Usage:
       triggers = [vwap_trade_trigger(op, bar, 0.0005) for bar in bars]
    '''
    sell_threshold = op.constant(("threshold", e.Float64, threshold))
    buy_threshold = op.constant(("threshold", e.Float64, -threshold))
    vwap = bar.vwap
    prev_vwap = op.tick_lag(vwap, 1)
    signal = (vwap - prev_vwap) / vwap
    sell_signal = op.filter_if(signal > sell_threshold, signal)
    buy_signal = op.filter_if(signal < buy_threshold, signal)
    sell_info = op.combine(sell_signal, ("signal",), op.asof(bar, sell_signal), tuple())
    buy_info = op.combine(buy_signal, ("signal",), op.asof(bar, buy_signal), tuple())
    return buy_info, sell_info


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


if __name__ == "__main__":
    e.set_license("aws s3 cp s3://fm-trial-dist/featuremine.lic - |")

    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--residuals', default=None)
    parser.add_argument('-gv', '--graphviz', action='store_true')
    parser.add_argument('-dmp', '--dump', action='store_true')
    parser.add_argument('-i', '--input', default=L3_source)
    parser.add_argument('-o', '--output', default=bar_source)
    parser.add_argument('-s', "--startdate",
                        help='The Start Date - format YYYY-MM-DD',
                        default='2020-05-30',
                        type=valid_date)
    parser.add_argument('-e', '--enddate',
                        help='The End Date format YYYY-MM-DD (Inclusive)',
                        default='2020-06-10',
                        type=valid_date)

    args = parser.parse_args()

    if args.graphviz and args.dump:
        print("Please enable only one visualization flag.")
        exit(1)

    if args.residuals == "":
        args.residuals = resid_source

    if args.graphviz:
        from featuremine.tools.visualization import graph_viz, graph_dump
        bars_L3_visualize(args.startdate, '1', args.input, args.output, args.residuals)
    else:
        bars_L3_generate(args.startdate, args.enddate, '1', args.input, args.output, args.residuals, args.dump)
