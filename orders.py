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

class StrategyOrderWriter:
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
        self.send_message(self.strg_placed, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

    def failed(self, info, reason):
        #TODO: report back actual request time from YTP instead of current time?
        self.send_message(self.strg_fail, info['strgOrdID'], "place", reason, time_ns())

    def canceled(self, side, info, leaves):
        self.execid += 1
        self.send_message(self.strg_canceled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), time_ns(), "SimulatorFM")

    def filled(self, px, qty, side, info):
        self.execid += 1
        self.send_message(self.strg_filled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

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
        book.cancel(key=ordkey, qty=lastQuantity, side=orderSide, info=kwargs)

    def filled(self, ordkey, book, orderSide, lastQuantity, lastPrice, **kwargs):
        book.cancel(key=ordkey, qty=lastQuantity, side=orderSide, info=kwargs)

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

