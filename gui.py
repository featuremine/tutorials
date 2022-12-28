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
import signals
from math import inf
import copy

def time_ns():
    return int(time.time() * 1000000000)

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class MarketDataGui(signals.MarketSignals):
    def __init__(self, seq, peer, prefix: str="ore/imnts/", sample: Optional[timedelta]=None) -> None:
        graph = extractor.system.comp_graph()
        graph.features.ytp_sequence(seq, timedelta(milliseconds=1))
        components = {"graph": graph, "systime": time_ns}
        super().__init__(components, peer,  prefix, sample)
        self.prices = multiprocessing.Manager().dict()
        self.proc = None
                
    def __del__(self):
        self.proc.join()

    def _process(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
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

        self.graph.stream_ctx().run_live()

    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        if self.proc:
            return

        self.proc = multiprocessing.Process(target=self._process, args=(imnts,))
        self.proc.start()

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
        self.orderid = 1
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
        # Parse order message received

    def _seq_clbck_send(self, peer, channel, time, data):
        print('_seq_clbck_send')
        d = schemas.strategy.ManagerMessage.from_bytes_packed(data).to_dict()
        print(d)
        self.requests.append(d)
        self.orderid += 1
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
                            'strgOrdID': self.orderid,
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
                            'tag': f"order{self.orderid}"
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
def padded_row():
    return ui.row().style('margin:1em;')

def expansion_bar(name):
    return ui.expansion(name).classes('w-full').props(add='switch-toggle-side').style('background-color: #e5e8e8')

UNAVAILABLE = '-'

def update_prices():
    p = mrkdata.prices.get((selectMarket.value, selectSecurity.value),
                           {'bidqty': '-','bidpx':'-','askqty':'-','askpx':'-'})
    bidlabel.set_text(p['bidpx'])
    asklabel.set_text(p['askpx'])

with ui.header().style('background-color: #3874c8').props('elevated'):
    with ui.column():
        with ui.row():
            ui.icon('monetization_on').style('top: 50%;transform: translateY(-10%)')
            ui.label('Featuremine Trading GUI')
    with ui.column().style('margin-start:auto;margin-end:right;align-items:right;'):
        selectAccount = ui.select([]).classes('items-center').style('width:10em;height:1em;').props(add='borderless').style('margin-start:auto;margin-end:right;align-items:right;text-align:right;')

with expansion_bar('orders BUY/SELL'):
    with padded_row():
        with ui.column():
            with ui.row():
                def update_select_securities(market):
                    selectSecurity.value = None
                    selectSecurity.options = {}
                    where = refdata.state.venuesSecurities.get(market, [])
                    for sid in where:
                        print(sid)
                        selectSecurity.options[sid] = refdata.state.securities[sid].symbol
                    selectSecurity.update()

                selectMarket = ui.select({}, on_change=lambda s: update_select_securities(s.value)).style('width:10em;align-items:center;text-align:center;').props(add='label=Market')
                selectSecurity = ui.select({}, on_change=update_prices).style('width:10em;align-items:center;text-align:center;').props(add='label=Instrument')
                
        with ui.column():
            with ui.row().style('align-items:center;'):
                ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
                ui.label('ask price').style('width:10em;align-items:center;text-align:center;')
            with ui.row().style('align-items:center;'):
                bidlabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')
                asklabel = ui.label(UNAVAILABLE).style('width:10em;align-items:center;text-align:center;')

    def update_qty():
        if notionalswitch.value:
            if is_number(qtyin.value) and is_number(pricein.value):
                qtyout.set_text("Quantity: {:.6f}".format(float(qtyin.value)/float(pricein.value)))
            else:
                qtyout.set_text(f"Quantity: -")
        else:
            if is_number(qtyin.value) and is_number(pricein.value):
                qtyout.set_text("Notional: {:.6f}".format(float(qtyin.value)*float(pricein.value)))
            else:
                qtyout.set_text(f"Notional: -")

    with padded_row():
        with ui.column():
            pricein = ui.input(label='Price', placeholder='0.00', on_change=update_qty).style('width:10em;align-items:center;text-align:center;')
        with ui.column():
            def update_askbid_checkbox(check):
                if check.sender == bidcheckbox and check.value:
                    askcheckbox.set_value(False)
                    pricein.props(add='readonly')
                elif check.sender == askcheckbox and check.value:
                    bidcheckbox.set_value(False)
                    pricein.props(add='readonly')
                else:
                    pricein.props(remove='readonly')

            bidcheckbox = ui.checkbox('bid', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;margin-top:1em;')
            askcheckbox = ui.checkbox('ask', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;align-items:center;text-align:center;')
        
        with ui.column():
            with ui.row():
                def switch_qty(notional):
                    qtyin.view.label = 'Notional' if notional else 'Quantity'
                    qtyin.update()
                    update_qty()
                        
                qtyin = ui.input(label='Quantity', placeholder='0.00', on_change=update_qty).style('width:10em;align-items:center;text-align:center;')
                with ui.column():
                    qtyout = ui.label('Notional: -').style('width:10em;align-items:center;text-align:left;margin-top:2em;')

                with ui.column():
                    notionalswitch = ui.switch('notional', on_change=lambda c: switch_qty(c.value)).style('margin-top:1em;')                

    with padded_row():
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
        ui.button('buy', on_click=lambda: parse_order('buy')).style('width:10em;align-items:center;text-align:center;').props('color=green')
        ui.button('sell', on_click=lambda: parse_order('sell')).style('width:10em;align-items:center;text-align:center;')


selected = []

table_options = {
            'defaultColDef': {
                'minWidth': 100,
                'filter': True,
                'cellStyle': {'display': 'flex ','justify-content': 'center'},
                'headerClass': 'font-bold'
            }, 
            'columnDefs': [
                {'headerName': 'Order', 'field': 'order'},
                {'headerName': 'Account', 'field': 'account'},
                {'headerName': 'Security', 'field': 'security'},
                {'headerName': 'Venue', 'field': 'venue'},
                {'headerName': 'Side', 'field': 'side'},
                {'headerName': 'Price', 'field': 'price'},
                {'headerName': 'Quantity', 'field': 'quantity'},
            ],
            'rowData': [],
        }

def create_orders_table(options):
    t = ui.table(options=options).style('margin:0;padding:0;height:100vh;width:100%;')
    for col_def in t.view.options.columnDefs:
        col_def.cellClass = ['text-2xl','text-white-500']
    return t
    
with expansion_bar('orders list'):
    with padded_row():
        with ui.column():
            def cancel_orders(b):
                global selected
                indices = [i for i, x in enumerate(selected) if x]
                for i in sorted(indices, reverse=True):
                    table_orders.options['rowData'].pop(i)
                if indices:
                    table_orders.update()
                    selected = [ x for i,x in enumerate(selected) if not x]

            ui.button('cancel', on_click=cancel_orders).style('width:10em').props('color=red')
                
    with padded_row():
        opt = copy.deepcopy(table_options)
        opt['columnDefs'].insert(0, {'headerName': '', 'field': 'enabled', 'cellRenderer': 'checkboxRenderer'})
        table_orders = create_orders_table(opt)
                
        def handle_change(sender, msg):
            selected[msg['rowIndex']] = msg['value']

        table_orders.view.on('cellValueChanged', handle_change)

with expansion_bar('orders event list'):                
    with padded_row():
        table_order_events = create_orders_table(table_options)

## Market Data
refdata = reference.ReferenceData(seq=seqref, cfg=cfg)
seqmkt = ytp.sequence(cfg['price_ytp'])
peermkt = seqmkt.peer(cfg['peer'])
mrkdata = MarketDataGui(seq=seqmkt, peer=peermkt, sample=timedelta(milliseconds=10))
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
        if 'strg' not in r['message']:
            continue
        msg = r['message']['strg']
        neword = msg['new'] # TODO: parse other messages
        table_entry = {
            'enabled': False,
            'order': neword['strgOrdID'],
            'account': neword['accountID'],
            'security': neword['securityId'],
            'venue': neword['venueID'],
            'side': neword['orderSide'],
            'price': '-' if 'market' in neword['orderType'] else neword['orderType']['limit'],
            'quantity': neword['quantity'] 
        }
        table_orders.options['rowData'].append(table_entry)
        selected.append(False)
        table_order_events.options['rowData'].append(table_entry)

    if requests or responses:
        table_orders.update()
        table_order_events.update()

orders.add_callback(update_orders_ui)

## Update UI
def update_elements():
    refdata.poll()
    orders.poll()

t = ui.timer(interval=0.01, callback=update_elements)

ui.run(title='Featuremine orders', reload=False, show=False)

