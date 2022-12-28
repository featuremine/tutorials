import argparse
import json
import time as pytime
from typing import Dict, Tuple, NamedTuple, Optional, Callable, Any
from datetime import timedelta
import queue
from collections import defaultdict
import functools
from bisect import insort, bisect_left
from logging import getLogger
from datetime import timedelta

from reference import ReferenceData, MarketDataCallbacks
from common import AbstractOrderBook, SidedPriceFIFOPriorityOrderBook, StrategyOrderUpdater, ManagerMessageWriter

from yamal import ytp
from conveyor.utils import schemas
import extractor

capnp_spec = schemas.strategy.ManagerMessage

# Simulator
# message    ->     DelayQueue
#                       |
#             StrategyMessageUpdater
#                       |
#                    Orders           ->          Fillmodel     -> response 


# message    ->   StrategyMessageUpdater
#                       |
#                    Orders           ->        PostgressUpdater


# message    ->  StrategyMessageUpdater
#                       |
#                    Orders           ->        GUIUpdater

# message    ->  StrategyMessageUpdater
#                       |
#                    Orders           ->        Accounts    -> Strategy -> yamal

# in C we need to implement event queue and subscription and timers


def time_ns():
    return int(pytime.time() * 1000000000)

class FillModel(AbstractOrderBook):
    def __init__(self, mktdata, responder):
        self.mktdata = mktdata
        self.responder = responder
        self.book = SidedPriceFIFOPriorityOrderBook()

    def add(self, key, px, qty, side, info):

        #TODO: validate duplicate order ids

        mktdata_key = (info["venueID"], info["securityId"])

        if mktdata_key not in self.mktdata.quotes:
            self.responder.failed(info, "price not available for security in provided venue")
            return

        price_ref = graph.get_ref(self.mktdata.quotes[mktdata_key])
        fillpx = price_ref[0].askpx if orderside == "buy" else price_ref[0].bidpx

        def worse(px, other):
            return px > other if orderside == "buy" else px < other

        if px is None or not worse(px, fillpx):
            # self.book.cancel(key, px, qty, side)
            self.responder.filled(fillpx, qty, side, info)
            return

        if info['timeInForce'] == 'ioc':
            self.responder.canceled(side, info, 0)
        else:
            #please the rest on the book
            self.book.add(key, px, qty, side, info)
            self.responder.placed(px, qty, side, info)

    def cancel(self, key, qty, side, info):
        if key in self.book:
            self.book.cancel(key, qty, side, info)

    def mkt_upd(self, frame):
        side = frame[0].side
        px = frame[0].price
        quantity = frame[0].qty
        ords = self.book.side(side)
        worse = self.book.pxcmp[side]

        while ords:
            o = ords[0]

            if quantity == 0 or worse(o.price, px):
                break

            filled = min(quantity, o.leaves)
            self.book.cancel(o, filled)
            if filled == o.leaves:
                self.responder.partiallyFilled(px, filled, side, o.info)
            else:
                self.responder.filled(px, filled, side, o.info)

class DelayQueue:

    def __init__(self, graph, delay):
        timer = graph.features.timer(timedelta(microseconds=1))
        graph.callback(timer, self.consume)
        self.delay = int(delay.total_seconds() * 1000000000)
        self.queue = []
        self.callbacks = []

    def consume(self, frame):
        curr_time_ns = time_ns()
        while self.queue and curr_time_ns >= self.queue[0][0]:
            elem = self.queue.pop(0)[1]
            for clbl in self.callbacks:
                clbl(elem)

    def push(self, item):
        self.queue.append((time_ns() + self.delay, item))

    def callback(self, clbl):
        self.callbacks.append(clbl)

class FillModels(dict):
    def __init__(self, mktdata, peer, strg_pfx, oms_name):
        super().__init__()
        self.mktdata = mktdata
        self.peer = peer
        self.strg_pfx = strg_pfx
        self.oms_name = oms_name

    def __missing__(self, key):
        stream = self.peer.stream(self.peer.channel(time_ns(), self.strg_pfx + key.strategy + "/" + self.oms_name))
        obj = self[key] = FillModel(mktdata, ManagerMessageWriter(stream))
        self.mktdata.trade_callback(key.imnt, key.venue, obj.mkt_upd)
        return obj

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    cfg = json.load(open(args.cfg))

    graph = extractor.system.comp_graph()
    op = graph.features

    state_seq = ytp.sequence(cfg["state_ytp"], readonly=True)
    state_peer = state_seq.peer(cfg["peer"])
    op.ytp_sequence(state_seq, timedelta(microseconds=1))

    strg_seq = ytp.sequence(cfg["strg_ytp"])
    strg_peer = strg_seq.peer(cfg["peer"])
    op.ytp_sequence(strg_seq, timedelta(microseconds=1))

    mktdata = MarketDataCallbacks(state_peer, graph)

    refdata = ReferenceData(state_seq, cfg)
    def refdata_cb(delta):
        # Subscribe to market data
        # make sure we dont subscribe more than once per pair
        imnts = {}
        for venid, securities in delta.venuesSecurities.items():
            venue = refdata.state.venuesNames[venid]
            market = venue.exdest if venue.exdest else venue.code
            for secid in securities:
                symbol = refdata.state.securities[secid].symbol
                imnts[(venid, secid)] = (market, symbol)
        mktdata.subscribe(imnts)
    refdata.add_callback(refdata_cb)

    strg_pfx = f'{cfg["strg_pfx"]}'
    oms_name = cfg["oms_name"]
    fillmodels = FillModels(mktdata, strg_peer, strg_pfx, oms_name)

    class Key(NamedTuple):
        strategy: str
        account: int
        imnt: int
        venue: int

    def mapper(upd):
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        specdata = getattr(msgdata, msgdata.which())
        return Key(strategy=upd['strg'], account=specdata.accountID, imnt=specdata.securityId, venue=specdata.venueID)

    updater = StrategyOrderUpdater(mapper, fillmodels)

    # subscribe order
    # Set up callbacks for market data updates

    delay_queue = DelayQueue(graph, delay=timedelta(milliseconds=cfg["sim_delay"]))
    delay_queue.callback(updater.update)

    strg_pfx_len = len(strg_pfx)
    oms_name_len = len(oms_name)

    def queue_push(peer, channel, time, data):
        rest = channel.name()[strg_pfx_len:]
        strg = rest[oms_name_len + 1:] if rest.startswith(oms_name) else rest[:-oms_name_len - 1]
        msg = capnp_spec.from_bytes_packed(data)
        delay_queue.push({"strg": strg, "msg": msg})

    strg_seq.data_callback(strg_pfx, queue_push)

    refdata.poll()

    graph.stream_ctx().run_live()
