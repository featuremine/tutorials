from collections import defaultdict, namedtuple
from typing import Dict, Tuple, Optional
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
import reference
from math import inf

def time_ns():
    return int(time.time() * 1000000000)

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class MarketDataGui(reference.MarketData):
    def __init__(self, peer, graph, prefix: str="ore/imnts/", period: Optional[timedelta]=None) -> None:
        super().__init__(peer, graph, prefix, period)
        self.prices = multiprocessing.Manager().dict()
                
    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        if self.prices:
            return
        
        def prices_update(x, ids):
            self.prices[ids] = {
                'bidqty': str(x[0].bidqty),
                'bidpx': str(x[0].bidprice),
                'askqty': str(x[0].askqty),
                'askpx': str(x[0].askprice),
            }
        
        super().process(imnts)
        
        for ids, quote in self.quotes.items():
            self.graph.callback(quote, functools.partial(prices_update, ids=ids))

class Orders(object):
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.seq = ytp.sequence(self.cfg['strategy_ytp'])
        self.peer = self.seq.peer(self.cfg['peer'])
        self.chsnd = self.peer.channel(time_ns(), f"{self.cfg['strategy_prefix']}{self.cfg['oms_name']}/{self.cfg['client_name']}")
        self.streamsnd = self.peer.stream(self.chsnd)
        self.seq.data_callback(f"{self.cfg['strategy_prefix']}{self.cfg['client_name']}/{self.cfg['oms_name']}", self._seq_clbck_rcv)
        self.seq.data_callback(f"{self.cfg['strategy_prefix']}{self.cfg['oms_name']}/{self.cfg['client_name']}", self._seq_clbck_send)
        self.requests = []
        self.responses = []
        self.callbacks = []
        self.ordid = 1
        self.seqnum = 1

    def add_callback(self, clb):
        self.callbacks.append(clb)

    def send(self, order: dict):
        print('send')
        print(order)
        msg = schemas.strategy.ManagerMessage.new_message()
        msg.from_dict(order)
        self.streamsnd.write(time_ns(), msg.to_bytes_packed())

    def _seq_clbck_rcv(self, peer, channel, time, data):
        print('_seq_clbck_rcv')
        d = schemas.strategy.ManagerMessage.from_bytes_packed(data).to_dict()
        print(d)
        self.responses.append(d)
        # OMS responses
        # ack, rejection, received
        # Parse order message received

    def _seq_clbck_send(self, peer, channel, time, data):
        print('_seq_clbck_send')
        d = schemas.strategy.ManagerMessage.from_bytes_packed(data).to_dict()
        print(d)
        #OMS requests
        self.requests.append(d)
        # TODO:order placement -> increment order id
        self.ordid += 1
        self.seqnum += 1
        # Parse order message sent
        
    def poll(self, limit=None):
        self.requests = []
        self.responses = []
        count = 0
        while self.seq.poll() and (not limit or count <= limit):
            count += 1
        
        if self.requests or self.responses:
            for c in self.callbacks:
                c(self.requests, self.responses)

    def limit(self, accid, secid, venid, side, ordpx, qty):
        return {
                'message': {
                    'strg': {
                        'new': {
                            'strgOrdID': self.ordid,
                            'accountID': accid,
                            'securityId': secid,
                            'venueID': venid,
                            'orderSide': side,
                            'orderType': {'limit': ordpx},
                            'quantity': qty,
                            'maxFloor': {'none': None},
                            'minQty': {'none': None},
                            'timeInForce': 'day',
                            'algorithm': { 'dma': None },
                            'tag': f"order{self.ordid}"
                        }
                    }
                },
                'seqnum': self.seqnum
            }
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
    seqref = ytp.sequence(cfg['state_ytp'])
    peerref = seqref.peer(cfg['peer'])
    builder = reference.ReferenceBuilder(peerref, cfg)
    builder.write()
elif not os.path.isfile(cfg['state_ytp']):
    print(f"yamal file {cfg['state_ytp']} does not exist. Please provide a valid yamal file for the market symbology.")
    exit(1)

if not os.path.isfile(cfg['price_ytp']):
    print(f"yamal file {cfg['price_ytp']} does not exist. Please provide a valid yamal file for the market data.")
    exit(1)

if args.no_gui:
    exit()

## UI
UNAVAILABLE = '-'

def update_prices():
    p = mrkdata.prices.get((selectMarket.value, selectSecurity.value),
                           {'bidqty': '-','bidpx':'-','askqty':'-','askpx':'-'})
    bidlabel.set_text(p['bidpx'])
    asklabel.set_text(p['askpx'])

