import argparse
from yamal import ytp
import numpy as np
import matplotlib.pyplot as plt
import json

class TradePlotter:
    def __init__(self, n):
        self.tms = np.zeros(n, dtype='datetime64[ms]')
        self.tds = np.zeros((n,3), dtype=np.float64)
        self.bid = None
        self.ask = None
        self.idx = 0
        self.done = False

    def trade(self, tm, px):
        if self.bid is None or self.ask is None:
            return
        self.tms[self.idx] = tm
        self.tds[self.idx, 0] = px
        self.tds[self.idx, 1] = self.bid
        self.tds[self.idx, 2] = self.ask
        self.idx += 1
        self.done = self.idx == self.tms.shape[0]

    def quote(self, bid, ask):
        self.bid = bid
        self.ask = ask

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp-file", help="ytp file name", required=True)
    parser.add_argument("--security", help="security to display", required=True)
    parser.add_argument("--points", help="number of trades", type=int, required=True)
    args = parser.parse_args()

    sequence = ytp.sequence(args.ytp_file)

    #Create a peer object using the desired peer name with the help of your sequence object
    peer = sequence.peer("reader")

    plotter = TradePlotter(args.points)

    def draw_plot(tms, tds):
        fig = plt.figure()
        ax = fig.add_subplot(1,1,1)
        plt.scatter(tms, tds[:,0], c='b', marker='+')
        plt.plot(tms, tds[:,1], c='r')
        plt.plot(tms, tds[:,2], c='g')
        plt.show()

    def trade_plotter(plotter, data):
        ev = json.loads(data)
        plotter.trade(np.datetime64(ev['T'], 'ms'), ev['p'])
    def quote_plotter(plotter, data):
        ev = json.loads(data)
        plotter.quote(ev['b'], ev['a'])

    peer.channel(0, f"{args.security}@trade").data_callback(lambda peer, chan, tm, data: trade_plotter(plotter, data))
    peer.channel(0, f"{args.security}@bookTicker").data_callback(lambda peer, chan, tm, data: quote_plotter(plotter, data))

    while not plotter.done:
        sequence.poll()

    draw_plot(plotter.tms, plotter.tds)