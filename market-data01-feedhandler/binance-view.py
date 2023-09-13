import argparse
from yamal import ytp
import numpy as np
import matplotlib.pyplot as plt
import json

class TradePlotter:
    def __init__(self, n):
        self.tms = np.zeros(n, dtype='datetime64[ms]')
        self.tds = np.zeros((n,5), dtype=np.float64)
        self.bid = None
        self.ask = None
        self.idx = 0
        self.done = False
    def times(self):
        return self.tms
    def trade(self, tm, px, qt, isbid):
        if self.bid is None or self.ask is None:
            return
        self.tms[self.idx] = tm
        self.tds[self.idx, 0] = self.bid
        self.tds[self.idx, 1] = self.ask
        self.tds[self.idx, 2] = px
        self.tds[self.idx, 3] = qt
        self.tds[self.idx, 4] = isbid
        self.idx += 1
        self.done = self.idx == self.tms.shape[0]
    def bids(self):
        return self.tds[:,0]
    def asks(self):
        return self.tds[:,1]
    def bid_trades(self):
        sel = self.tds[:,4] == True
        return self.tms[sel], self.tds[sel,2], self.tds[sel,3]
    def ask_trades(self):
        sel = self.tds[:,4] == False
        return self.tms[sel], self.tds[sel,2], self.tds[sel,3]
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

    def draw_plot(data):
        fig = plt.figure()
        ax = fig.add_subplot(1,1,1)
        plt.title("Trades with Corresponding Best Bid and Offer")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Price")
        bts, bpx, bqt = data.bid_trades()
        ats, apx, aqt = data.ask_trades()
        plt.scatter(bts, bpx, marker='^', sizes=bqt*1000.0, c='g')
        plt.scatter(ats, apx, marker='v', sizes=aqt*1000.0, c='r')
        plt.plot(data.times(), data.bids(), c='g', linewidth = '2')
        plt.plot(data.times(), data.asks(), c='r', linewidth = '2')
        plt.grid()
        plt.show()

    def trade_plotter(plotter, data):
        ev = json.loads(data)
        plotter.trade(np.datetime64(ev['T'], 'ms'), ev['p'], ev['q'], ev['m'])
    def quote_plotter(plotter, data):
        ev = json.loads(data)
        plotter.quote(ev['b'], ev['a'])

    peer.channel(0, f"{args.security}@trade").data_callback(lambda peer, chan, tm, data: trade_plotter(plotter, data))
    peer.channel(0, f"{args.security}@bookTicker").data_callback(lambda peer, chan, tm, data: quote_plotter(plotter, data))

    while not plotter.done:
        sequence.poll()

    draw_plot(plotter)