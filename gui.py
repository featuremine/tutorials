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

from common import SystemTime, StrgOrdIds, ManagerMessageWriter
from common import StrategyOrderUpdater, OrderStateTable, Side, OrderEventDetails

from yamal import ytp
import extractor
from conveyor.utils import schemas


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

# only 'equals' for now
def is_filtered(row, filter_model):
    for k, v in row.items():
        if k in filter_model:
            if filter_model[k]['filter'] != str(v):
                return True
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
    oms: str
    idx: int

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
    oe_details = OrderEventDetails()

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

    order_row = {}
    
    ## UI
    def padded_row():
        return ui.row().style('margin:1em;')

    def expansion_bar(name):
        return ui.expansion(name).classes('w-full').props(add='switch-toggle-side').style('background-color: #e5e8e8')

    async def update_filters():
        async def set_filters(table):
            filter = await table.call_api_method('getFilterModel')
            ref = refdata.state
            if selectAccount.value:
                filter['account'] = {'filterType': 'text', 'type': 'equals', 'filter': str(selectAccount.value)}
            if selectMarket.value:
                filter['venue'] = {'filterType': 'text', 'type': 'equals', 'filter': ref.venuesNames[selectMarket.value].label}
            if selectSecurity.value:
                filter['security'] = {'filterType': 'text', 'type': 'equals', 'filter': ref.securities[selectSecurity.value].symbol}
            if not guiswitch.value:
                filter['oms'] = {'filterType': 'text', 'type': 'equals', 'filter': g_oms_name}
                filter['strg'] = {'filterType': 'text', 'type': 'equals', 'filter': g_strg_name}
            else:
                filter.pop('oms', None)
                filter.pop('strg', None)
            if table.id == table_orders.id:
                if activecheckbox.value:
                    filter['done'] = {'filterType': 'text', 'type': 'equals', 'filter': 'active'}
                else:
                    filter.pop('done', None)
            await table.call_api_method('setFilterModel', filter)

        await set_filters(table_order_events)
        await set_filters(table_orders)

    UNAVAILABLE = '-'

    with ui.header().style('background-color: #3874c8').props('elevated'):
        with ui.column():
            with ui.row():
                ui.icon('monetization_on').style('top: 50%;transform: translateY(-10%)')
                ui.label('Featuremine Trading GUI')
        with ui.column().style('margin-start:auto;margin-end:right;align-items:right;'):
            with ui.row():
                guiswitch = ui.switch('All Orders', value=True, on_change=update_filters).classes('text-black').style('height:1em;').props(add='v-model=green color=green')  
                selectAccount = ui.select([], on_change=update_filters).style('width:10em;height:1em;').props(add='borderless label=Account clearable')

    def update_prices():
        if not selectMarket.value or not selectSecurity.value:
            bidpx = '-'
            askpx = '-'
        else:
            p = mrkdata.prices.get((selectMarket.value, selectSecurity.value),
                                {'bidqty': '-','bidpx':'-','askqty':'-','askpx':'-'})
            bidpx = p['bidpx']
            askpx = p['askpx']
        bidlabel.set_text(bidpx)
        asklabel.set_text(askpx)
        if bidcheckbox.value:
            pricein.set_value(bidpx)
        elif askcheckbox.value:
            pricein.set_value(askpx)

    with expansion_bar('orders BUY/SELL'):
        with padded_row():
            with ui.column():
                with ui.row():
                    def on_market_select():
                        selectSecurity.value = None
                        selectSecurity.options = {}
                        for sid in refdata.state.venuesSecurities.get(selectMarket.value, []):
                            selectSecurity.options[sid] = refdata.state.securities[sid].symbol
                        selectSecurity.update()
                    selectMarket = ui.select({}, on_change=on_market_select).style('width:10em;').props(add='label=Market clearable')
                    selectSecurity = ui.select({}, on_change=update_filters).style('width:10em;').props(add='label=Instrument clearable')
                    
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
                        qtyin.label = 'Notional' if notional else 'Quantity'
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
                qty = float(qtyin.value)/float(pricein.value) if notionalswitch.value else float(qtyin.value)
                g_writer.place(accountID=int(selectAccount.value), \
                               securityId=int(selectSecurity.value), venueID=int(selectMarket.value), \
                               strgOrdID=strg_ord_ids(), orderSide=side, px=px, \
                               quantity=qty, maxFloor=None, minQty=None, \
                               timeInForce='day', algorithm=None, tag='')

                ui.notify('An order was sent')
            ui.button('buy', on_click=lambda: parse_order('buy')).style('width:10em;').props('color=green')
            ui.button('sell', on_click=lambda: parse_order('sell')).style('width:10em;')


    selected = set()
    column_defs = {
                    'cellClass': ['text-2xl', 'text-white-500'],
                    'width': 165,
                    'minWidth': 100,
                    'filter': True,
                    'resizable': True,
                    'cellStyle': {'display': 'flex','justify-content': 'center'},
                    'headerClass': 'font-bold'
                }
    def create_orders_table(options):
        t = ui.table(options=options).style('margin:0;padding:0;height:100vh;width:100%;')

        async def table_auto_size():
            try:
                await t.call_api_method("sizeColumnsToFit")
                await t.call_api_method("setDomLayout", 'autoHeight')
            except:
                pass
        
        ui.timer(interval=0.3, callback=table_auto_size)
        return t
        
    with expansion_bar('orders list'):
        with padded_row():
            with ui.column():
                async def cancel_orders():
                    global selected
                    ref = refdata.state
                    filter_model = await table_orders.call_api_method('getFilterModel')
                    for key in selected:
                        o = orders[(key.strg, key.oms, key.idx)]
                        frow = {
                            'id': key.idx,
                            'account': o.info['accountID'],
                            'security': ref.securities[o.info['securityId']].symbol,
                            'venue': ref.venuesNames[o.info['venueID']].label,
                            'strg': key.strg,
                            'oms': key.oms,
                            'side': 'buy' if o.side == Side.BID else 'sell',
                            'price': o.px,
                            'quantity': o.qty,
                            'done': 'active'
                        }
                        if not is_filtered(frow, filter_model):
                            ord_ch = peerstrg.channel(systime(), f"{strg_pfx}/{key.oms}/{key.strg}")
                            ord_stream = peerstrg.stream(ord_ch)
                            e_writer.cancel(stream=ord_stream, strgOrdID=key.idx)
                        
                ui.button('cancel', on_click=cancel_orders).style('width:10em').props('color=red')
            
            async def select_all(sender):                
                global selected
                if sender.sender.id == clearallbut.id:
                    selected.clear()
                    for o in table_orders.options['rowData']:
                        o['enabled'] = False
                elif sender.sender.id == selectallbut.id:
                    filter_model = await table_orders.call_api_method('getFilterModel')
                    for o in table_orders.options['rowData']:
                        if not is_filtered(o, filter_model):
                            o['enabled'] = True
                            selected.add(OrderKey(strg=o['strg'], oms=o['oms'], idx=o['id']))
                table_orders.update()

            with ui.column():
                selectallbut = ui.button('Select All', on_click=select_all).style('width:10em').props('color=blue')
                
            with ui.column():
                clearallbut = ui.button('Clear All', on_click=select_all).style('width:10em').props('color=blue')
                
            with ui.column():
                activecheckbox = ui.checkbox('active', on_change=update_filters)
                    
                    
        with padded_row():
            table_options = {
                'defaultColDef': column_defs, 
                'columnDefs': [
                    {'headerName': '', 'field': 'enabled', 'cellRenderer': 'checkboxRenderer', 'suppressSizeToFit': True, 'width': 40, 'minWidth': 40},
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
            def handle_change(msg):
                row = msg['args']['data']
                o = OrderKey(strg=row['strg'], oms=row['oms'], idx=row['id'])
                if msg['args']['value']:
                    selected.add(o)
                else:
                    selected.remove(o)

            table_orders.on('cellValueChanged', handle_change)

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
                    {'headerName': 'Reason', 'field': 'reason'},
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
        ord = updater({
            "strg": strg,
            "oms": oms,
            "msg": msg
            })
        if ord is None:
            return

        if strg == g_strg_name and oms == g_oms_name:
            strg_ord_ids.add(ord.info['strgOrdID'])
            
        ref = refdata.state

        table_orders_entry = {
            'enabled': False,
            'id': ord.info['strgOrdID'],
            'account': ord.info['accountID'],
            'security': ref.securities[ord.info['securityId']].symbol,
            'venue': ref.venuesNames[ord.info['venueID']].label,
            'strg': strg,
            'oms': oms,
            'side': 'buy' if ord.side == Side.BID else 'sell',
            'price': '-' if ord.px is None else ord.px,
            'quantity': ord.qty,
            'done': 'done' if ord.done else 'active'
        }
        key = (strg, oms, ord.info['strgOrdID'])
        if key in order_row:
            table_orders.options['rowData'][order_row[key]] = table_orders_entry
        else:
            order_row[key] = len(table_orders.options['rowData'])
            table_orders.options['rowData'].append(table_orders_entry)
        table_orders.update()

        tp, px, qt, reason = oe_details(msg)
        table_event_entry = {
            'type': tp,
            'id': ord.info['strgOrdID'],
            'account': ord.info['accountID'],
            'security': ref.securities[ord.info['securityId']].symbol,
            'venue': ref.venuesNames[ord.info['venueID']].label,
            'strg': strg,
            'oms': oms,
            'side': 'buy' if ord.side == Side.BID else 'sell',
            'price': '-' if px is None else px,
            'quantity': '-' if qt is None else qt,
            'reason': reason
        }
        table_order_events.options['rowData'].append(table_event_entry)
        table_order_events.update()
                              
    seqstrg.data_callback(f"{cfg['strategy_prefix']}/", order_update)

    ## Update UI
    def update_elements():
        refdata.poll()
        seqstrg.poll()
            
    ui.timer(interval=0.01, callback=update_elements)

    ui.run(title='Featuremine orders', reload=False, show=False)
