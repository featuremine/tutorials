import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
import time as pytime
from typing import Dict, Tuple, NamedTuple, Optional
from datetime import timedelta
from collections import deque, defaultdict
import functools
from bisect import insort, bisect_left
from logging import getLogger
from datetime import timedelta
from conveyor.utils import schemas
capnp_spec = schemas.strategy.ManagerMessage

def time_ns():
    return int(pytime.time() * 1000000000)

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


def QueuedOrderComp(first, second):
    if first.side == "buy":
        if first.price < second.price:
            return 1
        elif first.price > second.price:
            return -1
    else:
        if first.price > second.price:
            return 1
        elif first.price < second.price:
            return -1
    if first.time > second.time:
        return 1
    if first.time < second.time:
        return -1
    return 0


class QueuedOrder(object):
    def __init__(self, now, identifier: int, px: float, qty: float, side, security, venue, account, responder):
        self.time = now
        self.identifier = identifier
        self.px = px
        self.qty = qty
        self.leaves = qty
        self.side = side
        self.securityid = security
        self.venueid = venue
        self.account = account
        self.responder = responder

    def __gt__(self, other):
        return QueuedOrderComp(self, other) == 1

    def __lt__(self, other):
        return QueuedOrderComp(self, other) == -1

    def send_message(msg_builder, *args, **kwargs):
        response = capnp_spec.new_message()
        msg_dict = msg_builder(*args, **kwargs)
        response.from_dict(msg_dict)
        encoded_response = response.to_bytes_packed()
        self.responder.write(time_ns(), encoded_response)

    def placed(self, execution_id) -> None:
        send_message(strg_placed, self.identifier, self.accid, self.securityid, self.venueid, self.side, str(execution_id), self.px, self.qty, time_ns(), "SimulatorFM")

    def filled(self, px, qty, execution_id) -> None:
        send_message(strg_filled, self.identifier, self.accid, self.securityid, self.venueid, self.side, str(execution_id), px, qty, time_ns(), "SimulatorFM")

    def canceled(self, execution_id) -> None:
        send_message(strg_canceled, self.identifier, self.accid, self.securityid, self.venueid, self.side, str(execution_id), time_ns(), "SimulatorFM")

    def failed(self, reason) -> None:
        send_message(strg_fail, self.identifier, "place", reason, self.time)

class LimitFillModel(object):
    def __init__(self): #probably should use venue as an argument
        self.bids_q = {}
        self.asks_q = {}

    def trade(self, venue_symbol, mkt, frame):
        symbol = venue_symbol["symbol"]
        px = frame[0].price
        qty = frame[0].qty
        side = frame[0].side

        def fill(symbol, price, quantity, side, ords, worse):
            while ords:
                o = ords[0]

                if quantity == 0 or worse(o.price, price):
                    break

                filled = min(quantity, o.leaves)
                o.leaves = o.leaves - filled
                quantity = quantity - filled
                if o.leaves == 0:
                    self.log.info("Order filled completely %s" % o)
                    ords.pop(0)
                o.filled(price, filled, 1)

        if side != 1:
            if symbol in self.bids_q:
                fill(symbol, px, qty, side, self.bids_q[symbol], lambda x, y: x < y)
        if side != 2:
            if symbol in self.asks_q:
                fill(symbol, px, qty, side, self.asks_q[symbol], lambda x, y: x > y)

    def place(self, order):
        order.placed()

        if order.side == "buy":
            if order.symbol not in self.bids_q:
                self.bids_q[order.symbol] = []
            insort(self.bids_q[order.symbol], QueuedOrder(self.platform.clock.now(), order=order))
        else:
            if order.symbol not in self.asks_q:
                self.asks_q[order.symbol] = []
            insort(self.asks_q[order.symbol], QueuedOrder(self.platform.clock.now(), order=order))

    def cancel(self, order):
        def q_cancel():
            self.log.info("received cancelation on %s for order %s with with id %i" % (self.name, order, order.id))
            if not order.alive():
                order.cancel_rej()
                return
            # test cancel_failed
            if order.id == 1013:
                if self.cancel_failed_count == 0:
                    self.cancel_failed_count += 1
                    self.log.info("order cancel_failed for order {}".format(order))
                    order.cancel_failed()
                else:
                    self.log.info("order {} canceled".format(order))
                    order.canceled()
            else:
                self.log.info("order {} canceled".format(order))
                order.canceled()

            symbol = order.symbol
            if order.side == "buy":
                if symbol not in self.bids_q:
                    return
                idx = bisect_left(
                    self.bids_q[symbol],
                    QueuedOrder(
                        timedelta(
                            seconds=0),
                        price=order.price,
                        qty=0,
                        side="buy",
                        id=0))
                ords = self.bids_q[symbol]
            else:
                if symbol not in self.asks_q:
                    return
                idx = bisect_left(
                    self.asks_q[symbol],
                    QueuedOrder(
                        timedelta(
                            seconds=0),
                        price=order.price,
                        qty=0,
                        side="SELL/SELLSHORT",
                        id=0))
                ords = self.asks_q[symbol]

            for x in range(idx, len(ords)):
                o = ords[x]
                if (order.id == o.id):
                    ords.pop(x)
                    return

            assert("This should never happen")

        self.platform.timer.schedule_once(self.platform.clock.now() + timedelta(milliseconds=50), q_cancel)
        return True

