import argparse
import extractor
from yamal import ytp
from datetime import timedelta


def print_trades(x):
    print(x)

def print_bbos(x):
    print(x)


def setup_prod_sip(universe, symbology, markets, lvls, graph, ytpfile):
    op = graph.features
    seq = ytp.sequence(ytpfile, readonly=True)
    peer = seq.peer("feed_handler")
    op.ytp_sequence(seq, timedelta(milliseconds=1))
    for imnt in universe.get("all"):
        ticker = symbology.info(imnt)["ticker"]
        bbos_book = []
        trades = []
        cum_trades = []
        statuses = []
        for mkt in markets:
            ch = peer.channel(1000, f"ore/imnts/{mkt}/{ticker}")  # E.G. "ore/imnts/coinbase/BTC-USD"
            bookupd = op.ore_ytp_decode(ch)
            decoded = op.decode_data(bookupd)
            bbo_book = op.book_build(decoded, lvls)

            book_receive = op.decode_receive(bookupd)
            bbo_receive = op.asof(book_receive, bbo_book)

            bidqty_int32 = op.convert(op.round(bbo_book.bid_shr_0), extractor.Int32)
            askqty_int32 = op.convert(op.round(bbo_book.ask_shr_0), extractor.Int32)
            bbo_book_combined = op.combine(
                bbo_book, (
                    ("bid_prx_0", "bidprice"),
                    ("ask_prx_0", "askprice")
                ),
                bidqty_int32, (("bid_shr_0", "bidqty"),),
                askqty_int32, (("ask_shr_0", "askqty"),),
                bbo_receive, (("time", "receive"),)
            )
            graph.callback(bbo_book_combined, print_bbos)

            trade = op.book_trades(decoded)  # change
            trade_receive = op.asof(book_receive, trade)

            bid, ask, unk = op.split(trade.decoration, 'decoration', ('b', 'a', 'u'))
            bid_val = op.constant(bid, ('side', extractor.Int32, 0))
            ask_val = op.constant(ask, ('side', extractor.Int32, 1))
            unk_val = op.constant(unk, ('side', extractor.Int32, 2))
            side = op.join(
                bid_val, ask_val, unk_val, 'decoration', extractor.Array(
                    extractor.Char, 1), ('b', 'a', 'u')).side

            qty_decimal64 = op.round(trade.qty)
            qty_int32 = op.convert(qty_decimal64, extractor.Int32)

            trade_combined = op.combine(
                trade, (("trade_price", "price"),),
                qty_int32, (("qty", "qty"),),
                trade_receive, (("time", "receive"),),
                side, (("side", "side"),)
            )
            graph.callback(trade_combined, print_trades)



class Universe:
    def __init__(self, universe_keys):
        self.universe_keys = universe_keys

    def get(self, name):
        if name != "all":
            raise LookupError("unknown universe name")
        return self.universe_keys


class Symbology:
    def __init__(self, symb_table):
        self.imnts = symb_table

    def info(self, id):
        return self.imnts[id]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ytp", help="YTP file", required=True)
    parser.add_argument("--markets", help="Comma separated markets list", required=True)
    parser.add_argument("--imnts", help="Comma separated instrument list", required=True)
    parser.add_argument("--levels", help="Number of levels to display", type=int, required=False, default=1)
    parser.add_argument(
        "--license",
        help="Extractor license (defaults to '../test/test.lic' if not provided)",
        required=False,
        default="../test/test.lic")
    args = parser.parse_args()

    extractor.set_license(args.license)
    graph = extractor.system.comp_graph()
    op = graph.features

    # E.G.
    # symb_table = {
    #     1: {"ticker": "ADA-USD"},
    #     2: {"ticker": "BTC-USD"},
    #     3: {"ticker": "ETH-BTC"},
    # }
    symb_table = {}
    i = 1
    for imnt in args.imnts.split(','):
        symb_table[i] = {"ticker": imnt}
        i += 1
    symbology = Symbology(symb_table)
    universe = Universe(symb_table.keys())

    # E.G.
    # markets = [
    #     "coinbase",
    #     "binance"
    # ]
    markets = args.markets.split(',')

    setup_prod_sip(universe, symbology, markets, args.levels, graph, args.ytp)

    graph.stream_ctx().run_live()
