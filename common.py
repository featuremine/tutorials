from typing import List, NamedTuple, Any
from enum import Enum
from collections import defaultdict
from bisect import insort, bisect_left
from weakref import WeakValueDictionary

from conveyor.utils import schemas

capnp_spec = schemas.strategy.ManagerMessage

class Side(Enum):
    BID = 0
    ASK = 1

class SystemTime(object):
    def __call__(self) -> Any:
        raise NotImplementedError('not implemented')

class AbstractOrderContainer(object):
    def place(self, key, imnt: int, venue: int, account: int, strg: str, px: float, qty: int, side: Side, info: Any):
        raise NotImplementedError('not implemented')

    def cancel(self, key, leaves):
        raise NotImplementedError('not implemented')

    def replace(self, key, px, qty):
        raise NotImplementedError('not implemented')

    def placed(self, key):
        raise NotImplementedError('not implemented')

    def filled(self, key, trdpx, qty):
        raise NotImplementedError('not implemented')

    def canceled(self, key, leaves):
        raise NotImplementedError('not implemented')

    def replaced(self, key, px, qty):
        raise NotImplementedError('not implemented')

    def rejected(self, key, reason):
        raise NotImplementedError('not implemented')

    def __getitem__(self, key):
        raise NotImplementedError('not implemented')

    def __contains__(self, key):
        raise NotImplementedError('not implemented')

    def bid(self):
        return self.side(0)

    def ask(self):
        return self.side(1)

    def side(self, i: Side):
        raise NotImplementedError('not implemented')

class OrderStateTable(AbstractOrderContainer):
    class Request(NamedTuple):
        pass

    class Place(Request):
        px: float
        qty: int

    class Replace(Request):
        px: float
        qty: int

    class Cancel(Request):
        leaves: int

    class Order(NamedTuple):
        imnt: int
        venue: int
        account: int
        strg: str
        px: float
        qty: int
        left: int
        filled: int
        canceled: int
        side: Side
        info: Any
        rejected: bool
        requests: List[Any] #TODO: List[OrderStateTable.Request]

    def __init__(self):
        self.orders = defaultdict(OrderStateTable.Order)
        self.sided = (WeakValueDictionary, WeakValueDictionary)
    
    def place(self, key, imnt: int, venue: int, account: int, strg: str, px: float, qty: int, side: Side, info: Any):
        order = OrderStateTable.Order(imnt=imnt, venue=venue, account=account, strg=strg,
                                      px=px, qty=qty, left=qty, side=side, info=info,
                                      status=OrderStateTable.Status.UNACKED)
        order.requests.append(OrderStateTable.Place(px=px, qty=qty))
        self.orders[key] = order
        self.sided[side][key] = order

    def cancel(self, key, leaves):
        order = self.orders[key]
        order.requests.append(OrderStateTable.Cancel(leaves=leaves))

    def replace(self, key, px, qty):
        order = self.orders[key]
        order.requests.append(OrderStateTable.Replace(px=px, qty=qty))

    def placed(self, key):
        order = self.orders[key]
        assert order.requests and order.requests[0] is OrderStateTable.Place, "was not expecting place"
        del order.requests[0]

    def filled(self, key, trdpx, qty):
        order = self.orders[key]
        order.left -= qty
        order.filled += qty

    def canceled(self, key, leaves):
        order = self.orders[key]
        assert order.requests and order.requests[0] is OrderStateTable.Cancel, "was not expecting place"
        del order.requests[0]
        oldleft = order.left
        order.left = leaves
        order.canceled += oldleft - leaves

    # TODO might get replace px and qty on the message. Need to check they match our request
    def replaced(self, key, px, qty):
        order = self.orders[key]
        assert order.requests and order.requests[0] is OrderStateTable.Replace, "was not expecting place"
        req = order.requests.pop(0)
        order.px = req.px
        order.qty = req.qty

    def rejected(self, key, reason):
        order = self.orders[key]
        assert order.requests, "was not expecting reject"
        req = order.requests.pop(0)
        if req is OrderStateTable.Place:
            order.failed = True

    def __getitem__(self, key):
        return self.orders[key]

    def __contains__(self, key):
        return key in self.orders

    def side(self, i):
        return self.sided[i]
   

class SidedPriceFIFOPriorityOrderBook(AbstractOrderContainer):
    def Comp(first, second):
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


    class Order(object):
        def __init__(self, px: float, qty: float, side, info):
            self.px = px
            self.qty = qty
            self.leaves = qty
            self.side = side
            self.info = info

        def __gt__(self, other):
            return SidedPriceFIFOPriorityOrderBook.Comp(self, other) == 1

        def __lt__(self, other):
            return SidedPriceFIFOPriorityOrderBook.Comp(self, other) == -1

    def __init__(self):
        self._order_dict = dict()
        # each order heap is an array sorted by price time priority
        self._order_heap = ([], [])
        self.pxcmp = (lambda x, y: x < y, lambda x, y: x > y)

    def add(self, key, px, qty, side, info):
        order = SidedPriceFIFOPriorityOrderBook.Order(px, qty, side, info)
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

