#!/usr/bin/env python3

import threading
import time
import random
from nicegui import ui

## Globals
run = True
r = 1
thread_lock = threading.Lock()

## Thread
def parallel_function():
    global r, run, thread_lock
    while run:
        thread_lock.acquire()
        r = random.uniform(1.000001, 123456789.99999)
        thread_lock.release()
        print('debug')
        print(r)        
        time.sleep(1)

uithread = threading.Thread(target=parallel_function)
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
    select_market = ui.select(list(markets_imnts.keys())).style('width:10em;align-items:center;text-align:center;')
    select_instrument = ui.select(markets_imnts['coinbase']).style('width:10em;align-items:center;text-align:center;')


with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.label('bid price').style('width:10em;align-items:center;text-align:center;')
    ui.label('ask price').style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    bidbutton = ui.button(123456789.123456, on_click=lambda: ui.notify('bid price was pressed')).style('width:10em;align-items:center;text-align:center;').props('color=green')
    askbutton = ui.button(123456789.123456, on_click=lambda: ui.notify('ask price was pressed')).style('width:10em;align-items:center;text-align:center;')

with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Price', placeholder='0.00', on_change=lambda e: print(+ e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('buy on ask', on_click=lambda: ui.notify('buy on ask was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    ui.button('buy on bid', on_click=lambda: ui.notify('buy on bid was pressed')).style('width:9em;align-items:center;text-align:center;').props('color=green')
    
with ui.row().style('margin-start:auto;margin-end:auto;align-items:center;'):
    ui.input(label='Quantity', placeholder='0.00', on_change=lambda e: print(+ e.value)).style('width:8em;align-items:center;text-align:center;')
    ui.button('sell on bid', on_click=lambda: ui.notify('sell on bid was pressed')).style('width:9em;align-items:center;text-align:center;')
    ui.button('sell on ask', on_click=lambda: ui.notify('sell on ask was pressed')).style('width:9em;align-items:center;text-align:center;')


def update_elements():
    global r, thread_lock, bidbutton, askbutton
    thread_lock.acquire()
    bidbutton.set_text(r)
    askbutton.set_text(r)
    print('update_elements')
    print(r)
    thread_lock.release()

t = ui.timer(interval=1, callback=update_elements)

## Setup
ui.run(title='Featuremine orders', reload=False, show=False)
run = False
uithread.join()