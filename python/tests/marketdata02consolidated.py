"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

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
            fname = "test_feed_handler_binance_unit.ytp"
            proc = None

            try:
                remove(fname)
            except OSError:
                pass

            securities = ["btcusdt","ethusdt"]

            cfg = {
                "binance" : {
                    "module" : "feed",
                    "component" : "binance-feed-handler",
                    "config" : {
                        "peer":"binance-feed-handler",
                        "ytp-file": fname,
                        "securities": securities,
                        "us-region": True
                    }
                }
            }

            proc = Process(target=run_reactor, kwargs={"cfg":cfg})
            proc.start()
            
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
                self.assertTrue(proc.is_alive())
                for seq, ts, strm, msg in it:
                    if strm.channel in expected:
                        expected.remove(strm.channel)
                    if not expected:
                        break

            if proc.is_alive():
                proc.terminate()
            proc.join()
        finally:
            if proc is not None:
                proc.terminate()
                proc.join()

    def test_feed_handler_kraken_unit(self):
        print("test_feed_handler_kraken_unit")

        try:
            fname = "test_feed_handler_kraken_unit.ytp"
            proc = None

            try:
                remove(fname)
            except OSError:
                pass

            securities = ["XBT/USD","ETH/USD"]

            cfg = {
                "kraken" : {
                    "module" : "feed",
                    "component" : "kraken-feed-handler",
                    "config" : {
                        "peer":"kraken-feed-handler",
                        "ytp-file": fname,
                        "securities": securities
                    }
                }
            }

            proc = Process(target=run_reactor, kwargs={"cfg":cfg})
            proc.start()
            
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
                self.assertTrue(proc.is_alive())
                for seq, ts, strm, msg in it:
                    if strm.channel in expected:
                        expected.remove(strm.channel)
                    if not expected:
                        break

            if proc.is_alive():
                proc.terminate()
            proc.join()
        finally:
            if proc is not None:
                proc.terminate()
                proc.join()

    def test_feed_handler_kraken_bad_symbology(self):
        print("test_feed_handler_kraken_bad_symbology")

        fname = "test_feed_handler_kraken_bad_symbology.ytp"

        try:
            remove(fname)
        except OSError:
            pass

        cfg = {
            "kraken" : {
                "module" : "feed",
                "component" : "kraken-feed-handler",
                "config" : {
                    "peer":"kraken-feed-handler",
                    "ytp-file": fname,
                    "securities":["bad","invalid"]
                }
            }
        }

        self.assertRaises(RuntimeError, run_reactor, cfg=cfg)

    def test_feed_parser(self):
        print("test_feed_parser")

        try:

            fname = "test_feed_parser.ytp"
            proc = None
            parserproc = None

            try:
                remove(fname)
            except OSError:
                pass

            y = yamal(fname, closable=False)

            parsercfg = {
                "parser" : {
                    "module" : "feed",
                    "component" : "feed-parser",
                    "config" : {
                        "peer":"feed-parser",
                        "ytp-input": fname,
                        "ytp-output": fname
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
                        "ytp-file": fname,
                        "securities":binance_securities,
                        "us-region": True
                    }
                },
                "binance-backup" : {
                    "module" : "feed",
                    "component" : "binance-feed-handler",
                    "config" : {
                        "peer":"binance-feed-handler-backup",
                        "ytp-file": fname,
                        "securities":binance_securities,
                        "us-region": True
                    }
                },
                "kraken" : {
                    "module" : "feed",
                    "component" : "kraken-feed-handler",
                    "config" : {
                        "peer":"kraken-feed-handler",
                        "ytp-file": fname,
                        "securities":kraken_securities
                    }
                },
                "kraken-backup" : {
                    "module" : "feed",
                    "component" : "kraken-feed-handler",
                    "config" : {
                        "peer":"kraken-feed-handler-backup",
                        "ytp-file": fname,
                        "securities":kraken_securities
                    }
                }
            }

            proc = Process(target=run_reactor, kwargs={"cfg":cfg})
            proc.start()
            
            dat = y.data()

            it = iter(dat)
            expected = [*[f"raw/binance/{sec}@trade" for sec in binance_securities],
                        *[f"raw/binance/{sec}@bookTicker" for sec in binance_securities],
                        *[f"raw/kraken/{sec}@trade" for sec in kraken_securities],
                        *[f"raw/kraken/{sec}@spread" for sec in kraken_securities]]

            timeout = timedelta(seconds=100)
            start = datetime.now()

            rawdata = defaultdict(lambda:[])
            oredata = defaultdict(lambda:[])

            #Ensure we have data
            while expected:
                now = datetime.now()
                self.assertLess(now, start + timeout)
                self.assertTrue(proc.is_alive())
                for seq, ts, strm, msg in it:
                    if strm.channel.startswith("raw"):
                        rawdata[strm.channel[3:]].append((seq, ts, strm.peer, msg))
                    else:
                        oredata[strm.channel[3:]].append((seq, ts, msg))
                    if strm.channel in expected:
                        expected.remove(strm.channel)
                    if not expected:
                        break
            
            if proc.is_alive():
                proc.terminate()
            proc.join()
            proc = None

            #Consume rest

            #Validate all messages match

            start = datetime.now()

            def validate_data():
                if len(rawdata) != 2 * len(binance_securities) + 2 * len(binance_securities):
                    return False
                if len(oredata) != len(binance_securities) + len(binance_securities):
                    return False
                return True

            #Wait until we can confirm proper functioning of parser
            while not validate_data():
                processed = False
                for seq, ts, strm, msg in it:
                    processed = True
                    self.assertLess(now, start + timeout)
                    self.assertTrue(parserproc.is_alive())
                    if strm.channel.startswith("raw"):
                        rawdata[strm.channel[3:]].append((seq, ts, strm.peer, msg))
                    else:
                        oredata[strm.channel[3:]].append((seq, ts, msg))
                if not processed:
                    now = datetime.now()

            if parserproc.is_alive():
                parserproc.terminate()
            parserproc.join()
            parserproc = None

            #Exhaust data
            for seq, ts, strm, msg in it:
                if strm.channel.startswith("raw"):
                    rawdata[strm.channel[3:]].append((seq, ts, strm.peer, msg))
                else:
                    oredata[strm.channel[3:]].append((seq, ts, msg))

            self.assertTrue(validate_data())

            parsercfg = {
                "parser" : {
                    "module" : "feed",
                    "component" : "feed-parser",
                    "config" : {
                        "peer":"feed-parser",
                        "ytp-input":"test_feed_parser.ytp",
                        "ytp-output":"test_feed_parser.ytp"
                    }
                }
            }

            parserproc = Process(target=run_reactor, kwargs={"cfg":parsercfg})
            parserproc.start()

            sleep(2)
            self.assertTrue(parserproc.is_alive())

            parserproc.terminate()
            parserproc.join()
            parserproc = None

            # No additional data has been produced by parser
            self.assertRaises(StopIteration, lambda: next(it))

        finally:
            if proc is not None:
                proc.terminate()
                proc.join()
            if parserproc is not None:
                parserproc.terminate()
                parserproc.join()


if __name__ == '__main__':
    unittest.main()
