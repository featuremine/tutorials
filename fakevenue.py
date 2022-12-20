import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
import time
from typing import Dict, Tuple
from conveyor.utils import schemas
capnp_spec = schemas.session.SessionMessage

def time_ns():
    return int(time.time() * 1000000000)

def sess_placed(sess_id, exec_id, side, price, quantity, transact_time, executing_broker):
    return {
            'message': {
                'data': {
                    'exec': {
                        'sessOrdID': sess_id,
                        'execID': exec_id,
                        'side': side,
                        'data': {
                            'placed': {
                                'brokerID': sess_id,
                                'price': {
                                    'unknown': None
                                } if price is None else {
                                    'price': price
                                },
                                'quantity': {
                                    'quantity': quantity
                                },
                            }
                        },
                        'transactTime': transact_time,
                        'executingBroker': executing_broker,
                    }
                }
            }
        }

class MarketDataFV(MarketData):

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        self.process(imnts)
        # Set up necessary callbacks

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
    publishing_stream = peer.stream(peer.channel(time_ns(), cfg["fv_prefix"][:-1]))

    def response_callback(peer, channel, time, data):
        message = capnp_spec.from_bytes_packed(data)
        if message.message.which() != "data":
            return
        if message.message.data.which() != "new":
            return
        neworder = message.message.data.new

        #Validate order price/type, and time in force and act accordingly

        #Not all venues have exdest, the code is only available in the channel prefix on the order placement side
        #venue_id = refdata.state.revVenuesNames[???]
        security_id = refdata.staate.revSecurities[neworder.symbol]

        mktdata_key = (venue_id, security_id)
        if mktdata_key not in mktdata.prices:
            # reject order, no market data
            pass

        price_ref = graph.get_ref(mktdata.prices[mktdata_key])

        orderpx = neworder.ordType.limit if neworder.ordType.which() == 'limit' else None
        orderqty = neworder.orderQty
        orderside = "buy" if neworder.side.which() == "buy" else "sell"

        execid += 1
        response = capnp_spec.new_message()
        response.from_dict(sess_placed(neworder.sessOrdID, str(execid), orderside, orderpx, neworder.orderQty, time_ns(), "FakeVenueFM"))

        encoded_response = response.to_bytes_packed()
        publishing_stream.write(time_ns(), encoded_response)

        fillpx = price_ref[0].askpx if neworder.side.which() == "buy" else price_ref[0].askpx

        response = capnp_spec.new_message()
        response.from_dict({
            "message" : {
                "data" : {
                    "exec": {
                        "sessOrdID": neworder.sessOrdID,
                        "execID": "garbage",
                        "side": "buy" if neworder.side.which() == "buy" else "sell",
                        "transactTime": 0,
                        "executingBroker": "garbage",
                        "account": "garbage",
                        "symbol": "garbage",
                        "data" : {
                            "filled" : {
                                # Use proper price from market data since the fill can be done on a better price
                                "lastPrice": fillpx,
                                "lastQuantity": neworder.orderQty,
                                "cumQty": neworder.orderQty,
                                "leaves": 0,
                                "avgPx": fillpx,
                                "lastFees": 0,
                                "lastLiquidity": 0
                            }
                        }
                    }
                }
            }
        })
        encoded_response = response.to_bytes_packed()
        publishing_stream.write(time_ns(), encoded_response)

    # Remove last character to keep configs compliant with oms config which expects "/" at the end
    seq.data_callback(cfg["fv_prefix"][:-1], response_callback)

    # Run context for graph
    graph.stream_ctx().run_live()
