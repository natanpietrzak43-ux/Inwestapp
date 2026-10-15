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
        for path in ('/api/news?instrument=BTC','/api/forecasts?instrument=BTC'):
            self.assertEqual(self.request(path)[0],400)
        example={'items':[],'sources':[],'notice':'test'}
        with patch('server.get_news',return_value=example):self.assertEqual(self.request('/api/news?instrument=XRP'),(200,example))

    def test_all_demo_routes(self):
        for key in ('XRP','XLM','SILVER','OIL','GOLD'):
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
        self.assertEqual(self.request('/api/analyze?instrument=BTC')[0],400)
        self.assertEqual(self.request('/api/analyze?mode=demo&risk=9')[0],400)
        self.assertEqual(self.request('/api/analyze?mode=demo&capital=nan')[0],400)

    def test_quote_route_and_invalid_instrument(self):
        example = {'quotes': [{'instrument':'XRP','status':'error','lastQuote':None,'error':'source failure'}], 'cacheSeconds':10}
        with patch('server.get_quotes',return_value=example) as source:
            status,result=self.request('/api/quotes?instrument=XRP')
            source.assert_called_once_with(['XRP'])
        self.assertEqual(status,200)
        self.assertEqual(result['quotes'],example['quotes'])
        self.assertEqual(result['alertEvents'],[])
        self.assertEqual(self.request('/api/quotes?instrument=BTC')[0],400)

    def test_catalog_defaults_and_empty_selection(self):
        status,catalog=self.request('/api/catalog')
        self.assertEqual(status,200)
        self.assertEqual(len(catalog['tools']),12)
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
