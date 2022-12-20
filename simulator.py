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


class MarketDataFV(MarketData):

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

class Order(NamedTuple):
    identifier: int
    price: float
    origqty: float
    outstandingqty: float

class Orders:
    def __init__(self):
        self.bids = defaultdict(deque())
        self.asks = defaultdict(deque())

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

    mktdata = MarketDataFV(orders, peer, graph)

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

            if ordertif == 'ioc':

                #Should we ack IOC orders?

                fillpx = price_ref[0].askpx if orderside == "buy" else price_ref[0].bidpx

                execid += 1
                send_message(strg_filled, channel, orderid, accid, securityid, venueid, orderside, str(execid), fillpx, orderqty, time_ns(), "FakeVenueFM")

            elif ordertif == 'day':

                orderpx = neworder.ordType.limit if neworder.ordType.which() == "limit" else None

                if orderpx is None:
                    send_message(strg_fail, channel, orderid, "place", "invalid time in force for marketable order, please use ioc", time)
                    return

                execid += 1
                send_message(strg_placed, channel, orderid, accid, securityid, venueid, orderside, str(execid), orderpx, orderqty, time_ns(), "FakeVenueFM")
                
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
