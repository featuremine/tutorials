from yamal import ytp
from conveyor.utils import schemas
from collections import defaultdict, namedtuple

class MarketData(object):
    State = namedtuple('State', ['bid', 'ask'])
    def __init__(self) -> None:
        self.prices = defaultdict(MarketData.State)
    
    def subscribe(self, imnts: dict[tuple[int, int], tuple[str,str]]) -> None:
        if self.prices:
            return
        # call extractor here on another thread

class ReferenceData(object):
    class State(object):
        def __init__(self) -> None:
            self.venuesSecurities = defaultdict(set)
            self.venuesNames = defaultdict(namedtuple('Venue', ['label', 'code', 'exdest']))
            self.securities = defaultdict(namedtuple('Security', ['symbol']))
            self.accounts = set()   

        def update(self, delta):
            for k, v in delta.venuesSecurities.items():
                self.venuesSecurities[k] &= v
            for k, v in delta.venuesNames.items():
                self.venuesNames[k] = v
            for k, v in delta.securities.items():
                self.securities[k] = v
            self.accounts &= delta.accounts

    def __init__(self, yamal: str, cfg: dict) -> None:
        self.state = ReferenceData.State()
        self.delta = ReferenceData.State()

        self.callbacks = []
        self.parser = {
            cfg['venue_channel']: schemas.reference.VenueData,
            cfg['symbology_channel']: schemas.reference.Symbology,
            cfg['risk_channel']: schemas.reference.RiskData
        }

        self.seq = ytp.sequence(yamal, readonly=True)
        self.seq.data_callback('/', self._seq_clbck)

    def add_callback(self, clb):
        self.callbacks.append(clb)

    def _seq_clbck(self, peer, channel, time, data):
        chname = channel.name()
        if not chname in self.parser:
            return
        d = self.parser[chname].from_bytes_packed(data).to_dict()
        print(d)
        if 'venue' in d['message']:
            v = d['message']['venue']
            item = self.delta.venuesNames[v['identifier']]
            item.code = v['code']
            if 'exdest' in v:
                item.exdest = v['exdest']
                item.label = f"{v['code']}/{v['exdest']}"
            else:
                item.exdest = None
                item.label = v['code']
        elif 'venueSecurityAttribute' in d['message']:
            vsa = d['message']['venueSecurityAttribute']
            self.delta.venuesSecurities[vsa['venueID']].add(vsa['securityId'])
        elif 'securityDefinition' in d['message']:
            item = d['message']['securityDefinition']
            self.delta.securities[item['identifier']].symbol = item['symbol']
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

if __name__ == '__main__':

    cfg = {
        'venue_channel': 'venu',
        'symbology_channel': 'symb',
        'risk_channel': 'risk'
    }

    refdata = ReferenceData('symb.ytp', cfg=cfg)
    mrkdata = MarketData()

    def prt(delta):
        print(delta.venuesSecurities)
        print(delta.venuesNames)
        print(delta.securities)
        print(delta.accounts)

    refdata.add_callback(prt)

    def mktSubscribe(delta):
        imnts = {}
        for venid, securities in delta.venueSecurities.items():
            venue = refdata.state.venuesNames[venid]
            market = venue.exdest if venue.exdest else venue.code
            for secid in securities:
                symbol = refdata.state.securities[secid].symbol
                imnts[(venid, secid)] = (market, symbol)
        mktSubscribe(imnts)

    refdata.add_callback(mktSubscribe)

    refdata.poll()
