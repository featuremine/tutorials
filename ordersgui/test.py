from yamal import ytp
from conveyor.utils import schemas
from collections import defaultdict

venues = []
venueSecurityAttribute = []
securityDefinition = []

venuesSecurities = defaultdict(list)
#{} # { 1001 : [1001, ...], ...}
venuesNames = {}
# 'code': 'SOCGEN', 'exdest': 'NYSE'

prices = {} # { (1001,1001) : '-', ...}



if __name__ == '__main__':

    seq = ytp.sequence('symb.ytp', readonly=True)

    def seq_clbck(peer, channel, time, data):
        print(peer.name())
        print(channel.name())
        if channel.name() == 'venu':
            d = schemas.reference.VenueData.from_bytes_packed(data).to_dict()
        elif channel.name() == 'symb':
            d = schemas.reference.Symbology.from_bytes_packed(data).to_dict()
        else:
            return
        print(d)
        if 'venue' in d['message']:
            print('VENUE')
            v = d['message']['venue']
            venues.append(v)
            venuesNames[v['identifier']] = {'code' : v['code']}
            venuesSecurities[v['identifier']] = []
        elif 'venueSecurityAttribute' in d['message']:
            print('venueSecurityAttribute')
            vsa = d['message']['venueSecurityAttribute']
            venueSecurityAttribute.append(vsa)
            venuesSecurities[vsa['venueID']].append(vsa['securityId'])
            prices[(vsa['venueID'], vsa['securityId'])] = '-'
        elif 'securityDefinition' in d['message']:
            print('securityDefinition')
            securityDefinition.append(d['message']['securityDefinition'])

    seq.data_callback('/', seq_clbck)

    count = 100
    while count > 0:
        seq.poll()
        count -= 1

    print(venues)
    print(venueSecurityAttribute)
    print(securityDefinition)
    print(venuesSecurities)
    print(prices)
