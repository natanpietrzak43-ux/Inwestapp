import csv
import io
import json
import threading
import tempfile
import os
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from server import Handler, demo_bars


class QuietHandler(Handler):
    def log_message(self, *_):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage=tempfile.TemporaryDirectory()
        cls.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':cls.storage.name})
        cls.env.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1',0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.env.stop()
        cls.storage.cleanup()

    def request(self, path, body=None):
        req = urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,json.load(exc)

    def test_release_and_versioned_assets_are_available_without_cache(self):
        from app_release import APP_VERSION,FEATURES
        status,health=self.request('/api/health');self.assertEqual(status,200);self.assertEqual(health['version'],APP_VERSION);self.assertEqual(health['features'],FEATURES)
        for path in ('/startup.js','/chart.js','/education.js','/app.js'):
            with urllib.request.urlopen(self.base+path+'?v='+APP_VERSION) as r:
                self.assertEqual(r.status,200);self.assertIn('javascript',r.headers['Content-Type']);self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertGreater(len(r.read()),100)
        with urllib.request.urlopen(self.base+'/') as r:
            html=r.read().decode();self.assertIn('data-ui-version="'+APP_VERSION+'"',html);self.assertIn('id="update-status"',html)

    def test_historical_bot_report_is_persistent_and_does_not_change_paper_state(self):
        before=self.request('/api/bot')[1]['state']
        status,report=self.request('/api/bot/backtest',{'mode':'demo','market':'perpetual','source':'okx','engine':'agents','instrument':'XLM','leverage':3})
        self.assertEqual(status,200);self.assertTrue(report['demo']);self.assertEqual(report['market'],'perpetual');self.assertEqual(report['currency'],'USDT')
        self.assertGreater(report['bars'],0);self.assertEqual(len(report['equity']),report['bars']);self.assertFalse(report['historicalGuardReplayed'])
        self.assertEqual(self.request('/api/bot')[1]['state'],before)
        summaries=self.request('/api/bot/backtests')[1]['records'];self.assertTrue(any(r['id']==report['id'] for r in summaries));self.assertNotIn('equity',summaries[0])
        self.assertEqual(self.request('/api/bot/backtests?id='+report['id'])[1],report)
        self.assertEqual(self.request('/api/bot/backtests?id=missing')[0],404)
        exported=self.request('/api/export')[1]['tables'];self.assertTrue(any(r['id']==report['id'] for r in exported['bot_backtests']))

    def test_futures_history_uses_only_contract_series_and_failure_never_falls_back(self):
        body={'market':'perpetual','source':'okx','engine':'agents','instrument':'BTC','leverage':2}
        with patch('server.okx_data.candles',return_value=(demo_bars('BTC','1h'),'test')) as fetch,patch('server.fetch_bars') as fallback:
            status,report=self.request('/api/bot/backtest',body)
        self.assertEqual(status,200);fetch.assert_called_once_with('BTC','1h','perpetual');fallback.assert_not_called()
        with patch('server.okx_data.candles',side_effect=OSError('offline')),patch('server.fetch_bars') as fallback:
            self.assertEqual(self.request('/api/bot/backtest',body)[0],502)
        fallback.assert_not_called()
        self.assertEqual(self.request('/api/bot/backtest',{**body,'mode':'csv','csv':'date,open'})[0],400)

    def test_source_import_keeps_instrument_context_and_inert_code(self):
        original=urllib.request.urlopen
        def transport(request,*args,**kwargs):
            if getattr(request,'full_url','').startswith('https://raw.githubusercontent.com/'):
                return io.BytesIO(b'print("must not execute")\n# <script>alert(1)</script>')
            return original(request,*args,**kwargs)
        with patch('strategy_sources.urllib.request.urlopen',side_effect=transport):
            status,record=self.request('/api/strategies/source',{'template':'strategy001','instrument':'ETH','timeframe':'4h','market':'perpetual'})
        self.assertEqual(status,200);self.assertFalse(record['verified']);self.assertEqual(record['context']['instrument'],'ETH')
        self.assertFalse(record['context']['suitabilityVerified']);self.assertEqual(len(record['sha256']),64);self.assertEqual(record['license'],'GPL-3.0')
        self.assertIn('<script>',record['content']['code']);self.assertEqual(len(self.request('/api/strategies/sources')[1]['templates']),3)
        self.assertEqual(self.request('/api/strategies/source',{'template':'../../private','instrument':'ETH'})[0],400)
        self.assertEqual(self.request('/api/strategies/source',{'template':'strategy001','instrument':'GOLD','market':'perpetual'})[0],400)

    def test_csv_bot_replay_keeps_usd_and_requires_matching_import_context(self):
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['date','open','high','low','close','volume']);writer.writeheader();writer.writerows(demo_bars('XRP','1h')[:230])
        body={'mode':'csv','instrument':'XRP','timeframe':'1h','source':'okx','market':'spot','csv':stream.getvalue(),'csv_instrument':'XRP','csv_timeframe':'1h'}
        status,report=self.request('/api/bot/backtest',body)
        self.assertEqual(status,200);self.assertEqual(report['currency'],'USD');self.assertEqual(report['source'],'csv');self.assertEqual(report['config']['source'],'reference')
        self.assertEqual(self.request('/api/bot/backtest',{**body,'csv_instrument':'BTC'})[0],400)

    def test_all_timeframes_in_http_keep_timestamps(self):
        for tf in ('15m','30m','1h','2h','4h','1d'):
            status,r=self.request('/api/analyze?mode=demo&timeframe='+tf)
            self.assertEqual(status,200)
            self.assertEqual(r['timeframe'],tf)
            self.assertEqual('T' in r['bars'][0]['date'],tf!='1d')
            self.assertIn('availableDays',r['history'])

    def test_persistent_crud_and_loopback_security(self):
        status,alert=self.request('/api/alerts',{'instrument':'XLM','direction':'above','price':999})
        self.assertEqual(status,201)
        self.assertTrue(any(a['id']==alert['id'] for a in self.request('/api/alerts')[1]['alerts']))
        for method,path,body,headers,expected in [
            ('POST','/api/alerts',{}, {'Origin':'https://evil.example','Content-Type':'application/json'},403),
            ('POST','/api/alerts',{}, {'Content-Type':'text/plain'},415),
            ('GET','/api/export',None,{'Host':'evil.example'},403),
            ('DELETE','/api/alerts/'+alert['id'],{}, {'Content-Type':'application/json'},200)]:
            req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers)
            try:
                with urllib.request.urlopen(req) as r:code=r.status
            except urllib.error.HTTPError as exc:code=exc.code
            self.assertEqual(code,expected)
        self.assertFalse(any(a['id']==alert['id'] for a in self.request('/api/alerts')[1]['alerts']))

    def test_news_and_forecast_routes_reject_invalid_instrument(self):
        for path in ('/api/news?instrument=DOGE','/api/forecasts?instrument=DOGE'):
            self.assertEqual(self.request(path)[0],400)
        example={'items':[],'sources':[],'notice':'test'}
        with patch('server.get_news',return_value=example):self.assertEqual(self.request('/api/news?instrument=XRP'),(200,example))

    def test_paper_bot_api_never_accepts_real_mode(self):
        self.assertEqual(self.request('/api/bot/start',{'mode':'live'})[0],400)
        status,r=self.request('/api/bot/start',{'instrument':'ETH','mode':'paper'})
        self.assertEqual(status,200);self.assertEqual(r['mode'],'paper');self.assertTrue(r['state']['active'])
        self.assertFalse(self.request('/api/bot/stop',{})[1]['state']['active'])

    def test_lab_demo_and_missing_live_data_are_distinct(self):
        status,r=self.request('/api/strategies/test',{'mode':'demo','instrument':'BTC','timeframe':'1h'})
        self.assertEqual(status,200);self.assertTrue(r['demo']);self.assertEqual(len(r['rows']),5)
        with patch('server.fetch_bars',side_effect=OSError()):self.assertEqual(self.request('/api/strategies/test',{'mode':'live'})[0],502)

    def test_mcp_status_has_no_secret_or_fake_connection(self):
        with patch('server.trader_mcp.status',return_value={'configured':True,'connected':False,'error':'blocked','tools':[]}):
            status,r=self.request('/api/mcp/status');self.assertEqual(status,200);self.assertFalse(r['connected']);self.assertNotIn('key',r)

    def test_all_demo_routes(self):
        for key in ('XRP','XLM','BTC','ETH','SILVER','OIL','GOLD'):
            status,result=self.request('/api/analyze?mode=demo&instrument='+key)
            self.assertEqual(status,200)
            self.assertEqual(result['decision']['action'],'WAIT')
            self.assertEqual(result['instrument']['id'],key)

    def test_provider_failure_never_uses_demo(self):
        with patch('server.fetch_bars',side_effect=OSError('upstream unavailable')):
            status,result=self.request('/api/analyze?mode=live')
        self.assertEqual(status,502)
        self.assertNotIn('bars',result)

    def test_live_response_with_stubbed_provider(self):
        # Contract test only: this is not evidence of real provider connectivity.
        with patch('server.fetch_bars',return_value=(demo_bars('XRP','1h'),'test-fetch-time')):
            status,result=self.request('/api/analyze?mode=live')
        self.assertEqual(status,200)
        self.assertEqual(result['mode'],'live')
        self.assertEqual(result['fetchedAt'],'test-fetch-time')

    def test_csv_import_and_invalid_body(self):
        file=io.StringIO()
        writer=csv.DictWriter(file,fieldnames=['date','open','high','low','close','volume'])
        writer.writeheader()
        writer.writerows(demo_bars('XRP'))
        status,result=self.request('/api/import',{'instrument':'XRP','csv':file.getvalue()})
        self.assertEqual(status,200)
        self.assertEqual(result['mode'],'csv')
        for body in ([],{'csv':None},{'instrument':'UNKNOWN','csv':'x'},{'instrument':'XRP','csv':'bad-columns'}):
            self.assertEqual(self.request('/api/import',body)[0],400)

    def test_invalid_parameters_and_instrument(self):
        self.assertEqual(self.request('/api/analyze?instrument=DOGE')[0],400)
        self.assertEqual(self.request('/api/analyze?mode=demo&risk=9')[0],400)
        self.assertEqual(self.request('/api/analyze?mode=demo&capital=nan')[0],400)

    def test_okx_analysis_routes_preserve_currency_and_fail_explicitly(self):
        with patch('server.fetch_bars',return_value=(demo_bars('BTC','1h'),'fixture')) as provider:
            status,result=self.request('/api/analyze?mode=okx&instrument=BTC')
            self.assertEqual(status,200);self.assertEqual(result['currency'],'USDT');self.assertEqual(result['provider'],'OKX')
            provider.assert_called_once_with('BTC','1h','okx')
        self.assertEqual(self.request('/api/analyze?mode=okx&instrument=GOLD')[0],400)
        with patch('server.fetch_bars',side_effect=OSError()):
            status,result=self.request('/api/analyze?mode=okx');self.assertEqual(status,502);self.assertNotIn('bars',result)
        self.assertEqual(self.request('/api/quotes?source=unknown')[0],400)

    def test_usdt_quotes_cannot_trigger_existing_usd_alerts(self):
        self.request('/api/alerts',{'instrument':'BTC','direction':'above','price':50})
        usdt={'instrument':'BTC','currency':'USDT','price':100,'status':'ok'}
        usd={'instrument':'BTC','currency':'USD','price':40,'status':'ok'}
        with patch('server.get_quotes',side_effect=[{'quotes':[usdt]},{'quotes':[usd]}]) as source:
            status,result=self.request('/api/quotes?source=okx&instrument=BTC')
        self.assertEqual(status,200);self.assertEqual(result['alertEvents'],[])
        self.assertEqual(source.call_args_list[1].args[0],['BTC'])

    def test_quote_route_and_invalid_instrument(self):
        example = {'quotes': [{'instrument':'XRP','status':'error','lastQuote':None,'error':'source failure'}], 'cacheSeconds':10}
        with patch('server.get_quotes',return_value=example) as source:
            status,result=self.request('/api/quotes?instrument=XRP')
            source.assert_called_once_with(['XRP'])
        self.assertEqual(status,200)
        self.assertEqual(result['quotes'],example['quotes'])
        self.assertEqual(result['alertEvents'],[])
        self.assertEqual(self.request('/api/quotes?instrument=DOGE')[0],400)

    def test_catalog_defaults_and_empty_selection(self):
        status,catalog=self.request('/api/catalog')
        self.assertEqual(status,200)
        self.assertEqual(len(catalog['tools']),14)
        status,result=self.request('/api/analyze?mode=demo&tools=')
        self.assertEqual(status,200)
        self.assertEqual(result['timeframe'],'1h')
        self.assertEqual(result['selectedTools'],[])
        self.assertTrue(result['decision']['missingGroups'])
        self.assertEqual(result['decision']['action'],'WAIT')

    def test_hourly_import_and_explicit_selected_tools(self):
        file=io.StringIO();writer=csv.DictWriter(file,fieldnames=['date','open','high','low','close','volume'])
        writer.writeheader();writer.writerows(demo_bars('XRP','1h'))
        status,result=self.request('/api/import',{'instrument':'XRP','csv':file.getvalue(),'timeframe':'1h','tools':['bollinger','stochastic','adx','obv'],'strategy':'range'})
        self.assertEqual(status,200)
        self.assertEqual(result['strategy'],'range')
        self.assertEqual(result['selectedTools'],['bollinger','stochastic','adx','obv'])
        self.assertEqual(result['timeframe'],'1h')

    def test_invalid_timeframe_tools_and_strategy(self):
        for suffix in ('timeframe=7d','tools=not-an-indicator','strategy=unknown'):
            self.assertEqual(self.request('/api/analyze?mode=demo&'+suffix)[0],400)


if __name__ == '__main__':
    unittest.main()