class MarketDataSim(MarketData):

    def __init__(self, orders, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        super().__init__(peer, graph, prefix, period)
        self.orders = orders

    def prices_update(self, ids, frame):
        # Fill orders if the price crosses
        pass

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        self.process(imnts)

        for ids, quote in self.quotes.items():
            self.graph.callback(quote, functools.partial(self.prices_update, ids=ids))

class Orders:
    def __init__(self):
        self.bids = defaultdict(deque())
        self.asks = defaultdict(deque())

def better_price(side, px, other):
    if side == 'buy':
        return px < other
    return other < px

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    cfg = json.load(open(args.cfg))
    seq = ytp.sequence(cfg["state_ytp"])
    peer = seq.peer(cfg["peer"])

    #Would deploy.py be invoked before running the fake venue?
    refbuilder = ReferenceBuilder(peer, cfg)
    refbuilder.write()

    state_seq = ytp.sequence(cfg["state_ytp"], readonly=True)

    refdata = ReferenceData(state_seq, cfg)

    graph = extractor.system.comp_graph()

    orders = defaultdict(Orders)

    mktdata = MarketDataSim(orders, peer, graph)

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

    refdata.poll()

    # Set up callbacks for market data updates

    execid = 1

    def send_message(msg_builder, channel, *args, **kwargs):
        requestch = channel.name()
        responsesplit = requestch.split("/")
        responsech = requestsplit[-3].join("/") + "/" + requestsplit[-1] + "/" + requestsplit[-2]

        publishing_stream = peer.stream(peer.channel(time_ns(), responsech))
        response = capnp_spec.new_message()
        msg_dict = msg_builder(*args, **kwargs)
        response.from_dict(msg_dict)
        encoded_response = response.to_bytes_packed()
        publishing_stream.write(time_ns(), encoded_response)

    def response_callback(peer, channel, time, data):
        message = capnp_spec.from_bytes_packed(data)

        if message.message.which() != "strg":
            return

        if message.message.strg.which() == "new":
            neworder = message.message.strg.new

            venueid = neworder.venueID
            securityid = neworder.securityId

            orderid = neworder.strgOrdID

            mktdata_key = (venueid, securityid)

            ords = orders[mktdata_key]

            if ords.count(orderid) > 0:
                send_message(strg_fail, channel, orderid, "place", "duplicated order identifier", time)
                return

            if mktdata_key not in mktdata.prices:
                send_message(strg_fail, channel, orderid, "place", "price not available for security in provided venue", time)
                return

            ordertif = neworder.timeInForce.which()
            orderqty = neworder.orderQty
            orderside = "buy" if neworder.side.which() == "buy" else "sell"

            price_ref = graph.get_ref(mktdata.prices[mktdata_key])

            orderpx = neworder.ordType.limit if neworder.ordType.which() == "limit" else None

            if ordertif == 'ioc':

                #Should we ack IOC orders?

                fillpx = price_ref[0].askpx if orderside == "buy" else price_ref[0].bidpx

                if orderpx is None or not better_price(orderside, orderpx, fillpx):
                    execid += 1
                    send_message(strg_filled, channel, orderid, accid, securityid, venueid, orderside, str(execid), fillpx, orderqty, time_ns(), "SimulatorFM")
                else:
                    execid += 1
                    send_message(strg_canceled, channel, orderid, accid, securityid, venueid, orderside, str(execid), time_ns(), "SimulatorFM")

            elif ordertif == 'day':

                if orderpx is None:
                    send_message(strg_fail, channel, orderid, "place", "invalid time in force for marketable order, please use ioc", time)
                    return

                execid += 1
                send_message(strg_placed, channel, orderid, accid, securityid, venueid, orderside, str(execid), orderpx, orderqty, time_ns(), "SimulatorFM")
                
                getattr(ords[orderpx], orderside).append(Order(identifier=orderid, price=orderpx, origqty=orderqty, outstandingqty=orderqty, side=orderside))

        elif message.message.strg.which() == "cancel":
            # handle order cancel
            pass

        else:
            # handle order replace
            pass

    # Remove last character to keep configs compliant with oms config which expects "/" at the end
    seq.data_callback(cfg["strategy_prefix"], response_callback)

    # Run context for graph
    graph.stream_ctx().run_live()
