from yamal import ytp
from conveyor.utils import schemas
from collections import defaultdict


class ReferenceData(object):
    def __init__(self, yamal: str, cfg: dict) -> None:
        self.venuesSecurities = defaultdict(set)
        self.venuesNames = defaultdict(dict)
        self.securities = defaultdict(dict)
        self.accounts = set()
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
        venuesSecurities = defaultdict(set)
        venuesNames = defaultdict(dict)
        securities = defaultdict(dict)
        accounts = set()
        chname = channel.name()
        if not chname in self.parser:
            return
        d = self.parser[chname].from_bytes_packed(data).to_dict()
        print(d)
        if 'venue' in d['message']:
            v = d['message']['venue']
            item = venuesNames[v['identifier']]
            item['code'] = v['code']
            if 'exdest' in v:
                item['exdest'] = v['exdest']
                item['label'] = f"{v['code']}/{v['exdest']}"
            else:
                item['label'] = v['code']
        elif 'venueSecurityAttribute' in d['message']:
            vsa = d['message']['venueSecurityAttribute']
            venuesSecurities[vsa['venueID']].add(vsa['securityId'])
        elif 'securityDefinition' in d['message']:
            item = d['message']['securityDefinition']
            securities[item['identifier']] = {
                'symbol': item['symbol']
            }
        elif 'account' in d['message']:
            accounts.add(d['message']['account']['identifier'])
        for c in self.callbacks:
            c(venuesSecurities, venuesNames, securities, accounts)
        for k, v in venuesSecurities.items():
            self.venuesSecurities[k] &= v
        for k, v in  venuesNames.items():
            self.venuesNames[k] = v
        for k, v in  securities.items():
            self.securities[k] = v
        self.accounts &= accounts

    def poll(self, limit=None):
        count = 0
        while self.seq.poll() and (not limit or count <= limit):
            count += 1


if __name__ == '__main__':
    def prt(venuesSecurities, venuesNames, securities, accounts):
        print(venuesSecurities)
        print(venuesNames)
        print(securities)
        print(accounts)

    cfg = {
        'venue_channel': 'venu',
        'symbology_channel': 'symb',
        'risk_channel': 'risk'
    }

    refdata = ReferenceData('symb.ytp', cfg=cfg)
    refdata.add_callback(prt)
    refdata.poll()
