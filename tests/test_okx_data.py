import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import market_data
import okx_data as okx
from timeframes import TIMEFRAMES


class OKXTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.cache=patch.object(okx,'CACHE_DIR',Path(self.temp.name));self.cache.start()
        self.now=time.time();market_data._CACHE.clear()
    def tearDown(self):self.cache.stop();self.temp.cleanup();market_data._CACHE.clear()
    def rows(self,count=230,tf='1h'):
        step=TIMEFRAMES[tf]['seconds'];end=int(self.now//step)*step
        return [[str((end-(i+1)*step)*1000),'100','102','98','101','123','12300','12300','1'] for i in range(count)]
    def ticker(self,**changes):return dict({'instId':'XLM-USDT','last':'0.25','bidPx':'0.2499','askPx':'0.2501','ts':str(int(self.now*1000))},**changes)
    def test_okx_quote_keeps_usdt_and_never_overwrites_usd_cache(self):
        with patch('okx_data.request',return_value=[self.ticker()]),patch('market_data.fetch_coinbase',return_value={'provider':'Coinbase Exchange','sourceSymbol':'XLM-USD','price':.26,'timestamp':self.now,'bid':.25,'ask':.27,'timingType':'exchange'}):
            usd=market_data.get_quote('XLM');usdt=market_data.get_quote('XLM','okx')
            self.assertEqual((usd['currency'],usd['price']),('USD',.26));self.assertEqual((usdt['currency'],usdt['provider']),('USDT','OKX'))
            self.assertEqual(usdt['sourceSymbol'],'XLM-USDT');self.assertEqual(market_data.get_quote('XLM')['price'],.26)
    def test_invalid_ticker_pair_price_spread_and_time_fail_closed(self):
        for changes in [{'instId':'XRP-USDT'},{'last':'nan'},{'bidPx':'1'},{'ts':str(int((self.now-130)*1000))},{'ts':str(int((self.now+10)*1000))}]:
            with self.subTest(changes=changes),patch('okx_data.request',return_value=[self.ticker(**changes)]),self.assertRaises(ValueError):okx.ticker('XLM')
    def test_all_native_intervals_utc_and_base_volume(self):
        for tf in TIMEFRAMES:
            rows=self.rows(tf=tf)
            with patch('okx_data.request',side_effect=[rows[:100],rows[100:200],rows[200:]]) as call,patch('okx_data.time.sleep'):
                result,_=okx.candles('XLM',tf)
            self.assertEqual(len(result),230);self.assertEqual(result[0]['volume'],123);self.assertLess(result[0]['date'],result[-1]['date'])
            self.assertEqual(call.call_args_list[0].args[1]['bar'],okx.BARS[tf])
            self.assertEqual('T' in result[0]['date'],tf!='1d')
            self.assertEqual(call.call_args_list[1].args[1]['after'],rows[99][0])
    def test_open_candle_is_omitted_and_incremental_refresh_retains_history(self):
        rows=self.rows();open_row=list(rows[0]);open_row[0]=str(int(self.now//3600)*3600*1000);open_row[8]='0'
        with patch('okx_data.request',side_effect=[[open_row,*rows[:99]],rows[99:199],rows[199:]]),patch('okx_data.time.sleep'):
            first,_=okx.candles('BTC')
        self.assertEqual(len(first),230)
        path=Path(self.temp.name)/'BTC-USDT-1h.json';cache=json.loads(path.read_text());cache['savedAt']-=31;path.write_text(json.dumps(cache))
        with patch('okx_data.request',return_value=rows[:3]) as call:
            second,_=okx.candles('BTC')
        self.assertEqual(first,second);self.assertEqual(call.call_count,1)
    def test_cached_history_is_not_returned_as_live_on_provider_failure(self):
        rows=self.rows()
        with patch('okx_data.request',side_effect=[rows[:100],rows[100:200],rows[200:]]),patch('okx_data.time.sleep'):okx.candles('ETH')
        path=Path(self.temp.name)/'ETH-USDT-1h.json';cache=json.loads(path.read_text());cache['savedAt']-=31;path.write_text(json.dumps(cache))
        with patch('okx_data.request',side_effect=OSError('offline')),self.assertRaises(OSError):okx.candles('ETH')
    def test_non_progressing_pages_and_bad_ohlc_are_rejected(self):
        rows=self.rows()
        with patch('okx_data.request',return_value=rows[:100]),patch('okx_data.time.sleep'),self.assertRaises(ValueError):okx.candles('XRP')
        rows[0][2]='90'
        with patch('okx_data.request',return_value=rows[:100]),self.assertRaises(ValueError):okx.candles('XRP')
    def test_source_failure_never_falls_back_to_coinbase(self):
        with patch('okx_data.ticker',side_effect=OSError()),patch('market_data.fetch_coinbase') as fallback:
            q=market_data.get_quote('XLM','okx')
        self.assertEqual(q['status'],'error');fallback.assert_not_called()
    def test_unsupported_instrument_is_rejected(self):
        with self.assertRaises(ValueError):okx.candles('GOLD')
