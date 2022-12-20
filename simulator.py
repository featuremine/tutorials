import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
import time as pytime
from typing import Dict, Tuple, NamedTuple
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

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        self.process(imnts)
        # Set up necessary callbacks

class Order(NamedTuple):
    price: float
    origqty: float
    outstandingqty: float

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
    # Use appropriate derived class instead of MarketData directly
    mktdata = MarketDataFV(peer, graph)

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

    # Create stream for responses on control channel
    publishing_stream = peer.stream(peer.channel(time_ns(), cfg["strategy_prefix"][:-1]))

    def send_message(msg_builder, *args, **kwargs):
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

            if orderid in orders:
                send_message(strg_fail, orderid, "place", "duplicated order identifier", time)
                return

            mktdata_key = (venueid, securityid)
            if mktdata_key not in mktdata.prices:
                send_message(strg_fail, orderid, "place", "price not available for security in provided venue", time)
                return

            ordertif = neworder.timeInForce.which()
            orderqty = neworder.orderQty
            orderside = "buy" if neworder.side.which() == "buy" else "sell"

            price_ref = graph.get_ref(mktdata.prices[mktdata_key])

            if ordertif == 'ioc':

                #Should we ack IOC orders?

                fillpx = price_ref[0].askpx if orderside == "buy" else price_ref[0].bidpx

                execid += 1
                send_message(strg_filled, orderid, accid, securityid, venueid, orderside, str(execid), fillpx, orderqty, time_ns(), "FakeVenueFM")

            elif ordertif == 'day':

                orderpx = neworder.ordType.limit if neworder.ordType.which() == "limit" else None

                if orderpx is None:
                    send_message(strg_fail, orderid, "place", "invalid time in force for marketable order, please use ioc", time)
                    return

                execid += 1
                send_message(strg_placed, orderid, accid, securityid, venueid, orderside, str(execid), orderpx, orderqty, time_ns(), "FakeVenueFM")
                
                orders[orderid] = Order(price=orderpx, origqty=orderqty, outstandingqty=orderqty)

        elif message.message.strg.which() == "cancel":
            # handle order cancel
            pass

        else:
            # handle order replace
            pass

    # Remove last character to keep configs compliant with oms config which expects "/" at the end
    seq.data_callback(cfg["strategy_prefix"][:-1], response_callback)

    # Run context for graph
    graph.stream_ctx().run_live()
