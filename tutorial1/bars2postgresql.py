import argparse
import extractor
import ytp
from datetime import datetime, timedelta, date
import pytz
from time import time_ns

prefix = "ore_data/imnts"

def epoch_delta(date):
    return date - pytz.timezone("UTC").localize(datetime(1970, 1, 1))

def UTC_time(year, mon, day, h=0, m=0, s=0):
    return epoch_delta(pytz.timezone("UTC").
                       localize(datetime(year, mon, day, h, m, s)))

def compute_bar(op, bbo, trade, start, stop, bar_period):
    def quote_side_float64(quote, name):
        return op.cond(op.is_zero(op.field(quote, name)),
                       op.nan(quote),
                       op.convert(quote, extractor.Float64))

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

    ftrade_px = op.convert(trade_px, extractor.Float64)
    ftrade_qty = op.convert(trade.qty, extractor.Float64)
    total_notional = op.left_lim(op.cumulative(ftrade_px * ftrade_qty), close)
    total_shares = op.left_lim(op.cumulative(ftrade_qty), close)
    prev_total_notional = op.tick_lag(total_notional, 1)
    prev_total_shares = op.tick_lag(total_shares, 1)
    notional = total_notional - prev_total_notional
    shares = total_shares - prev_total_shares
    vwap = op.cond(op.is_zero(shares), op.convert(open_trade.price, extractor.Float64), notional / shares)

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
    max_spread_ratio = op.constant(("max_spread_ratio", extractor.Float64, maximum_spread_ratio))
    midpx_multiplier = op.constant(("price", extractor.Float64, 0.5))
    cleanbidpx = op.filter_unless(op.is_zero(quote.bidqty), op.convert(quote.bidprice, extractor.Float64))
    cleanaskpx = op.filter_unless(op.is_zero(quote.askqty), op.convert(quote.askprice, extractor.Float64))
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


def bars_L3_live(op, yamal, peer_name, channels, date: date, period):
    start = UTC_time(date.year, date.month, date.day, 0)
    stop = UTC_time(date.year, date.month, date.day, 23, 59, 59)
    seq = ytp.sequence(yamal, readonly=True)
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer(peer_name)
    upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]
    return bars_L3(op, upds, start=start, stop=stop, period=period)

def print_vwap(x):
    print(x)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp", help="YTP file", required=True)
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to '../test/test.lic' if not provided)",
        required=False,
        default="../test/test.lic")
    args = parser.parse_args()

    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

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
    for imnt in args.imnts.split(','):
        for mkt in args.markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"]

    bars = bars_L3_live(op, args.ytp, "feed_handler", channels, date.today(), period=timedelta(seconds=1))
    for bar in bars:
        graph.callback(op.field(bar, "vwap"), print_vwap)

    graph.stream_ctx().run_live()
