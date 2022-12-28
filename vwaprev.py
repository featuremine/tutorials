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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    cfg = json.load(open(args.cfg))

    components = {}

    components["graph"] = extractor.system.comp_graph()
    op = components["graph"].features

    state_seq = ytp.sequence(cfg["state_ytp"], readonly=True)
    state_peer = state_seq.peer(cfg["peer"])
    op.ytp_sequence(state_seq, timedelta(microseconds=1))

    strg_seq = ytp.sequence(cfg["strg_ytp"])
    strg_peer = strg_seq.peer(cfg["peer"])
    op.ytp_sequence(strg_seq, timedelta(microseconds=1))

    signals = VWAPRevSignals(components["graph"], state_peer)
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
        signals.subscribe(imnts)
    refdata.add_callback(refdata_cb)

    strg_pfx = f'{cfg["strg_pfx"]}'
    oms_name = cfg["oms_name"]

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

    delay_queue = DelayQueue(
        graph, delay=timedelta(milliseconds=cfg["sim_delay"]))
    delay_queue.callback(updater.update)

    strg_pfx_len = len(strg_pfx)
    oms_name_len = len(oms_name)

    def queue_push(peer, channel, time, data):
        rest = channel.name()[strg_pfx_len:]
        strg = rest[oms_name_len +
                    1:] if rest.startswith(oms_name) else rest[:-oms_name_len - 1]
        msg = capnp_spec.from_bytes_packed(data)
        delay_queue.push({"strg": strg, "msg": msg})

    strg_seq.data_callback(strg_pfx, queue_push)

    refdata.poll()

    graph.stream_ctx().run_live()
