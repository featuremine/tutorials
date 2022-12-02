#!/usr/bin/env python3

import threading
import time
from nicegui import ui

run = True

askprice = 123456789.123456
bidprice = 123456789.123456
def parallel_function():
   while run:
       time.sleep(0.1)


uithread = threading.Thread(target=parallel_function)
uithread.start()
    
ui.label('bid price')
ui.button(bidprice, on_click=lambda: ui.notify('bid price was pressed'))
ui.label('ask price')
ui.button(askprice, on_click=lambda: ui.notify('ask price was pressed'))
ui.run()
run = False
uithread.join()