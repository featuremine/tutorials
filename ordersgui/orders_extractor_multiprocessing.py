#!/usr/bin/env python3

from yamal import ytp
import extractor
import functools
from datetime import timedelta
from time import time_ns
import multiprocessing
from ctypes import c_char_p
import time
from nicegui import ui

## Globals
manager = multiprocessing.Manager()
gbidprice = manager.Value('d', 1.0)
gaskprice = manager.Value('d', 1.0)
gmarket = manager.Value(c_char_p, 'coinbase')
gimnt = manager.Value(c_char_p, 'BTC-USD')

## Thread
def extractor_thread():
    global gmarket, gimnt, gbidprice, gaskprice
    prefix = "ore/imnts"
    graph = extractor.system.comp_graph()
    op = graph.features

    def prices_update(x, market, imnt):
        global gmarket, gimnt, gbidprice, gaskprice
        if gmarket.get() == market and gimnt.get() == imnt:
            gbidprice.set(float(x[0].bidprice))
            gaskprice.set(float(x[0].askprice))

    markets = 'coinbase'
    imnts = 'BTC-USD,ETH-USD,DOGE-USD,USDT-USD'
    # Parse markets and instruments
    channels = []
    mktimnt = []
    for imnt in imnts.split(','):
        for mkt in markets.split(','):
            channels += [f"{prefix}/{mkt}/{imnt}"] # YTP channels for each market/instrument pair
            mktimnt += [(mkt,imnt)] # market/instrument pair

    seq = ytp.sequence('ore_coinbase_l2.ytp')
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    peer = seq.peer('feed_handler')
    upds = [op.decode_data(op.ore_ytp_decode(peer.channel(time_ns(), ch))) for ch in channels]

    levels = [op.book_build(upd, 1) for upd in upds]
    times = [op.book_vendor_time(upd) for upd in upds]

    quotes = [op.combine(level,
                    (("bid_prx_0", "bidprice"),
                     ("bid_shr_0", "bidqty"),
                     ("ask_prx_0", "askprice"),
                     ("ask_shr_0", "askqty")))
            for level in levels]

    # Add a callback for each bar that corresponds to a market/instrument pair
    for qt, mi in zip(quotes, mktimnt):
       graph.callback(qt, functools.partial(prices_update, market=mi[0], imnt=mi[1]))

    # Run the extractor blocking
    graph.stream_ctx().run_live()

uithread = multiprocessing.Process(target=extractor_thread)
uithread.start()


## UI
markets_imnts = {
    'coinbase' : [
        'BTC-USD',
        'ETH-USD',
        'DOGE-USD',
        'USDT-USD'
    ]
}

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    select_market = ui.select(list(markets_imnts.keys()), value=gmarket.get(), on_change=lambda s: gmarket.set(s.value)).style('width:10em;align-items:center;text-align:center;')
    select_instrument = ui.select(markets_imnts['coinbase'], value=gimnt.get(), on_change=lambda s: gimnt.set(s.value)).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
    ui.label('ask price').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    bidbutton = ui.button(gbidprice.get(), on_click=lambda: ui.notify('bid price was pressed')).style('width:10em;align-items:center;text-align:center;').props('color=green')
    askbutton = ui.button(gaskprice.get(), on_click=lambda: ui.notify('ask price was pressed')).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Price', placeholder='0.00', on_change=lambda e: print(+ e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('buy on ask', on_click=lambda: ui.notify('buy on ask was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    ui.button('buy on bid', on_click=lambda: ui.notify('buy on bid was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Quantity', placeholder='0.00', on_change=lambda e: print(+ e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('sell on bid', on_click=lambda: ui.notify('sell on bid was pressed')).style('width:9em;align-items:center;text-align:center;')
    ui.button('sell on ask', on_click=lambda: ui.notify('sell on ask was pressed')).style('width:9em;align-items:center;text-align:center;')


def update_elements():
    global gmarket, gimnt, gbidprice, gaskprice, bidbutton, askbutton
    bidbutton.set_text(gbidprice.get())
    askbutton.set_text(gaskprice.get())
    print('update_elements')
    print(gbidprice.get())
    print(gaskprice.get())

t = ui.timer(interval=1, callback=update_elements)

## Setup
ui.run(title='Featuremine orders', reload=False, show=False)
uithread.join()
