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

class TradePlotter:
    def __init__(self, n, callback):
        self.tms = np.zeros(n, dtype='datetime64[ms]')
        self.tds = np.zeros((n,5), dtype=np.float64)
        self.bid = None
        self.ask = None
        self.idx = 0
        self.done = False
        self.callback = callback
    def times(self):
        return self.tms
    def trade(self, tm, px, qt, isbid):
        if self.bid is None or self.ask is None:
            return
        tm_us = int(tm / timedelta(microseconds=1))
        self.tms[self.idx] = np.datetime64(tm_us, 'us')
        self.tds[self.idx, 0] = self.bid
        self.tds[self.idx, 1] = self.ask
        self.tds[self.idx, 2] = float(px)
        self.tds[self.idx, 3] = float(qt)
        self.tds[self.idx, 4] = isbid
        self.idx += 1
        self.done = self.idx == self.tms.shape[0]
        if (self.done):
            self.callback(self)
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp-file", help="ytp file name", required=True)
    parser.add_argument("--market", help="market of security to display", required=False)
    parser.add_argument("--security", help="security to display", required=True)
    parser.add_argument("--points", help="number of trades", type=int, required=True)
    args = parser.parse_args()

    def draw_plot(data):
        fig = plt.figure()
        ax = fig.add_subplot(1,1,1)
        plt.title("Trades with Corresponding Best Bid and Offer")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Price")
        bts, bpx, bqt = data.bid_trades()
        ats, apx, aqt = data.ask_trades()
        avgtrd = (np.sum(bqt) + np.sum(aqt)) / (bqt.shape[0] + aqt.shape[0])
        plt.scatter(bts, bpx, marker='^', sizes=bqt/avgtrd*20.0, c='g')
        plt.scatter(ats, apx, marker='v', sizes=aqt/avgtrd*20.0, c='r')
        plt.plot(data.times(), data.bids(), c='g', linewidth = '2')
        plt.plot(data.times(), data.asks(), c='r', linewidth = '2')
        plt.grid()
        plt.show()
        exit()
    
    plotter = TradePlotter(args.points, draw_plot)

    graph = extractor.system.comp_graph()
    op = graph.features

    channel = ("ore/{0}/{1}".format(args.market, args.security),)
    upds = op.seq_ore_live_split(args.ytp_file, channel)
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
    graph.callback(trades[0], lambda ev: plotter.trade(ev[0].receive, ev[0].price, ev[0].qty, ev[0].side))
    graph.callback(bbos[0], lambda ev: plotter.quote(ev[0].bidprice, ev[0].askprice))

    graph.stream_ctx().run_live()