class CapnpMessageWriter:
    def __init__(self, category, kind):
        self.category = category
        self.kind = kind

    def __call__ (self, **rest):
        return {
            "message": {
                self.category: {
                    self.kind: rest
                }
            }
        }

class ManagerMessageWriter:
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

    _place = CapnpMessageWriter('strg', 'new')

    def __init__(self, systime, stream, ctx):
        self.systime = systime
        self.stream = stream
        self.ctx = ctx

    def send(self, builder, **rest):
        msg = capnp_spec.new_message()
        msg_dict = builder(**rest)
        msg.from_dict(msg_dict)
        encoded_response = msg.to_bytes_packed()
        self.stream.write(self.systime(), encoded_response)

    def place(self, strgOrdID, orderSide, px, quantity, maxFloor, minQty, timeInForce, algorithm, tag, **rest):
        self.send(ManagerMessageWriter._place,
                  strgOrdID=strgOrdID,
                  orderSide=orderSide,
                  orderType={'market': None} if px is None else {'limit': px},
                  quantity=quantity,
                  maxFloor={'none': None} if maxFloor is None else {'maxFloor': maxFloor},
                  minQty={'none': None} if minQty is None else {'maxQty': minQty},
                  timeInForce=timeInForce,
                  algorithm={'dma': None} if algorithm is None else {'custom': algorithm},
                  tag=tag,
                  **rest,
                  **self.ctx)

    def placed(self, px, qty, side, info):
        CapnpMessageWriter.send_message(self.strg_placed, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

    def failed(self, info, reason):
        #TODO: report back actual request time from YTP instead of current time?
        CapnpMessageWriter.send_message(self.strg_fail, info['strgOrdID'], "place", reason, time_ns())

    def canceled(self, side, info, leaves):
        CapnpMessageWriter.send_message(self.strg_canceled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), time_ns(), "SimulatorFM")

    def filled(self, px, qty, side, info):
        CapnpMessageWriter.send_message(self.strg_filled, info['strgOrdID'], info['accountID'], info['securityId'], info['venueID'], side, str(self.execid), px, qty, time_ns(), "SimulatorFM")

class StrategyOrderUpdater:
    def __init__(self, book: AbstractOrderContainer):
        self.book = book

    def __call__(self, upd: dict):
        msg = upd["msg"]
        msgdata = getattr(msg.message, msg.message.which())
        specdata = getattr(msgdata, msgdata.which())
        if not hasattr(specdata, 'strgOrdID'):
            return
        key = (upd["strg"], specdata.strgOrdID)
        getattr(self, msgdata.which())(key, **specdata.to_dict())
    
    def new(self, key, accountID, securityId, venueID, orderType, quantity, orderSide, **kwargs):
        px = None if 'market' in orderType else orderType['limit']
        side = Side.BID if orderSide == 'buy' else Side.ASK
        self.book.place(key=key, imnt=securityId, venue=venueID, account=accountID,
                        strg=key[0], px=px, qty=quantity, side=side, info=kwargs)

    def cancel(self, key, **kwargs):
        self.book.cancel(key=key, leaves=0)

    def replace(self, key, price, quantity, **kwargs):
        px = price['price'] if 'price' in price else None
        qt = quantity['quantity'] if 'quantity' in quantity else None
        self.book.replace(key=key, px=price, qty=qt)

    def exec(self, key, data, **execargs):
        for exectype, execdata in data.items():
            if execdata is None:
                getattr(self, exectype)(key, **execargs)
            else:
                getattr(self, exectype)(key, **execargs, **execdata)

    def placed(self, key, **kwargs):
        self.book.placed(key=key)

    def replaced(self, key, **kwargs):
        self.book.replaced(key=key)

    def partiallyFilled(self, key, lastPrice, lastQuantity, leaves, **kwargs):
        self.book.filled(key=key, trdpx=lastPrice, qty=lastQuantity)

    def filled(self, key, lastPrice, lastQuantity, leaves, **kwargs):
        self.book.filled(key=key, trdpx=lastPrice, qty=lastQuantity)

    def failed(self, key, book, **kwargs):
        #TODO: what to do on failed? Should add new method on rejected? 
        if kwargs["type"] != "place":
            # No effect
            return
        self.book.canceled(key=key, leaves=0)

    def rejected(self, key, reason, **kwargs):
        self.book.rejected(key=key, reason=reason)

    # No effect
    def cancelRej(self, key, reason, **kwargs):
        self.book.rejected(key=key, reason=reason)

    # No effect
    def replaceRej(self, key, reason, **kwargs):
        self.book.rejected(key=key, reason=reason)

    def doneForDay(self, key, leaves, **kwargs):
        self.book.cancel(key=key, leaves=leaves)

    def canceled(self, key, leaves, **kwargs):
        self.book.canceled(key=key, leaves=leaves)

    def expired(self, key, leaves, **kwargs):
        self.book.canceled(key=key, leaves=0)

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

