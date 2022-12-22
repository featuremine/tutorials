import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
import time as pytime
from typing import Dict, Tuple, NamedTuple, Optional
from datetime import timedelta
import queue
from collections import defaultdict
import functools
from bisect import insort, bisect_left
from logging import getLogger
from datetime import timedelta
from conveyor.utils import schemas
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

class AbstractOrderBook:
    def __init__(self):
        self._order_dict = dict()
        # order heap is am array sorted by price time priority
        self._order_heap[0] = []
        self._order_heap[1] = []
        self.pxcmp = (bidcmp, askcmp)

    def add(key, px, qty, side, info):
        raise NotImplementedError('not implemented')

    def __getitem__(self, key):
        pass

    def bid(self):
        pass

    def ask(self):
        pass

class SidedPriceFIFOPriorityOrderBook(AbstractOrderBook):
    pass

class MarketDataSim(MarketData):

    def __init__(self, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        super().__init__(peer, graph, prefix, period)

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        if self.quotes:
            return
        self.process(imnts)

    def callback(self, imnt, venue, call):
        pass

class StrategyOrderWriter:
    pass

class FillModel(AbstractOrderBook):
    def __init__(self, mktdata, orders):
        pass

    def add(key, px, qty, side, info):
        if px is None:
            #execute market order
            pass

        #check whether it can be executed immideately

        if info['timeInForce'] == 'IOC':
            #cancel what is left
            pass
        else:
            #please the rest on the book
            pass

class StrategyOrderUpdater:

    def __init__(self, mapper: callable[dict, any], books: dict[AbstractOrderBook]):
        pass

    def update(self, upd):
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        if not 'StrgOrdID' in msgdata:
            return
        bookkey = self.mapper(upd)
        book = self.books[bookkey]
        ordkey = (upd["strg"], msgdata['StrgOrdID'])
        getattr(self, msgdata.which())(ordkey, book, **getattr(msgdata, msgdata.which()).to_dict())

    def new(self, ordkey, book, orderType, quantity, side,  **kwargs):
        px = None if 'market' in orderType else orderType['limit']
        book.add(ordkey, px=px, qty=quantity, side=side, info=kwargs)

    def cancel(self, strategy, strgOrdID):
        pass

    def replace(self, strategy, strgOrdID, price, quantity):
        pass

    def failed(self, strategy, strgOrdID, type, reason, requestTime, tag):
        pass

    def cancelRej(self, strategy, strgOrdID, reason, sessOrdID, transactTime, requestTime, tag, receiveTime):
        pass

    def replaceRej(self, strategy, strgOrdID, reason, sessOrdID, transactTime, requestTime, tag, receiveTime):
        pass

    def exec(self, data, **execargs):
        for exectype, execdata in data.items():
            if execdata is None:
                getattr(self, exectype)(**execargs)
            else:
                getattr(self, exectype)(**execargs, **execdata)

    def placed(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, orderType, orderQuantity):
        pass

    def replaced(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, orderType, orderQuantity):
        pass

    def partiallyFilled(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, lastQuantity, lastPrice, lastFees, liquidityCode, cumQty, leaves, avgPx, lastMkt):
        pass

    def filled(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, lastQuantity, lastPrice, lastFees, liquidityCode, cumQty, leaves, avgPx, lastMkt):
        pass

    def rejected(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, reason):
        pass

    def doneForDay(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, leaves):
        pass

    def canceled(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, leaves):
        pass

    def expired(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, leaves):
        pass

    def pendingNew(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime):
        pass

    def pendingCancel(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime):
        pass

    def pendingReplace(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime):
        pass

    def correction(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, cumQty, leaves, avgPx, lastQuantity, execRefID):
        pass

    def bust(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, cumQty, leaves, avgPx, lastQuantity, execRefID):
        pass

    def restated(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, cumQty, leaves, avgPx):
        pass

    def status(self, strategy, strgOrdID, accountID, securityId, venueID, orderSide, sessOrdID, exchExecID, exchOrdID, transactTime, executingBroker, requestTime, tag, receiveTime, cumQty, leaves, avgPx):
        pass

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

class FillModels(defaultdict):
    def __missing__(self, key: _KT) -> _VT:
        obj = FillModel()
        self.mktdata.callback(key.imnt, key.venue, obj.mkt_upd)

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

    mktdata = MarketDataSim(state_peer, graph)

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

    orders = FillModels(mktdata)

    updater = StrategyOrderUpdater(orders)
    writer = StrategyOrderWriter()

    fillmodel = FillModel(mktdata, orders)

    # subscribe order
    # Set up callbacks for market data updates

    delay_queue = DelayQueue(graph, delay=timedelta(milliseconds=cfg["sim_delay"]))
    delay_queue.callback(updater.update)

    oms_pfx = f'{cfg["strg_pfx"]}{cfg["OMS_name"]}/'
    oms_pfx_len = len(oms_pfx)
    def queue_push(peer, channel, time, data):
        strg = channel.name()[oms_pfx_len:]
        msg = capnp_spec.from_bytes_packed(data)
        delay_queue.push({"strg": strg, "msg": msg})

    strg_seq.data_callback(oms_pfx, queue_push)

    refdata.poll()

    graph.stream_ctx().run_live()
