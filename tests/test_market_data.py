import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import market_data as market


class QuoteTests(unittest.TestCase):
    def setUp(self):
        market._CACHE.clear()
        self.now = time.time()
        self.ticker = {'price':'1.25','bid':'1.24','ask':'1.26',
                       'time':datetime.fromtimestamp(self.now,timezone.utc).isoformat()}

    def tearDown(self):
        market._CACHE.clear()

    def test_coinbase_price_time_bid_ask_and_currency(self):
        with patch('market_data.read_json',return_value=self.ticker) as api:
            result=market.get_quote('XRP')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['provider'],'Coinbase Exchange')
        self.assertEqual(result['price'],1.25)
        self.assertEqual(result['currency'],'USD')
        self.assertEqual((result['bid'],result['ask']),(1.24,1.26))
        self.assertFalse(result['stale'])
        self.assertEqual(result['timingType'],'exchange')
        self.assertIn('/products/XRP-USD/ticker',api.call_args.args[0])

    def test_yahoo_never_claims_guaranteed_realtime(self):
        meta={'regularMarketPrice':2500,'regularMarketTime':self.now,'currency':'USD'}
        with patch('market_data.read_json',return_value={'chart':{'result':[{'meta':meta}]}}):
            result=market.get_quote('GOLD')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['timingType'],'reference')
        self.assertIsNone(result['delaySeconds'])
        self.assertIsNone(result['bid'])

    def test_reported_delay_and_outside_session(self):
        meta={'regularMarketPrice':25,'regularMarketTime':self.now-900,'currency':'USD','exchangeDataDelayedBy':10,
              'currentTradingPeriod':{'regular':{'start':self.now-86400,'end':self.now-3600}}}
        with patch('market_data.read_json',return_value={'chart':{'result':[{'meta':meta}]}}):
            result=market.get_quote('SILVER')
        self.assertEqual(result['delaySeconds'],600)
        self.assertEqual(result['marketState'],'outside_session')
        self.assertTrue(result['stale'])

    def test_stale_trade_is_marked(self):
        self.ticker['time']=datetime.fromtimestamp(self.now-300,timezone.utc).isoformat()
        with patch('market_data.read_json',return_value=self.ticker):
            result=market.get_quote('XLM')
        self.assertTrue(result['stale'])
        self.assertGreaterEqual(result['ageSeconds'],300)

    def test_cache_avoids_duplicate_calls_but_recalculates_age(self):
        with patch('market_data.read_json',return_value=self.ticker) as api:
            with patch('market_data.time.time',return_value=self.now):
                first=market.get_quote('XRP')
            with patch('market_data.time.time',return_value=self.now+180):
                second=market.get_quote('XRP')
        self.assertEqual(api.call_count,1)
        self.assertFalse(first['stale'])
        self.assertTrue(second['stale'])

    def test_failure_retains_only_explicitly_stale_last_price(self):
        with patch('market_data.read_json',return_value=self.ticker):
            first=market.get_quote('XRP')
        market._CACHE[('XRP','reference')]['savedAt']-=11
        with patch('market_data.read_json',side_effect=OSError('offline')):
            second=market.get_quote('XRP')
            cached=market.get_quote('XRP')
        self.assertEqual(second['status'],'error')
        self.assertEqual(second['lastQuote']['price'],first['price'])
        self.assertTrue(second['lastQuote']['stale'])
        self.assertEqual(cached['status'],'error')

    def test_invalid_values_and_future_timestamps_are_rejected(self):
        cases=[{'price':'nan'},{'price':'-1'},{'bid':'inf'},{'bid':'1.5'}, {'time':'invalid'},
               {'time':datetime.fromtimestamp(self.now+3600,timezone.utc).isoformat()}]
        for change in cases:
            market._CACHE.clear()
            with patch('market_data.read_json',return_value={**self.ticker,**change}):
                self.assertEqual(market.get_quote('XRP')['status'],'error')

    def test_partial_provider_failure_preserves_other_instruments(self):
        with (patch('market_data.fetch_coinbase',side_effect=OSError('crypto offline')),
             patch('market_data.fetch_yahoo_quote',return_value={'price':2000,'timestamp':self.now,'bid':None,'ask':None,
                   'provider':'Yahoo Finance','sourceSymbol':'GC=F','timingType':'reference','delaySeconds':None,'marketState':'unknown'})):
            result=market.get_quotes()
        self.assertEqual(len(result['quotes']),len(market.INSTRUMENTS))
        self.assertEqual([q['status'] for q in result['quotes']],['error' if i['kind']=='crypto' else 'ok' for i in market.INSTRUMENTS.values()])


if __name__ == '__main__':
    unittest.main()
