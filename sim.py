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

def time_ns():
    return int(pytime.time() * 1000000000)

class MarketDataSim(MarketData):

    def __init__(self, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        super().__init__(peer, graph, prefix, period)

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        if self.quotes:
            return
        self.process(imnts)

class StrategyOrderUpdater:

    def __init__(self, orders):
        pass

    def update(self, upd):
        print("attempting to update", upd)
        strg = upd["strg"]
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        getattr(self, msgdata.which())(**getattr(msgdata, msgdata.which()).to_dict())

    def new(self, strgOrdID, accountID, securityId, venueID, orderSide, orderType, quantity, maxFloor, timeInForce, algorithm, minQty, tag):
        pass

    def cancel():
        pass

class StrategyOrderWriter:
    pass

class FillModel:

    def __init__(self, mktdata, orders):
        pass

class DelayQueue:

    def __init__(self, graph, delay):
        timer = graph.features.timer(timedelta(microseconds=1))
        graph.callback(timer, self.consume)
        self.delay = int(delay.total_seconds() * 1000000000)
        self.queue = []
        self.callbacks = []

    def consume(self, frame):
        curr_time_ns = int(frame[0].actual.total_seconds() * 1000000000)
        while self.queue and curr_time_ns >= self.queue[0][0] + self.delay:
            print("found element in queue that needs to be removed")
            elem = self.queue.pop(0)[1]
            for clbl in self.callbacks:
                clbl(elem)

    def push(self, item):
        self.queue.append((time_ns(), item))

    def callback(self, clbl):
        self.callbacks.append(clbl)

class AbstractOrderBook:
    pass

class SidedPriceFIFOPriorityOrderBook(AbstractOrderBook):
    pass

class SimOrderBook(SidedPriceFIFOPriorityOrderBook):
    pass

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

    orders = SimOrderBook()

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
        print("pushing to queue", {"strg": strg, "msg": msg})
        delay_queue.push({"strg": strg, "msg": msg})

    strg_seq.data_callback(oms_pfx, queue_push)

    refdata.poll()

    graph.stream_ctx().run_live()
