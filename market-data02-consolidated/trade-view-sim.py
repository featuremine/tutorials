"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.
        
        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import argparse
import extractor
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
from functools import partial

class TradePlotter:
    def __init__(self):
        self.tms = np.empty((0),dtype='datetime64[ms]')
        self.tds = np.empty((0, 5),dtype=np.float64)
        self.bid = None
        self.ask = None
        self.idx = 0
    def times(self):
        return self.tms
    def trade(self, tm, px, qt, isbid):
        if self.bid is None or self.ask is None:
            return
        tm_us = int(tm / timedelta(microseconds=1))
        self.tms.resize(self.idx + 1)
        self.tms[self.idx] = np.datetime64(tm_us, 'us')
        tds = np.zeros(5, dtype=np.float64)
        tds[0] = self.bid
        tds[1] = self.ask
        tds[2] = float(px)
        tds[3] = float(qt)
        tds[4] = isbid
        self.tds.resize((self.idx + 1, 5))
        self.tds[self.idx] = tds
        self.idx += 1
    def bids(self):
        return self.tds[:,0]
    def asks(self):
        return self.tds[:,1]
    def bid_trades(self):
        sel = self.tds[:,4] == True
        return self.tms[sel], self.tds[sel,2], self.tds[sel,3]
    def ask_trades(self):
        sel = self.tds[:,4] == False
        return self.tms[sel], self.tds[sel,2], self.tds[sel,3]
    def quote(self, bid, ask):
        self.bid = float(bid)
        self.ask = float(ask)

from datetime import datetime

def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S") - datetime(1970,1,1)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp-file", help="ytp file name", required=True)
    parser.add_argument("--market", help="market of security to display", required=True, nargs='+')
    parser.add_argument("--security", help="security to display", required=True, nargs='+')
    parser.add_argument('-s', "--start",
                        help='The Start Datetime - format YYYY-MM-DDThh:mm:ss',
                        default=None,
                        type=valid_date)
    parser.add_argument('-e', '--end',
                        help='The End Date format YYYY-MM-DDThh:mm:ss (Inclusive)',
                        default=None,
                        type=valid_date)
    args = parser.parse_args()

    plotters = {}
    graph = extractor.system.comp_graph()
    op = graph.features

    for market in args.market:
      for security in args.security:
        plotter = TradePlotter()

        channel = ("ore/{0}/{1}".format(market, security),)
        upds = op.seq_ore_sim_split(args.ytp_file, channel)
        headers = [op.book_header(upd) for upd in upds]

        levels = [op.book_build(upd, 1) for upd in upds]
        lvlhdrs = [op.asof(hdr, lvl) for hdr, lvl in zip(headers, levels)]
        bbos = [op.combine(
            level, (
                ("bid_prx_0", "bidprice"),
                ("ask_prx_0", "askprice"),
                ("bid_shr_0", "bidqty"),
                ("ask_shr_0", "askqty")
            ),
            hdr, (("receive", "receive"),)) for level, hdr in zip(levels, lvlhdrs)]

        const_b = op.constant(('decoration', extractor.Array(extractor.Char, 4), 'b'))
        const_a = op.constant(('decoration', extractor.Array(extractor.Char, 4), 'a'))
        const_u = op.constant(('decoration', extractor.Array(extractor.Char, 4), 'u'))
        def normalize_trade(trade):
            decoration_equals_a = trade.decoration == const_a
            decoration_equals_b = trade.decoration == const_b
            const_n_value_b = op.constant(('side', extractor.Int32, 0))
            const_n_value_a = op.constant(('side', extractor.Int32, 1))
            const_n_value_u = op.constant(('side', extractor.Int32, 2))
            eq_b = op.cond(decoration_equals_b, const_n_value_b, const_n_value_u)
            side = op.cond(decoration_equals_a, const_n_value_a, eq_b)

            return op.combine(
                trade, (
                    ("trade_price", "price"),
                    ("receive", "receive"),
                    ("qty", "qty")
                ),
                side, (("side", "side"),))

        trades = [normalize_trade(op.book_trades(upd)) for upd in upds]

        # Then subscribe to message callbacks.
        def valid_time(ev):
            return (args.start is None or ev[0].receive >= args.start) and \
                   (args.end is None or ev[0].receive <= args.end)
        graph.callback(trades[0], partial(lambda ev, pltr: pltr.trade(ev[0].receive, ev[0].price, ev[0].qty, ev[0].side) if valid_time(ev) else None, pltr=plotter))
        graph.callback(bbos[0], partial(lambda ev, pltr: pltr.quote(ev[0].bidprice, ev[0].askprice) if valid_time(ev) else None, pltr=plotter))

        plotters[market, security] = plotter

    graph.stream_ctx().run()

    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    plt.title("Trades with Corresponding Best Bid and Offer")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Price")
    clridx = 0

    def draw_plot(mkt, sec, data):
        bts, bpx, bqt = data.bid_trades()
        ats, apx, aqt = data.ask_trades()
        avgtrd = (np.sum(bqt) + np.sum(aqt)) / (bqt.shape[0] + aqt.shape[0])
        bidscttr = plt.scatter(bts, bpx, marker='^', sizes=bqt/avgtrd*20.0)
        askscttr = plt.scatter(ats, apx, marker='v', sizes=aqt/avgtrd*20.0)
        plt.plot(data.times(), data.bids(), c=bidscttr.get_facecolor(), linewidth = '2', label=f"Bids, {mkt}/{sec}")
        plt.plot(data.times(), data.asks(), c=askscttr.get_facecolor(), linewidth = '2', label=f"Asks, {mkt}/{sec}")

    for key, plotter in plotters.items():
        mkt, sec = key
        draw_plot(mkt, sec, plotter)

    plt.grid()
    plt.legend(loc='lower left')
    plt.show()


