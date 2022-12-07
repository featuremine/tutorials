from collections import defaultdict, namedtuple
from typing import Dict, Tuple
from yamal import ytp
from conveyor.utils import schemas
from nicegui import ui

class SymbologyBuilder(object):
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def write(self):
        seq = ytp.sequence(self.cfg['ytp'])
        peer = seq.peer(self.cfg['peer'])
        channels = {
            'venue' : peer.channel(0, self.cfg['venue_channel']),
            'symb' : peer.channel(0, self.cfg['symbology_channel']),
            'risk' : peer.channel(0, self.cfg['risk_channel'])
        }
        streams = {
            'venue' : peer.stream(channels['venue']),
            'symb' : peer.stream(channels['symb']),
            'risk' : peer.stream(channels['risk'])
        }

        for acc in self.cfg['accounts']:
            msg = schemas.reference.RiskData.new_message()
            msg.from_dict({'message': {'account': acc }})
            streams['risk'].write(0, msg.to_bytes_packed())

        for venue in cfg['venues']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venue': venue }})
            streams['venue'].write(0, msg.to_bytes_packed())
            
        for security in cfg['securityDefinitions']:
            msg = schemas.reference.Symbology.new_message()
            msg.from_dict({'message': {'securityDefinition': security }})
            streams['symb'].write(0, msg.to_bytes_packed())
            
        for venueSecurity in cfg['venueSecurityAttributes']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venueSecurityAttribute': venueSecurity }})
            streams['venue'].write(0, msg.to_bytes_packed())

class MarketData(object):
    State = namedtuple('State', ['bid', 'ask'])
    def __init__(self) -> None:
        self.prices = defaultdict(MarketData.State)
    
    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        if self.prices:
            return
        # call extractor here on another thread

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
        print(peer.name())
        print(chname)
        print(d)
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

## TEST SymbologyBuilder


## UI
UNAVAILABLE = '-'

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    def update_select_securities(market):
        selectSecurity.options = {}
        for sid in refdata.state.venuesSecurities[market]:
            print(sid)
            selectSecurity.options[sid] = refdata.state.securities[sid].symbol
        selectSecurity.update()

    selectMarket = ui.select({}, on_change=lambda s: update_select_securities(s.value)).style('width:10em;align-items:center;text-align:center;')
    selectSecurity = ui.select({}).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
    ui.label('ask price').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    bidbutton = ui.button(UNAVAILABLE, on_click=lambda: ui.notify('bid price was pressed')).style('width:10em;align-items:center;text-align:center;').props('color=green')
    askbutton = ui.button(UNAVAILABLE, on_click=lambda: ui.notify('ask price was pressed')).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Price', placeholder='0.00', on_change=lambda e: print(e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('buy on ask', on_click=lambda: ui.notify('buy on ask was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    ui.button('buy on bid', on_click=lambda: ui.notify('buy on bid was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Quantity', placeholder='0.00', on_change=lambda e: print(e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('sell on bid', on_click=lambda: ui.notify('sell on bid was pressed')).style('width:9em;align-items:center;text-align:center;')
    ui.button('sell on ask', on_click=lambda: ui.notify('sell on ask was pressed')).style('width:9em;align-items:center;text-align:center;')


## Market Data
cfg = {
    'venue_channel': 'venu',
    'symbology_channel': 'symb',
    'risk_channel': 'risk'
}

refdata = ReferenceData('symb.ytp', cfg=cfg)
mrkdata = MarketData()

def updateUI(delta):
    updateMarket = False
    for vid, v in delta.venuesNames.items():
        selectMarket.options[vid] = v.label
        updateMarket = True
    if updateMarket:
        selectMarket.update()
        
    updateSecurities = False
    if selectMarket.value in delta.venuesSecurities:
        for sid in delta.venuesSecurities[selectMarket.value]:
            selectSecurity.options[sid] = delta.securities[sid].symbol
            updateSecurities = True
    if updateSecurities:
        selectSecurity.update()
        
    print(delta.venuesSecurities)
    print(delta.venuesNames)
    print(delta.securities)
    print(delta.accounts)

refdata.add_callback(updateUI)

def mktSubscribe(delta):
    imnts = {}
    for venid, securities in delta.venuesSecurities.items():
        venue = refdata.state.venuesNames[venid]
        market = venue.exdest if venue.exdest else venue.code
        for secid in securities:
            symbol = refdata.state.securities[secid].symbol
            imnts[(venid, secid)] = (market, symbol)
    mrkdata.subscribe(imnts)

refdata.add_callback(mktSubscribe)

## Update UI
def update_elements():
    refdata.poll()

t = ui.timer(interval=1, callback=update_elements)

## Run
ui.run(title='Featuremine orders', reload=False, show=False)