with ui.header().style('background-color: #3874c8').props('elevated'):
    ui.icon('monetization_on')
    ui.label('Featuremine Trading GUI').style('width:15em;align-items:left;text-align:left;')
    with ui.row().style('margin-start:auto;margin-end:right;align-items:right;'):
        selectAccount = ui.select([]).style('width:10em;height:1em;align-items:right;text-align:right;')

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
    bidlabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')
    asklabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')

def update_qty():
    if notionalcheckbox.value:
        if is_number(qtyin.value) and is_number(pricein.value):
            qtyout.set_text("Quantity: {:.6f}".format(float(qtyin.value)/float(pricein.value)))
        else:
            qtyout.set_text(f"Quantity: -")
    else:
        if is_number(qtyin.value) and is_number(pricein.value):
            qtyout.set_text("Notional: {:.6f}".format(float(qtyin.value)*float(pricein.value)))
        else:
            qtyout.set_text(f"Notional: -")

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    pricein = ui.input(label='Price', placeholder='0.00', on_change=update_qty).style('width:8em;align-items:center;text-align:center;')
    with ui.column().style('margin-start:auto;margin-end:auto;align-items:center;'):
        def update_askbid_checkbox(check):
            if check.sender == bidcheckbox and check.value:
                askcheckbox.set_value(False)
                pricein.props(add='readonly')
            elif check.sender == askcheckbox and check.value:
                bidcheckbox.set_value(False)
                pricein.props(add='readonly')
            else:
                pricein.props(remove='readonly')
        
        bidcheckbox = ui.checkbox('bid', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')
        askcheckbox = ui.checkbox('ask', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    def switch_qty(notional):
        qtyin.view.label = 'Notional' if notional else 'Quantity'
        qtyin.update()
        update_qty()
            
    qtyin = ui.input(label='Quantity', placeholder='0.00', on_change=update_qty).style('width:8em;align-items:center;text-align:center;')
    notionalcheckbox = ui.checkbox('notional', on_change=lambda c: switch_qty(c.value)).style('width:5em;height:1em;align-items:center;text-align:center;')
    
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    qtyout = ui.label('Notional: -').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    def parse_order(side):
        if not selectAccount.value:
            ui.notify('please select an account')
            return
        elif not selectMarket.value:
            ui.notify('please select a market')
            return
        elif not selectSecurity.value:
            ui.notify('please select a security')
            return
        elif not is_number(qtyin.value):
            ui.notify('please select a valid quantity')
            return
        elif not is_number(pricein.value):
            ui.notify('please select a valid price')
            return
            
        orders.send(orders.limit(
            accid=int(selectAccount.value), secid=int(selectSecurity.value),
            venid=int(selectMarket.value), side=side, ordpx=float(pricein.value),
            qty=float(qtyin.value)))
        ui.notify('An order was sent')
    ui.button('buy', on_click=lambda: parse_order('buy')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    ui.button('sell', on_click=lambda: parse_order('sell')).style('width:9em;align-items:center;text-align:center;')

with ui.expansion('orders', icon='work').classes('w-full'):
    orderslog = ui.log(max_lines=100).classes('w-full h-16')

## Market Data
refdata = reference.ReferenceData(seq=seqref, cfg=cfg)
graph = extractor.system.comp_graph()
op = graph.features
seqmkt = ytp.sequence(cfg['price_ytp'])
op.ytp_sequence(seqmkt, timedelta(milliseconds=1))
peermkt = seqmkt.peer(cfg['peer'])
mrkdata = MarketDataGui(peer=peermkt, graph=graph, period=timedelta(milliseconds=10))
orders = Orders(cfg=cfg)

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
    
    if bidcheckbox.value:
        pricein.set_value(bidlabel.text)
    elif askcheckbox.value:
        pricein.set_value(asklabel.text)

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

def update_orders_ui(requests, responses):
    for r in requests:
        orderslog.push(f"order id {r['message']['strg']['new']['strgOrdID']}")

orders.add_callback(update_orders_ui)

## Update UI
def update_elements():
    refdata.poll()
    orders.poll()

t = ui.timer(interval=0.01, callback=update_elements)

## Run UI and extractor process
refdata.poll() # Remove after changes to be able to modify graphs on the fly
proc = multiprocessing.Process(target=graph.stream_ctx().run_live)
proc.start()

ui.run(title='Featuremine orders', reload=False, show=False)

proc.join()
