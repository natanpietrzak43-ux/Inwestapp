import csv
import io
import json
import threading
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
        cls.server = ThreadingHTTPServer(('127.0.0.1',0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None):
        req = urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,json.load(exc)

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
        with patch('server.fetch_bars',return_value=(demo_bars('XRP'),'test-fetch-time')):
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
        self.assertEqual(result,example)
        self.assertEqual(self.request('/api/quotes?instrument=BTC')[0],400)


if __name__ == '__main__':
    unittest.main()
