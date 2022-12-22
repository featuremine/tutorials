import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
import time as pytime
from typing import Dict, Tuple, NamedTuple, Optional, Callable, Any
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

    def add(self, key, px, qty, side, info):
        raise NotImplementedError('not implemented')

    def cancel(self, key, qty, side, info):
        raise NotImplementedError('not implemented')

    def __getitem__(self, key):
        raise NotImplementedError('not implemented')

    def __contains__(self, key):
        raise NotImplementedError('not implemented')

    def bid(self):
        return self.side(0)

    def ask(self):
        return self.side(1)

    def side(self, i):
        raise NotImplementedError('not implemented')


def QueuedOrderComp(first, second):
    if first.side == "buy":
        if first.px < second.px:
            return 1
        elif first.px > second.px:
            return -1
    else:
        if first.px > second.px:
            return 1
        elif first.px < second.px:
            return -1
    if first.time > second.time:
        return 1
    if first.time < second.time:
        return -1
    return 0

class QueuedOrder(object):
    def __init__(self, now, px: float, qty: float, side, info):
        self.time = now
        self.px = px
        self.qty = qty
        self.leaves = qty
        self.side = side
        self.info = info

    def __gt__(self, other):
        return QueuedOrderComp(self, other) == 1

    def __lt__(self, other):
        return QueuedOrderComp(self, other) == -1

class SidedPriceFIFOPriorityOrderBook(AbstractOrderBook):
    def __init__(self):
        self._order_dict = dict()
        # each order heap is an array sorted by price time priority
        self._order_heap = ([], [])
        self.pxcmp = (lambda x, y: x < y, lambda x, y: x > y)

    def add(self, key, px, qty, side, info):
        order = QueuedOrder(time_ns(), px, qty, side, info)
        insort(self._order_heap[1 * side == "buy"], order)
        self._order_dict[key] = order

    def cancel(self, key, qty, side, info):
        order = self._order_dict[key]
        ords = self._order_heap[1 * side == "buy"]
        idx = bisect_left(ords, order)

        for x in range(idx, len(ords)):
            o = ords[x]
            if (info["strgOrdID"] == o.id):
                o.leaves -= qty
                if qty == 0:
                    ords.pop(x)
                    del self._order_dict[key]
                return

    def __getitem__(self, key):
        return self._order_dict[key]

    def __contains__(self, key):
        return key in self._order_dict

    def side(self, i):
        return self._order_heap[i]

