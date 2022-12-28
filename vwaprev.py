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

from reference import ReferenceData, VWAPRevSignals
from common import AbstractOrderBook, SidedPriceFIFOPriorityOrderBook, StrategyOrderUpdater, ManagerMessageWriter

from yamal import ytp
from conveyor.utils import schemas
import extractor

class Strategies(object):
    class Key(NamedTuple):
        strategy: str
        account: int
        imnt: int
        venue: int
    def __init__(self, components):
        super().__init__()
        self.mktdata = components["mktdata"]
        self.writers = components["writers"]
        self._strategies = {}

    def get(self, key):
        writer = self.writers.get()
        obj = self[key] = FillModel(mktdata, ManagerMessageWriter(stream))
        self.mktdata.trade_callback(key.imnt, key.venue, obj.mkt_upd)
        return obj

class StrategyOrderWriters(object):
    def __init__(self):
        pass

    def get(self, strategy, account, imnt, venue):
        pass

class YamalSequence(object):

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    cfg = json.load(open(args.cfg))

    graph = extractor.system.comp_graph()
    op = graph.features
  
    state_seq = ytp.sequence(cfg["state_ytp"], readonly=True)
    state_peer = state_seq.peer(cfg["peer"])
    op.ytp_sequence(state_seq, timedelta(microseconds=1))

    refdata = ReferenceData(state_seq, cfg)

    strg_seq = ytp.sequence(cfg["strg_ytp"])
    strg_peer = strg_seq.peer(cfg["peer"])
    op.ytp_sequence(strg_seq, timedelta(microseconds=1))

    writers = StrategyOrderWriters(strg_peer)

    signals = VWAPRevSignals(graph, state_peer)

    orders = defaultdict(SidedPriceFIFOPriorityOrderBook)

    strategies = Strategies(refdata=refdata, signals=signals, writers=writers, orders=orders)
    
    ref_called = False
    def refdata_cb(delta):
        if ref_called:
            return
        ref_called = True
        for venid, securities in delta.venuesSecurities.items():
            for secid in securities:
                strategies.get(secid=secid, venid=venid)
    refdata.add_callback(refdata_cb)
 
    strg_pfx = cfg["strg_pfx"]
    oms_name = cfg["oms_name"]

    def mapper(upd):
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        d = getattr(msgdata, msgdata.which())
        return Strategies.Key(strategy=upd['strg'], account=d.accountID, imnt=d.securityId, venue=d.venueID)

    updater = StrategyOrderUpdater(mapper, orders)

    strg_pfx_len = len(strg_pfx)
    oms_name_len = len(oms_name)

    def queue_push(peer, channel, time, data):
        rest = channel.name()[strg_pfx_len:]
        strg = rest[oms_name_len + 1:] if rest.startswith(oms_name) else rest[:-oms_name_len - 1]
        msg = capnp_spec.from_bytes_packed(data)
        updater.update({"strg": strg, "msg": msg})

    strg_seq.data_callback(strg_pfx, queue_push)

    refdata.poll()

    graph.stream_ctx().run_live()
