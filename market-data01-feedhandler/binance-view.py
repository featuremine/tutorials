import argparse
from yamal import ytp
import numpy as np
import matplotlib.pyplot as plt
import json
import pandas as pd
from IPython.display import clear_output

sequence = ytp.sequence("mktdata.ytp")

#Create a peer object using the desired peer name with the help of your sequence object
peer = sequence.peer("reader")

#Create a channel object using the desired channel name with the help of your peer object
tq = []
bids = []
asks = []
tt = []
trades = []
fig = plt.figure()
ax = fig.add_subplot(1,1,1)

def redraw_plot():
    clear_output(wait=True)
    plt.plot(tq, bids, tq, asks)
    plt.scatter(tt, trades)
    plt.show()
    
def quote_update(peer, chan, tm, data):
    quote = json.loads(data)
    tq.append(pd.Timestamp(tm, unit='ns'))
    bids.append(quote["b"])
    asks.append(quote["a"])
    redraw_plot()
    
def trade_update(peer, chan, tm, data):
    price = json.loads(data)
    tt.append(pd.Timestamp(tm, unit='ns'))
    trades.append(price["p"])
    redraw_plot()

peer.channel(0, "btcusdt@bookTicker").data_callback(quote_update)
peer.channel(0, "btcusdt@trade").data_callback(trade_update)

while(True):
    sequence.poll()