class MarketDataSim(MarketData):

    def __init__(self, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        super().__init__(peer, graph, prefix, period)

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        if self.quotes:
            return
        self.process(imnts)

    def trade_callback(self, imnt, venue, call):
        pass

    def quote_callback(self, imnt, venue, call):
        pass


def strg_placed(orderid, accid, securityid, venueid, side, execid, price, quantity, transact_time, executing_broker):
    return {
        "message": {
            "sess": {
                "exec": {
                    "strgOrdID": orderid,
                    "accountID": accid,
                    "securityId": securityid,
                    "venueID": venueid,
                    "orderSide": side,
                    "sessOrdID": str(orderid),
                    "exchExecID": execid,
                    "exchOrdID": str(orderid),
                    "transactTime": transact_time,
                    "executingBroker": executing_broker,
                    "data": {
                        "placed": {
                            "orderType": {
                                "market": None
                            } if price is None else {
                                "limit": price
                            },
                            "orderQuantity": quantity
                        }
                    }
                }
            }
        }
    }


def strg_fail(orderid, failure_type, reason, request_time):
    return {
            "message": {
                "sess": {
                    "failed": {
                        "strgOrdID": orderid,
                        "type": failure_type,
                        "reason": reason,
                        "requestTime": request_time
                    }
                }
            }
        }



def strg_filled(orderid, accid, securityid, venueid, side, execid, price, quantity, transact_time, executing_broker):
    return {
        "message": {
            "sess": {
                "exec": {
                    "strgOrdID": orderid,
                    "accountID": accid,
                    "securityId": securityid,
                    "venueID": venueid,
                    "orderSide": side,
                    "sessOrdID": str(orderid),
                    "exchExecID": execid,
                    "exchOrdID": str(orderid),
                    "transactTime": transact_time,
                    "executingBroker": executing_broker,
                    "data": {
                        "filled": {
                            "lastQuantity": quantity,
                            "lastPrice": price,
                            "lastFees": 0,
                            "liquidityCode": 0,
                            "cumQty": quantity,
                            "leaves": 0,
                            "avgPx": price,
                            "lastMkt": executing_broker
                        }
                    }
                }
            }
        }
    }


def strg_canceled(orderid, accid, securityid, venueid, side, execid, transact_time, executing_broker):
    return {
        "message": {
            "sess": {
                "exec": {
                    "strgOrdID": orderid,
                    "accountID": accid,
                    "securityId": securityid,
                    "venueID": venueid,
                    "orderSide": side,
                    "sessOrdID": str(orderid),
                    "exchExecID": execid,
                    "exchOrdID": str(orderid),
                    "transactTime": transact_time,
                    "executingBroker": executing_broker,
                    "data": {
                        "canceled": {
                            "leaves": 0
                        }
                    }
                }
            }
        }
    }


class StrategyOrderWriter:
    def __init__(self, stream):
        self.stream = stream
        self.execid = 0

    def send_message(self, msg_builder, *args, **kwargs):
        response = capnp_spec.new_message()
        msg_dict = msg_builder(*args, **kwargs)
        response.from_dict(msg_dict)
        encoded_response = response.to_bytes_packed()
        self.stream.write(time_ns(), encoded_response)

    def placed(self, px, qty, side, info):
        self.execid += 1
        self.send_message(strg_placed, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

    def failed(self, info, reason):
        #TODO: report back actual request time from YTP instead of current time?
        self.send_message(strg_fail, info['strgOrdID'], "place", reason, time_ns())

    def canceled(self, side, info, leaves):
        self.execid += 1
        self.send_message(strg_canceled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), time_ns(), "SimulatorFM")

    def filled(self, px, qty, side, info):
        self.execid += 1
        self.send_message(strg_filled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

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

class StrategyOrderUpdater:

    def __init__(self, mapper: Callable[[dict], Any], books: Dict[Any, AbstractOrderBook]):
        self.mapper = mapper
        self.books = books

    def update(self, upd):
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        specdata = getattr(msgdata, msgdata.which())
        if not hasattr(specdata, 'strgOrdID'):
            return
        bookkey = self.mapper(upd)
        book = self.books[bookkey]
        ordkey = (upd["strg"], specdata.strgOrdID)
        getattr(self, msgdata.which())(ordkey, book, **specdata.to_dict())

    def new(self, ordkey, book, orderType, quantity, orderSide, **kwargs):
        px = None if 'market' in orderType else orderType['limit']
        book.add(key=ordkey, px=px, qty=quantity, side=orderSide, info=kwargs)

    def cancel(self, ordkey, book, **kwargs):
        pass

    def replace(self, ordkey, book, price, quantity, **kwargs):
        pass

    def exec(self, ordkey, book, data, **execargs):
        for exectype, execdata in data.items():
            if execdata is None:
                getattr(self, exectype)(ordkey, book, **execargs)
            else:
                getattr(self, exectype)(ordkey, book, **execargs, **execdata)

    def placed(self, ordkey, book, orderType, orderQuantity, **kwargs):
        pass

    def replaced(self, ordkey, book, orderType, orderQuantity, **kwargs):
        pass

    def partiallyFilled(self, ordkey, book, orderSide, lastQuantity, lastPrice, **kwargs):
        book.fill(key=ordkey, px=lastPrice, qty=lastQuantity, side=orderSide, info=kwargs)

    def filled(self, ordkey, book, orderSide, lastQuantity, lastPrice, **kwargs):
        book.fill(key=ordkey, px=lastPrice, qty=lastQuantity, side=orderSide, info=kwargs)

    def failed(self, ordkey, book, **kwargs):
        if kwargs["type"] != "place":
            # No effect
            return
        book.cancel(key=ordkey, qty=leaves, side=orderSide, info=kwargs)

    # No effect
    def rejected(self, ordkey, book, reason, **kwargs):
        pass

    # No effect
    def cancelRej(self, ordkey, book, **kwargs):
        pass

    # No effect
    def replaceRej(self, ordkey, book, **kwargs):
        pass

    def doneForDay(self, ordkey, book, orderSide, leaves, **kwargs):
        book.cancel(key=ordkey, qty=leaves, side=orderSide, info=kwargs)

    def canceled(self, ordkey, book, orderSide, leaves, **kwargs):
        book.cancel(key=ordkey, qty=leaves, side=orderSide, info=kwargs)

    def expired(self, ordkey, book, orderSide, leaves, **kwargs):
        book.cancel(key=ordkey, qty=leaves, side=orderSide, info=kwargs)

    # No effect
    def pendingNew(self, **kwargs):
        pass

    # No effect
    def pendingCancel(self, **kwargs):
        pass

    # No effect
    def pendingReplace(self, **kwargs):
        pass

    def correction(self, ordkey, book, receiveTime, cumQty, leaves, avgPx, lastQuantity, execRefID, **kwargs):
        pass

    def bust(self, ordkey, book, receiveTime, cumQty, leaves, avgPx, lastQuantity, execRefID, **kwargs):
        pass

    def restated(self, ordkey, book, receiveTime, cumQty, leaves, avgPx, **kwargs):
        pass

    def status(self, ordkey, book, receiveTime, cumQty, leaves, avgPx, **kwargs):
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

class FillModels(dict):
    def __init__(self, mktdata, peer, strg_pfx, oms_name):
        super().__init__()
        self.mktdata = mktdata
        self.peer = peer
        self.strg_pfx = strg_pfx
        self.oms_name = oms_name

    def __missing__(self, key):
        stream = self.peer.stream(self.peer.channel(time_ns(), self.strg_pfx + key.strategy + "/" + self.oms_name))
        obj = self[key] = FillModel(mktdata, StrategyOrderWriter(stream))
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
