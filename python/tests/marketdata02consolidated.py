import unittest
from yamal import reactor, yamal
from os import remove
from multiprocessing import Process
from time import sleep
from datetime import datetime, timedelta
from collections import defaultdict

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
            proc.terminate()
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
            proc.terminate()
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

    def test_consolidation(self):
        print("test_consolidation")

        try:
            remove("test_consolidation.ytp")
        except OSError:
            pass

        parsercfg = {
            "parser" : {
                "module" : "feed",
                "component" : "feed-parser",
                "config" : {
                    "peer":"feed-parser",
                    "ytp-input":"test_consolidation.ytp",
                    "ytp-output":"test_consolidation.ytp"
                }
            }
        }

        parserproc = Process(target=run_reactor, kwargs={"cfg":parsercfg})
        parserproc.start()

        binance_securities = ["btcusdt","ethusdt"]
        kraken_securities = ["XBT/USD","ETH/USD"]

        cfg = {
            "binance" : {
                "module" : "feed",
                "component" : "binance-feed-handler",
                "config" : {
                    "peer":"binance-feed-handler",
                    "ytp-file":"test_consolidation.ytp",
                    "securities":binance_securities
                }
            },
            "binance-backup" : {
                "module" : "feed",
                "component" : "binance-feed-handler",
                "config" : {
                    "peer":"binance-feed-handler-backup",
                    "ytp-file":"test_consolidation.ytp",
                    "securities":binance_securities
                }
            },
            "kraken" : {
                "module" : "feed",
                "component" : "kraken-feed-handler",
                "config" : {
                    "peer":"kraken-feed-handler",
                    "ytp-file":"test_consolidation.ytp",
                    "securities":kraken_securities
                }
            },
            "kraken-backup" : {
                "module" : "feed",
                "component" : "kraken-feed-handler",
                "config" : {
                    "peer":"kraken-feed-handler-backup",
                    "ytp-file":"test_consolidation.ytp",
                    "securities":kraken_securities
                }
            }
        }

        proc = Process(target=run_reactor, kwargs={"cfg":cfg})
        proc.start()
        
        fname = "test_consolidation.ytp"

        y = yamal(fname, closable=False)
        dat = y.data()

        it = iter(dat)
        expected = [*[f"raw/binance/{sec}@trade" for sec in binance_securities],
                    *[f"raw/binance/{sec}@bookTicker" for sec in binance_securities],
                    *[f"raw/kraken/{sec}@trade" for sec in kraken_securities],
                    *[f"raw/kraken/{sec}@spread" for sec in kraken_securities]]

        timeout = timedelta(seconds=100)
        start = datetime.now()

        data = defaultdict(lambda:[])

        #Ensure we have data
        while expected:
            now = datetime.now()
            self.assertLess(now, start + timeout)
            for seq, ts, strm, msg in it:
                data[strm.channel, strm.peer].append((seq, ts, msg))
                if strm.channel in expected:
                    expected.remove(strm.channel)
                if not expected:
                    break
        
        print("terminating")

        if proc.is_alive():
            proc.terminate()
        proc.join()

        print("Consuming rest")

        #Consume rest

        #Validate all messages match

        start = datetime.now()

        done = False

        #Ensure we have data
        while not done:
            now = datetime.now()
            if now > start + timedelta(seconds=10):
                print(data)
            for seq, ts, strm, msg in it:
                data[strm.channel, strm.peer].append((seq, ts, msg))
            #validate if all data was parsed and consolidated

        if parserproc.is_alive():
            parserproc.terminate()
        parserproc.join()

if __name__ == '__main__':
    unittest.main()
