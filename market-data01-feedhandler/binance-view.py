import argparse
from yamal import ytp
import numpy as np
import matplotlib.pyplot as plt
import json
import pandas as pd
from IPython.display import clear_output

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp-file", help="ytp file name", required=True)
    parser.add_argument("--security", help="security to display", required=True)
    args = parser.parse_args()

    sequence = ytp.sequence(args.ytp_file)

    #Create a peer object using the desired peer name with the help of your sequence object
    peer = sequence.peer("reader")

    #Create a channel object using the desired channel name with the help of your peer object
    tq = []
    bids = []
    asks = []
    tt = []
    trades = []
    plt.ion()
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)

    def redraw_plot():
        #clear_output(wait=True)
        plt.plot(tq, bids, 'g-')
        plt.plot(tq, asks, 'r-')
        plt.scatter(tt, trades, c='b', marker='+')
        plt.show()
        plt.pause(0.01)
        
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

    peer.channel(0, f"{args.security}@bookTicker").data_callback(quote_update)
    peer.channel(0, f"{args.security}@trade").data_callback(trade_update)

    while(True):
        sequence.poll()