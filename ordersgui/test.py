from yamal import ytp
from conveyor.utils import schemas
from collections import defaultdict


venuesSecurities = defaultdict(set)
venuesNames = defaultdict(dict)
securities = defaultdict(dict)
accounts = set()

parser = {
    'venu': schemas.reference.VenueData,
    'symb': schemas.reference.Symbology,
    'risk': schemas.reference.RiskData
}

if __name__ == '__main__':

    seq = ytp.sequence('symb.ytp', readonly=True)

    def seq_clbck(peer, channel, time, data):
        print(peer.name())
        chname = channel.name()
        print(chname)
        if not chname in parser:
            return
        d = parser[chname].from_bytes_packed(data).to_dict()
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

    seq.data_callback('/', seq_clbck)

    count = 100
    while count > 0:
        seq.poll()
        count -= 1

    print('venuesSecurities')
    print(venuesSecurities)
    print('venuesNames')
    print(venuesNames)
    print('securities')
    print(securities)
    print('accounts')
    print(accounts)
