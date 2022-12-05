#!/usr/bin/env python3

import threading
import time
import random
from nicegui import ui

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
askprice = 123456789.123456
bidprice = 123456789.123456
ui.label('bid price')
bidbutton = ui.button(bidprice, on_click=lambda: ui.notify('bid price was pressed'))
ui.label('ask price')
askbutton = ui.button(askprice, on_click=lambda: ui.notify('ask price was pressed'))

def update_elements():
    global r, bidbutton, askbutton
    bidbutton.set_text(r)
    bidbutton.update()
    askbutton.set_text(r)
    askbutton.update()
    print('update_elements')
    print(r)

t = ui.timer(interval=1, callback=update_elements)

# Setup
ui.run(reload=False)
run = False
uithread.join()