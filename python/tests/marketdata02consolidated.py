import unittest

class TestMarketData02Consolidated(unittest.TestCase):

    def test_feed_handler_binance_unit(self):
        print("test_feed_handler_binance_unit")

    def test_feed_handler_binance_bad_symbology(self):
        print("test_feed_handler_binance_bad_symbologys")

    def test_feed_handler_kraken_unit(self):
        print("test_feed_handler_kraken_unit")

    def test_feed_handler_kraken_bad_symbology(self):
        print("test_feed_handler_kraken_bad_symbology")

    def test_feed_parser_unit(self):
        print("test_feed_parser_unit")

    def test_integration(self):
        print("test_integration")

if __name__ == '__main__':
    unittest.main()
