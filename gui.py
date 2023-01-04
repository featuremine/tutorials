from typing import Dict, Tuple, Optional, NamedTuple
from collections import defaultdict
from nicegui import ui
import argparse
import json, time
from datetime import timedelta
import multiprocessing
import functools
import os
import reference
import signals
import copy

from common import SystemTime, StrgOrdIds, ManagerMessageWriter, StrategyOrderUpdater, OrderStateTable, Side

from yamal import ytp
import extractor
from conveyor.utils import schemas


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class GuiSysTime(SystemTime):
    def __call__(self) -> int:
        return int(time.time() * 1000000000)

class MarketDataGui(object):
    def __init__(self, cfg, sample: Optional[timedelta]=None) -> None:
        self.cfg = cfg
        self.sample = sample
        self.prices = multiprocessing.Manager().dict()
        self.proc = None
        
    def __del__(self):
        if self.proc:
            self.proc.join()

    def _process(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        graph = extractor.system.comp_graph()
        seq = ytp.sequence(self.cfg['price_ytp'])
        peer = seq.peer(self.cfg['peer'])
        graph.features.ytp_sequence(seq, timedelta(milliseconds=1))
        systime = GuiSysTime()

        components = {"graph": graph, "systime": systime}
        sig = signals.MarketSignals(components, peer, 'ore/imnts/', self.sample)

        def prices_update(x, ids):
            self.prices[ids] = {
                'bidqty': str(x[0].bidqty),
                'bidpx': str(x[0].bidprice),
                'askqty': str(x[0].askqty),
                'askpx': str(x[0].askprice),
            }
        
        sig.process(imnts)
        
        for ids, quote in sig.quotes.items():
            graph.callback(quote, functools.partial(prices_update, ids=ids))

        graph.stream_ctx().run_live()

    def subscribe(self, imnts: Dict[Tuple[int, int], Tuple[str,str]]) -> None:
        if self.proc:
            return

        self.proc = multiprocessing.Process(target=self._process, args=(imnts,))
        self.proc.start()

class OrderKey(NamedTuple):
    strg: str
    idx: int

class TradingKey(NamedTuple):
    imnt: int
    venue: int
    account: int

class TradingInfo(NamedTuple):
    writer: ManagerMessageWriter
    updater: StrategyOrderUpdater
    orders: OrderStateTable

if __name__ == '__main__':
    ## Main
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", help="configuration file in JSON format", required=True, type=str)
    args = parser.parse_args()

    if not os.path.isfile(args.cfg):
        print(f"configuration file {args.cfg} does not exist. Please provide a valid JSON configuration file.")
        exit(1)

    cfg = json.load(open(args.cfg))

    if not os.path.isfile(cfg['state_ytp']):
        print(f"yamal file {cfg['state_ytp']} does not exist. Please provide a valid yamal file for the market symbology.")
        exit(1)

    if not os.path.isfile(cfg['price_ytp']):
        print(f"yamal file {cfg['price_ytp']} does not exist. Please provide a valid yamal file for the market data.")
        exit(1)

    ## Market Data
    seqref = ytp.sequence(cfg['state_ytp'])
    refdata = reference.ReferenceData(seq=seqref, cfg=cfg)

    systime = GuiSysTime()

    mrkdata = MarketDataGui(cfg=cfg, sample=timedelta(milliseconds=10))

    strg_pfx = cfg['strategy_prefix']
    g_oms_name = cfg['oms_name']
    g_strg_name = cfg['peer']

    seqstrg = ytp.sequence(cfg['strategy_ytp'])
    peerstrg = seqstrg.peer(g_strg_name)
    g_ord_ch = peerstrg.channel(systime(), f"{strg_pfx}/{g_oms_name}/{g_strg_name}")
    g_ord_stream = peerstrg.stream(g_ord_ch)
    g_writer = ManagerMessageWriter(systime=systime, ctx={'stream': g_ord_stream})
    e_writer = ManagerMessageWriter(systime=systime)

    strg_ord_ids = StrgOrdIds(1000)

    ## UI
    def padded_row():
        return ui.row().style('margin:1em;')

    def expansion_bar(name):
        return ui.expansion(name).classes('w-full').props(add='switch-toggle-side').style('background-color: #e5e8e8')

    UNAVAILABLE = '-'

    with ui.header().style('background-color: #3874c8').props('elevated'):
        with ui.column():
            with ui.row():
                ui.icon('monetization_on').style('top: 50%;transform: translateY(-10%)')
                ui.label('Featuremine Trading GUI')
        with ui.column().style('margin-start:auto;margin-end:right;align-items:right;'):
            selectAccount = ui.select([]).style('width:10em;height:1em;').props(add='borderless label=Account')

    def update_prices():
        p = mrkdata.prices.get((selectMarket.value, selectSecurity.value),
                            {'bidqty': '-','bidpx':'-','askqty':'-','askpx':'-'})
        bidlabel.set_text(p['bidpx'])
        asklabel.set_text(p['askpx'])
        if bidcheckbox.value:
            pricein.set_value(p['bidpx'])
        elif askcheckbox.value:
            pricein.set_value(p['askpx'])

    with expansion_bar('orders BUY/SELL'):
        with padded_row():
            with ui.column():
                with ui.row():
                    def update_select_securities(market):
                        selectSecurity.value = None
                        selectSecurity.options = {}
                        for sid in refdata.state.venuesSecurities.get(market, []):
                            selectSecurity.options[sid] = refdata.state.securities[sid].symbol
                        selectSecurity.update()

                    selectMarket = ui.select({}, on_change=lambda s: update_select_securities(s.value)).style('width:10em;').props(add='label=Market')
                    selectSecurity = ui.select({}, on_change=update_prices).style('width:10em;').props(add='label=Instrument')
                    
            with ui.column():
                with ui.row().style('align-items:center;'):
                    ui.label('bid price').style('width:10em;text-align:center;')
                    ui.label('ask price').style('width:10em;text-align:center;')
                with ui.row().style('align-items:center;'):
                    bidlabel = ui.label(UNAVAILABLE).style('width:10em;text-align:center;')
                    asklabel = ui.label(UNAVAILABLE).style('width:10em;text-align:center;')

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
                pricein = ui.input(label='Price', placeholder='0.00', on_change=update_qty).style('width:10em;')
            with ui.column():
                def update_askbid_checkbox(check):
                    if check.value:
                        (askcheckbox if check.sender == bidcheckbox else bidcheckbox).set_value(False)
                        pricein.props(add='readonly')
                    else:
                        pricein.props(remove='readonly')

                bidcheckbox = ui.checkbox('bid', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;margin-top:1em;')
                askcheckbox = ui.checkbox('ask', on_change=lambda c: update_askbid_checkbox(c)).style('width:5em;height:1em;')
            
            with ui.column():
                with ui.row():
                    def switch_qty(notional):
                        qtyin.view.label = 'Notional' if notional else 'Quantity'
                        qtyin.update()
                        update_qty()
                            
                    qtyin = ui.input(label='Quantity', placeholder='0.00', on_change=update_qty).style('width:10em;')
                    with ui.column():
                        qtyout = ui.label('Notional: -').style('width:10em;text-align:left;margin-top:2em;')

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

                px = float(pricein.value) if pricein.value else None
                g_writer.place(accountID=int(selectAccount.value), \
                               securityId=int(selectSecurity.value), venueID=int(selectMarket.value), \
                               strgOrdID=strg_ord_ids(), orderSide=side, px=px, \
                               quantity=float(qtyin.value), maxFloor=None, minQty=None, \
                               timeInForce='day', algorithm=None, tag='')

                ui.notify('An order was sent')
            ui.button('buy', on_click=lambda: parse_order('buy')).style('width:10em;').props('color=green')
            ui.button('sell', on_click=lambda: parse_order('sell')).style('width:10em;')


    selected = set()
    column_defs = {
                    'minWidth': 100,
                    'maxHeight': 800,
                    'filter': True,
                    'resizable': True,
                    'cellStyle': {'display': 'flex ','justify-content': 'center'},
                    'headerClass': 'font-bold'
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
                    for i in selected:
                        row = table_orders.options['rowData'][i]
                        ord_ch = peerstrg.channel(systime(), f"{strg_pfx}/{row['oms']}/{row['strg']}")
                        ord_stream = peerstrg.stream(ord_ch)
                        e_writer.cancel(stream=ord_stream, strgOrdID=row['id'])
                        
                ui.button('cancel', on_click=cancel_orders).style('width:10em').props('color=red')
                    
        with padded_row():
            table_options = {
                'defaultColDef': column_defs, 
                'columnDefs': [
                    {'headerName': '', 'field': 'enabled', 'cellRenderer': 'checkboxRenderer'},
                    {'headerName': 'ID', 'field': 'id'},
                    {'headerName': 'Account', 'field': 'account'},
                    {'headerName': 'Security', 'field': 'security'},
                    {'headerName': 'Venue', 'field': 'venue'},
                    {'headerName': 'Strategy', 'field': 'strg'},
                    {'headerName': 'OMS', 'field': 'oms'},
                    {'headerName': 'Side', 'field': 'side'},
                    {'headerName': 'Price', 'field': 'price'},
                    {'headerName': 'Quantity', 'field': 'quantity'},
                    {'headerName': 'Status', 'field': 'done'},
                ],
                'rowData': [],
            }
            table_orders = create_orders_table(table_options)
                    
            def handle_change(sender, msg):
                if msg['value']:
                    selected.add(msg['rowIndex'])
                else:
                    selected.remove(msg['rowIndex'])

            table_orders.view.on('cellValueChanged', handle_change)

    with expansion_bar('orders event list'):                
        with padded_row():
            table_options = {
                'defaultColDef': column_defs, 
                'columnDefs': [
                    {'headerName': 'Type', 'field': 'type'},
                    {'headerName': 'ID', 'field': 'id'},
                    {'headerName': 'Account', 'field': 'account'},
                    {'headerName': 'Security', 'field': 'security'},
                    {'headerName': 'Venue', 'field': 'venue'},
                    {'headerName': 'Strategy', 'field': 'strg'},
                    {'headerName': 'OMS', 'field': 'oms'},
                    {'headerName': 'Side', 'field': 'side'},
                    {'headerName': 'Price', 'field': 'price'},
                    {'headerName': 'Quantity', 'field': 'quantity'},
                ],
                'rowData': [],
            }
            table_order_events = create_orders_table(table_options)

    def update_ui(delta):
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

    refdata.add_callback(update_ui)

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

    orders = OrderStateTable()
    updater = StrategyOrderUpdater(orders)
    tradeinfos = defaultdict(TradingInfo)

    strg_pfx_len = len(strg_pfx) + 1
    def order_update(peer, channel, time, data):
        msg = schemas.strategy.ManagerMessage.from_bytes_packed(data)
        first, _, second = channel.name()[strg_pfx_len:].partition('/')
        msgtype = msg.message.which()
        if msgtype == 'strg':
            strg = second
            oms = first
        else:
            strg = first
            oms = second
        msgdata = getattr(msg.message, msgtype)
        ord = updater({
            "strg": strg,
            "oms": oms,
            "msg": msg
            })
        if ord is None or 'strgOrdID' not in ord.info:
            return
        new_order = not strg_ord_ids.exists(ord.info['strgOrdID'])
        if strg == g_strg_name and oms == g_oms_name:
            strg_ord_ids.add(ord.info['strgOrdID'])

        if new_order:
            table_entry = {
                'enabled': False,
                'type': msgdata.which(),
                'id': ord.info['strgOrdID'],
                'account': ord.info['accountID'],
                'security': ord.info['securityId'],
                'venue': ord.info['venueID'],
                'strg': strg,
                'oms': oms,
                'side': 'buy' if ord.side == Side.BID else 'sell',
                'price': ord.px,
                'quantity': ord.qty,
                'done': 'done' if ord.done else 'active'
            }
            table_orders.options['rowData'].append(table_entry)
            table_orders.update()
            table_order_events.options['rowData'].append(table_entry)
        else: 
            for o in table_orders.options['rowData']:
                if o['id'] == ord.info['strgOrdID']:
                    #TODO: change order status if necessary
                    pass
            # TODO: fill this entry with proper values
            table_event_entry = {
                'type': msgdata.which(),
                'id': ord.info['strgOrdID'],
                'account': ord.info['accountID'],
                'security': ord.info['securityId'],
                'venue': ord.info['venueID'],
                'strg': strg,
                'oms': oms,
                'side': '',
                'price': '',
                'quantity': ''
            }
            table_order_events.options['rowData'].append(table_event_entry)
                        
        table_order_events.update()
                              
    seqstrg.data_callback(f"{cfg['strategy_prefix']}/", order_update)

    ## Update UI
    def update_elements():
        refdata.poll()
        seqstrg.poll()

    t = ui.timer(interval=0.01, callback=update_elements)

    ui.run(title='Featuremine orders', reload=False, show=False)
