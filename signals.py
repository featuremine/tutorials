from collections import defaultdict
from typing import Dict, Tuple, Optional
from datetime import timedelta

import extractor

from common import SystemTime

class MarketSignals(object):
    def __init__(self, components, peer, prefix: str, sample: Optional[timedelta]=None) -> None:
        self.peer = peer
        self.graph = components["graph"]
        self.systime = components["systime"]
        self.prefix = prefix
        self.sample = sample
        self.quotes = {}
        self.times = {}
        self.trades = {}

        op = self.graph.features
        if self.sample:
            self.close = op.timer(self.sample)

    def process(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        op = self.graph.features

        for ids, syms in imnts.items():
            # NOTE: maybe we will need to address symbology changes
            if ids in self.quotes:
                continue

            channel = self.peer.channel(self.systime(), f"{self.prefix}/{syms[0]}/{syms[1]}")
            upd = op.decode_data(op.ore_ytp_decode(channel))
            level = op.combine(op.book_build(upd, 1),
                            (("bid_prx_0", "bidprice"),
                            ("bid_shr_0", "bidqty"),
                            ("ask_prx_0", "askprice"),
                            ("ask_shr_0", "askqty")))
            if self.sample:
                quote = op.asof(level, self.close)
            else:
                quote = level
            self.quotes[ids] = quote
            self.times[ids] = op.book_vendor_time(upd)
            self.trades[ids] = op.combine(op.book_trades(upd),
                                    (("trade_price", "price"),
                                    ("vendor", "receive"),
                                    ("qty", "qty"),
                                    ("decoration", "side")))

    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str, str]]) -> None:
        if self.quotes:
            return
        self.process(imnts)


class BarSignals(MarketSignals):
    def __init__(self, components, peer, prefix: str, period, sample: Optional[timedelta] = None) -> None:
        super().__init__(components, peer, prefix, sample)
        self.period = period
        self.bars = {}

    def process(self, imnts: Dict[Tuple[int, int], Tuple[str, str]]) -> None:
        super().process(imnts)

        op = self.graph.features

        def compute_bar(op, quote, trade, vendor_time):
            close_time = op.data_bar(
                vendor_time, timedelta(seconds=int(self.period)))
            open_time = op.tick_lag(close_time, 1)
            close_quote = op.left_lim(quote, close_time)
            open_quote = op.tick_lag(op.asof(quote, close_time), 1)

            high_quote = op.left_lim(
                op.asof(quote, op.max(quote.bidprice, close_time)), close_time)
            low_quote = op.left_lim(op.asof(quote, op.min(
                quote.askprice, close_time)), close_time)

            notional = op.left_lim(op.cumulative(
                trade.price * trade.qty), close_time)
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

            high_trade_there = op.asof(
                op.asof(trade, op.max(trade.price, first_trade)), close_time)
            low_trade_there = op.asof(
                op.asof(trade, op.min(trade.price, first_trade)), close_time)

            high_trade = op.cond(no_trades, close_trade, high_trade_there)
            low_trade = op.cond(no_trades, close_trade, low_trade_there)

            # TODO: use mid price if no trade price exists yet
            vwap = op.cond(op.is_zero(shares), op.asof(
                trade.price, close_time), notional / shares)

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


        for ids, syms in imnts.items():
            # NOTE: maybe we will need to address symbology changes
            if ids in self.bars:
                continue

            self.bars[ids] = compute_bar(op, self.quotes[ids], self.trades[ids], self.times[ids])


class VWAPRevSignals(BarSignals):
    def __init__(self, components, peer, prefix: str, period, threshold, sample: Optional[timedelta] = None) -> None:
        super().__init__(components, peer, prefix, period, sample)
        self.vwaprev = {}
        self.threshold = threshold

    def process(self, imnts: Dict[Tuple[int, int], Tuple[str, str]]) -> None:
        super().process(imnts)

        op = self.graph.features

        def vwap_rev_signal(bar):
            sell_threshold = op.constant(("threshold", extractor.Float64, self.threshold))
            buy_threshold = op.constant(("threshold", extractor.Float64, -self.threshold))
            vwap = bar.vwap
            prev_vwap = op.tick_lag(vwap, 1)
            signal = (vwap - prev_vwap) / vwap
            sell_signal = op.filter_if(signal > sell_threshold, signal)
            buy_signal = op.filter_if(signal < buy_threshold, signal)
            sell_info = op.combine(sell_signal, ("signal",),
                                op.asof(bar, sell_signal), tuple())
            buy_info = op.combine(buy_signal, ("signal",),
                                op.asof(bar, buy_signal), tuple())
            return buy_info, sell_info

        for ids, syms in imnts.items():
            # NOTE: maybe we will need to address symbology changes
            if ids in self.vwaprev:
                continue

            self.vwaprev[ids] = vwap_rev_signal(self.bars[ids])
