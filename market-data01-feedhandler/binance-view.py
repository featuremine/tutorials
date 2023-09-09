import argparse
from yamal import ytp
import numpy as np
import matplotlib.pyplot as plt
import json
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
    tq = np.array([], dtype=np.datetime64)
    tt = np.array([], dtype=np.datetime64)
    bids = np.array([], dtype=np.float64)
    asks = np.array([], dtype=np.float64)
    trds = np.array([], dtype=np.float64)
    plt.ion()
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)

    def redraw_plot(delay):
        global tt, tq, trds, asks, bids
        ax.clear()
        now = np.datetime64('now')
        delta = np.timedelta64(5, 'm')
        cutoff = now - delta
        tti = np.argmax(tt > cutoff)
        tt = tt[tti:]
        trds = trds[tti:]
        tqi = np.argmax(tq > cutoff)
        if tqi > 1:
            tq = tq[tqi-1:]
            bids = bids[tqi-1:]
            asks = asks[tqi-1:]
            tq[0] = cutoff
        plt.scatter(tt, trds, c='b', marker='+')
        plt.plot(tq, bids, c='r')
        plt.plot(tq, asks, c='g')
        plt.show()
        fig.canvas.flush_events()
        plt.pause(delay)

    def trade_update(peer, chan, tm, data):
        global tt, trds
        price = json.loads(data)
        tt = np.append(tt, np.datetime64(tm, 'ns'))
        trds = np.append(trds, price["p"])

    def quote_update(peer, chan, tm, data):
        global tq, asks, bids
        price = json.loads(data)
        b = price["b"]
        a = price["a"]

        if len(bids) > 1 and bids[-1] == bids[-2] and bids[-1] == b and asks[-1] == asks[-2] and asks[-1] == a:
            tq[-1] = np.datetime64(tm, 'ns')
        else:
            tq = np.append(tq, np.datetime64(tm, 'ns'))
            bids = np.append(bids, b)
            asks = np.append(asks, a)

    peer.channel(0, f"{args.security}@trade").data_callback(trade_update)
    peer.channel(0, f"{args.security}@bookTicker").data_callback(quote_update)

    while(True):
        if not sequence.poll():
            redraw_plot(0.5)
