from collections import defaultdict, namedtuple
from typing import Dict, Tuple
from yamal import ytp
import extractor
from conveyor.utils import schemas
from nicegui import ui
import argparse
import json, time
from datetime import timedelta
import multiprocessing
import functools
import os

def time_ns():
    return int(time.time() * 1000000000)
    
class SymbologyBuilder(object):
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def write(self):
        seq = ytp.sequence(self.cfg['yamal_file'])
        peer = seq.peer(self.cfg['peer'])
        tm = time_ns()
        streams = {
            'venue' : peer.stream(peer.channel(tm, self.cfg['venue_channel'])),
            'symb' : peer.stream(peer.channel(tm, self.cfg['symbology_channel'])),
            'risk' : peer.stream(peer.channel(tm, self.cfg['risk_channel']))
        }

        for acc in self.cfg['accounts']:
            msg = schemas.reference.RiskData.new_message()
            msg.from_dict({'message': {'account': acc }})
            streams['risk'].write(tm, msg.to_bytes_packed())

        for venue in cfg['venues']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venue': venue }})
            streams['venue'].write(tm, msg.to_bytes_packed())
            
        for security in cfg['securityDefinitions']:
            msg = schemas.reference.Symbology.new_message()
            msg.from_dict({'message': {'securityDefinition': security }})
            streams['symb'].write(tm, msg.to_bytes_packed())
            
        for venueSecurity in cfg['venueSecurityAttributes']:
            msg = schemas.reference.VenueData.new_message()
            msg.from_dict({'message': {'venueSecurityAttribute': venueSecurity }})
            streams['venue'].write(tm, msg.to_bytes_packed())

class MarketData(object):
    def __init__(self, cfg: dict) -> None:
        self.prices = multiprocessing.Manager().dict()
        self.cfg = cfg
        
    def process(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        for imnt in imnts:
            self.prices[imnt] = { 'bid' : '-', 'ask' : '-'}
        graph = extractor.system.comp_graph()
        op = graph.features

        def prices_update(x, market, imnt):
            if x[0].bidprice != extractor.Decimal128(0) and x[0].askprice != extractor.Decimal128(0):
                self.prices[(market,imnt)] =  { 'bid' : str(x[0].bidprice), 'ask' : str(x[0].askprice)}

        # Parse markets and instruments
        channels = []
        for mkt, imnt in imnts.values():
            channels += [f"ore/imnts/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
        
        mktimnt = []
        for mktid, imntid in imnts:
            mktimnt += [(mktid,imntid)] # market/instrument pair

        seq = ytp.sequence(self.cfg['yamal_file_market_data'])
        op.ytp_sequence(seq, timedelta(milliseconds=1))
        peer = seq.peer(self.cfg['peer_market_data'])
        upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]

        levels = [op.book_build(upd, 1) for upd in upds]

        close = op.timer(timedelta(milliseconds=10))
        
        quotes = [op.asof(op.combine(level,
                        (("bid_prx_0", "bidprice"),
                        ("bid_shr_0", "bidqty"),
                        ("ask_prx_0", "askprice"),
                        ("ask_shr_0", "askqty"))), close)
                for level in levels]

        # Add a callback for each bar that corresponds to a market/instrument pair
        for qt, mi in zip(quotes, mktimnt):
            graph.callback(qt, functools.partial(prices_update, market=mi[0], imnt=mi[1]))

        # Run the extractor blocking
        graph.stream_ctx().run_live()
    
    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        if self.prices:
            return
        # call extractor here on another thread
        self.proc = multiprocessing.Process(target=self.process, args=(imnts,))
        self.proc.start()

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

        self.seq = ytp.sequence(cfg['yamal_file'], readonly=True)
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

## Main
parser = argparse.ArgumentParser()
parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
parser.add_argument("--init", help="initialize OMS from the configuration", action='store_true')
parser.add_argument("--no-gui", help="initialize OMS from the configuration", action='store_true')
args = parser.parse_args()

if not os.path.isfile(args.cfg):
    print(f"configuration file {args.cfg} does not exist. Please provide a valid JSON configuration file.")
    exit(1)

cfg = json.load(open(args.cfg))

if args.init:
    builder = SymbologyBuilder(cfg)
    builder.write()
elif not os.path.isfile(cfg['yamal_file']):
    print(f"yamal file {cfg['yamal_file']} does not exist. Please provide a valid yamal file for the market symbology.")
    exit(1)

if not os.path.isfile(cfg['yamal_file_market_data']):
    print(f"yamal file {cfg['yamal_file_market_data']} does not exist. Please provide a valid yamal file for the market data.")
    exit(1)

if args.no_gui:
    exit()

## UI
UNAVAILABLE = '-'

def update_prices():
    p = mrkdata.prices.get((selectMarket.value, selectSecurity.value), {'bid': '-', 'ask': '-'})
    bidbutton.set_text(p['bid'])
    askbutton.set_text(p['ask'])

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('Account').style('width:10em;align-items:center;text-align:center;')
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    selectAccount = ui.select([]).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('Market').style('width:10em;align-items:center;text-align:center;')
    ui.label('Instrument').style('width:10em;align-items:center;text-align:center;')
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    def update_select_securities(market):
        selectSecurity.value = None
        selectSecurity.options = {}
        where = refdata.state.venuesSecurities.get(market, [])
        for sid in where:
            print(sid)
            selectSecurity.options[sid] = refdata.state.securities[sid].symbol
        selectSecurity.update()

    selectMarket = ui.select({}, on_change=lambda s: update_select_securities(s.value)).style('width:10em;align-items:center;text-align:center;')
    selectSecurity = ui.select({}, on_change=update_prices).style('width:10em;align-items:center;text-align:center;')

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
refdata = ReferenceData(cfg=cfg)
mrkdata = MarketData(cfg)

def updateUI(delta):
    if delta.accounts:
        selectAccount.options.extend(delta.accounts)
        selectAccount.update()
    
    for vid, v in delta.venuesNames.items():
        selectMarket.options[vid] = v.label
    if delta.venuesNames:
        selectMarket.update()
    
    where = delta.venuesSecurities.get(selectMarket.value, [])
    for sid in where:
        selectSecurity.options[sid] = delta.securities[sid].symbol
    if where:
        selectSecurity.update()

    update_prices()

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
mrkdata.proc.join()
