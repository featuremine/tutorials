#!/usr/bin/env python3

import threading
import time
import random
from nicegui import ui

## Globals
run = True
r = 1

## Thread
def parallel_function():
    global r, run
    while run:
        r = random.uniform(1.000001, 123456789.99999)
        print('debug')
        print(r)        
        time.sleep(1)

uithread = threading.Thread(target=parallel_function)
uithread.start()

## UI  
ui.label('bid price')
bidbutton = ui.button(123456789.123456, on_click=lambda: ui.notify('bid price was pressed'))
ui.label('ask price')
askbutton = ui.button(123456789.123456, on_click=lambda: ui.notify('ask price was pressed'))

def update_elements():
    global r, bidbutton, askbutton
    bidbutton.set_text(r)
    askbutton.set_text(r)
    print('update_elements')
    print(r)

t = ui.timer(interval=1, callback=update_elements)

## Setup
ui.run(title='Featuremine orders', reload=False, show=False)
run = False
uithread.join()