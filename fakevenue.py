import argparse
from reference import ReferenceBuilder, ReferenceData, MarketData
from yamal import ytp
import json
import extractor
from typing import Dict, Tuple

class MarketDataFV(MarketData):

    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        self.process(imnts)
        # Set up necessary callbacks

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    cfg = json.load(open(args.cfg))
    seq = ytp.sequence(cfg['state_ytp'])
    peer = seq.peer(cfg['peer'])

    #Would deploy.py be invoked before running the fake venue?
    refbuilder = ReferenceBuilder(peer, cfg)
    refbuilder.write()

    state_seq = ytp.sequence(cfg['state_ytp'], readonly=True)

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

    def response_callback():
        #TODO:IMPLEMENT
        pass

    seq.data_callback(cfg['fv_prefix'], response_callback)

    graph.stream_ctx().run_live()
