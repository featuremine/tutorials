import unittest
from yamal import reactor, yamal
from os import remove
from multiprocessing import Process
from time import sleep
from datetime import datetime, timedelta

def run_reactor(cfg):
    r = reactor()
    r.deploy(cfg)
    r.run(live=True)

class TestMarketData02Consolidated(unittest.TestCase):

    def test_feed_handler_binance_unit(self):
        print("test_feed_handler_binance_unit")

        try:
            remove("test_feed_handler_binance_unit.ytp")
        except OSError:
            pass

        securities = ["btcusdt","ethusdt"]

        cfg = {
            "binance" : {
                "module" : "feed",
                "component" : "binance-feed-handler",
                "config" : {
                    "peer":"binance-feed-handler",
                    "ytp-file":"test_feed_handler_binance_unit.ytp",
                    "securities":securities
                }
            }
        }

        proc = Process(target=run_reactor, kwargs={"cfg":cfg})
        proc.start()
        
        fname = "test_feed_handler_binance_unit.ytp"

        y = yamal(fname, closable=False)
        dat = y.data()

        it = iter(dat)
        expected = [*[f"raw/binance/{sec}@trade" for sec in securities],
                    *[f"raw/binance/{sec}@bookTicker" for sec in securities]]

        timeout = timedelta(seconds=100)
        start = datetime.now()

        while expected:
            now = datetime.now()
            self.assertLess(now, start + timeout)
            for seq, ts, strm, msg in it:
                if strm.channel in expected:
                    expected.remove(strm.channel)
                if not expected:
                    break

        if proc.is_alive():
            proc.kill()
        proc.join()

    def test_feed_handler_kraken_unit(self):
        print("test_feed_handler_kraken_unit")

        try:
            remove("test_feed_handler_kraken_unit.ytp")
        except OSError:
            pass

        securities = ["XBT/USD","ETH/USD"]

        cfg = {
            "kraken" : {
                "module" : "feed",
                "component" : "kraken-feed-handler",
                "config" : {
                    "peer":"kraken-feed-handler",
                    "ytp-file":"test_feed_handler_kraken_unit.ytp",
                    "securities":securities
                }
            }
        }

        proc = Process(target=run_reactor, kwargs={"cfg":cfg})
        proc.start()
        
        fname = "test_feed_handler_kraken_unit.ytp"

        y = yamal(fname, closable=False)
        dat = y.data()

        it = iter(dat)
        expected = [*[f"raw/kraken/{sec}@trade" for sec in securities],
                    *[f"raw/kraken/{sec}@spread" for sec in securities]]

        timeout = timedelta(seconds=100)
        start = datetime.now()

        while expected:
            now = datetime.now()
            self.assertLess(now, start + timeout)
            for seq, ts, strm, msg in it:
                if strm.channel in expected:
                    expected.remove(strm.channel)
                if not expected:
                    break

        if proc.is_alive():
            proc.kill()
        proc.join()

    def test_feed_handler_kraken_bad_symbology(self):
        print("test_feed_handler_kraken_bad_symbology")

        try:
            remove("test_feed_handler_kraken_bad_symbology.ytp")
        except OSError:
            pass

        cfg = {
            "kraken" : {
                "module" : "feed",
                "component" : "kraken-feed-handler",
                "config" : {
                    "peer":"kraken-feed-handler",
                    "ytp-file":"test_feed_handler_kraken_bad_symbology.ytp",
                    "securities":["bad","invalid"]
                }
            }
        }

        self.assertRaises(RuntimeError, run_reactor, cfg=cfg)

    def test_feed_parser_unit(self):
        print("test_feed_parser_unit")

    def test_integration(self):
        print("test_integration")

if __name__ == '__main__':
    unittest.main()
