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
    tt = []
    trades = []
    plt.ion()
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    count = 0

    def redraw_plot():
        clear_output(wait=True)
        plt.scatter(tt, trades, c='b', marker='+')
        plt.show()
        plt.pause(0.1)

    def trade_update(peer, chan, tm, data):
        global count
        price = json.loads(data)
        tt.append(pd.Timestamp(tm, unit='ns'))
        trades.append(price["p"])

    peer.channel(0, f"{args.security}@trade").data_callback(trade_update)

    while(True):
        if not sequence.poll():
            redraw_plot()
        else:
            count += 1
            if count % 10000 == 0:
                redraw_plot()
