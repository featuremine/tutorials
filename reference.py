from collections import defaultdict, namedtuple
from typing import Dict, Tuple, NamedTuple, Optional
from yamal import ytp
import extractor
from conveyor.utils import schemas
import time
from math import inf
from datetime import timedelta
import functools

def time_ns():
    return int(time.time() * 1000000000)
   
class ReferenceBuilder(object):
    def __init__(self, peer, cfg) -> None:
        self.cfg = cfg
        self.peer = peer

    def write(self):
        tm = time_ns()
        streams = {
            'venue' : self.peer.stream(self.peer.channel(tm, self.cfg['venue_channel'])),
            'symb' : self.peer.stream(self.peer.channel(tm, self.cfg['symbology_channel'])),
            'risk' : self.peer.stream(self.peer.channel(tm, self.cfg['risk_channel']))
        }

        for acc in self.cfg['accounts']:
            msg = schemas.reference.RiskData.new_message()
            msg.from_dict({'message': {'account': acc }})
            streams['risk'].write(tm, msg.to_bytes_packed())

        for venue in self.cfg['venues']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venue': venue }})
            streams['venue'].write(tm, msg.to_bytes_packed())
            
        for venueacc in self.cfg['venueAccountMappings']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venueAccountMapping': venueacc }})
            streams['venue'].write(tm, msg.to_bytes_packed())
            
        for security in self.cfg['securityDefinitions']:
            msg = schemas.reference.Symbology.new_message()
            msg.from_dict({'message': {'securityDefinition': security }})
            streams['symb'].write(tm, msg.to_bytes_packed())
            
        for venueSecurity in self.cfg['venueSecurityAttributes']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venueSecurityAttribute': venueSecurity }})
            streams['venue'].write(tm, msg.to_bytes_packed())

class ReferenceData(object):
    Venue = namedtuple('Venue', ['label', 'code', 'exdest'])
    Security = namedtuple('Security', ['symbol'])
    
    class State(object):
        def __init__(self) -> None:
            self.venuesSecurities = defaultdict(set)
            self.venuesNames = defaultdict(ReferenceData.Venue)
            self.securities = defaultdict(ReferenceData.Security)
            self.accounts = set()   

        def update(self, delta):
            for k, v in delta.venuesSecurities.items():
                self.venuesSecurities[k].update(v)
            for k, v in delta.venuesNames.items():
                self.venuesNames[k] = v
            for k, v in delta.securities.items():
                self.securities[k] = v
            self.accounts.update(delta.accounts)

    def __init__(self, cfg: dict) -> None:
        self.state = ReferenceData.State()
        self.delta = ReferenceData.State()

        self.callbacks = []
        self.parser = {
            cfg['venue_channel']: schemas.reference.VenueData,
            cfg['symbology_channel']: schemas.reference.Symbology,
            cfg['risk_channel']: schemas.reference.RiskData
        }

        self.seq = ytp.sequence(cfg['state_ytp'], readonly=True)
        self.seq.data_callback('/', self._seq_clbck)

    def add_callback(self, clb):
        self.callbacks.append(clb)

    def _seq_clbck(self, peer, channel, time, data):
        chname = channel.name()
        if not chname in self.parser:
            return
        d = self.parser[chname].from_bytes_packed(data).to_dict()
        if 'venue' in d['message']:
            v = d['message']['venue']
            if 'exdest' in v:
                self.delta.venuesNames[v['identifier']] = ReferenceData.Venue(f"{v['code']}/{v['exdest']}", v['code'], v['exdest'])
            else:
                self.delta.venuesNames[v['identifier']] = ReferenceData.Venue(v['code'], v['code'], None)
        elif 'venueSecurityAttribute' in d['message']:
            vsa = d['message']['venueSecurityAttribute']
            self.delta.venuesSecurities[vsa['venueID']].add(vsa['securityId'])
        elif 'securityDefinition' in d['message']:
            sd = d['message']['securityDefinition']
            self.delta.securities[sd['identifier']] = ReferenceData.Security(sd['symbol'])
        elif 'account' in d['message']:
            self.delta.accounts.add(d['message']['account']['identifier'])

    def poll(self, limit=None):
        self.delta = ReferenceData.State()
        count = 0
        while self.seq.poll() and (not limit or count <= limit):
            count += 1

        self.state.update(self.delta)

        for c in self.callbacks:
            c(self.delta)

class MarketData(object):
    class State(NamedTuple):
        bidpx: extractor.Decimal128
        bidqt: extractor.Decimal128
        askpx: extractor.Decimal128
        askqt: extractor.Decimal128

        # def __init__(self):
        #     super()
        #     self.bidpx = extractor.Decimal128(-inf)
        #     self.askpx = extractor.Decimal128(inf)
        #     self.bidqt = extractor.Decimal128(0)
        #     self.askqt = extractor.Decimal128(0)

    def __init__(self, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        self.peer = peer
        self.graph = graph
        self.prefix = prefix
        self.period = period
        self.prices = {}
        
    def process(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        op = self.graph.features

        if self.period:
            close = op.timer(timedelta(milliseconds=self.period))

        for ids, syms in imnts.items():

            if ids in self.prices:
                continue

            channel = self.peer.channel(time_ns(), f"{self.prefix}{syms[0]}/{syms[1]}")
            upd = op.decode_data(op.ore_ytp_decode(channel))
            level = op.combine(op.book_build(upd, 1),
                            (("bid_prx_0", "bidprice"),
                            ("bid_shr_0", "bidqty"),
                            ("ask_prx_0", "askprice"),
                            ("ask_shr_0", "askqty")))
            if self.period:
                quote = op.asof(level, close)
            else:
                quote = level

            self.prices[ids] = quote
    
    def subscribe(self, imnts: Dict[Tuple[int,int], Tuple[str,str]]) -> None:
        raise NotImplementedError("function is not implemented")
