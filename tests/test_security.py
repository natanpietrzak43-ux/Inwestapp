import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch

import http_security
import instrument_catalog
from local_server import LocalHTTPServer
import network_guard
import release_integrity
from server import Handler, demo_bars
import okx_data
import paper_bot
import secure_store
import news_data


class BrowserBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        cls.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':cls.folder.name});cls.env.start()
        cls.server=LocalHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.token=http_security.state(cls.server).token

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.env.stop();cls.folder.cleanup()

    def request(self,path='/',method='GET',body=None,headers=None,token=False):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        h=dict(headers or {})
        if token:h['X-Inwestapp-Token']=self.token
        if isinstance(body,dict):h['Content-Type']='application/json';body=json.dumps(body)
        connection.request(method,path,body=body,headers=h)
        response=connection.getresponse();result=response.status,dict(response.getheaders()),response.read();connection.close();return result

    def test_every_response_has_browser_security_headers_and_no_python_banner(self):
        for path in ('/','/style.css','/api/health','/api/no-such-route','/../../private/okx-demo.json'):
            status,headers,body=self.request(path)
            self.assertEqual(headers['X-Frame-Options'],'DENY')
            self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
            self.assertNotIn('unsafe-eval',headers['Content-Security-Policy'])
            self.assertNotIn("script-src 'self' 'unsafe-inline'",headers['Content-Security-Policy'])
            self.assertEqual(headers['Referrer-Policy'],'no-referrer')
            self.assertNotIn('Python',headers['Server'])
            self.assertNotIn('Access-Control-Allow-Origin',headers)
            self.assertEqual(int(headers['Content-Length']),len(body))

    def test_foreign_origin_read_and_write_and_cross_port_are_blocked(self):
        for headers in ({'Origin':'https://evil.example'},{'Origin':'null'},
                        {'Origin':'http://127.0.0.1:9999'},{'Referer':'https://evil.example/anything'},
                        {'Sec-Fetch-Site':'cross-site'},{'Sec-Fetch-Site':'same-site'}):
            for path,method,body in (('/api/export','GET',None),('/api/bot/start','POST',{})):
                self.assertEqual(self.request(path,method,body,headers,token=True)[0],403)
        self.assertIsNone(paper_bot.status()['state'])

    def test_token_is_required_before_any_side_effect(self):
        for token in (None,'wrong-token'):
            headers={} if token is None else {'X-Inwestapp-Token':token}
            self.assertEqual(self.request('/api/alerts','POST',{'instrument':'SOL','price':150,'direction':'above'},headers)[0],403)
        self.assertEqual(json.loads(self.request('/api/alerts')[2])['alerts'],[])

    def test_legitimate_session_and_mutations_work(self):
        self.assertEqual(self.request('/api/session')[0],403)
        status,headers,raw=self.request('/api/session',headers={'X-Inwestapp-Client':'browser'})
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['csrfToken'],self.token)
        self.assertEqual(headers['Cache-Control'],'no-store');self.assertNotIn('Set-Cookie',headers)
        status,_,raw=self.request('/api/alerts','POST',{'instrument':'SOL','price':150,'direction':'above'},token=True)
        self.assertEqual(status,201)
        self.assertEqual(self.request('/api/alerts/'+json.loads(raw)['id'],'DELETE',{},token=True)[0],200)

    def test_server_restart_changes_token(self):
        other=LocalHTTPServer(('127.0.0.1',0),Handler)
        try:self.assertNotEqual(http_security.state(other).token,self.token)
        finally:other.server_close()

    def test_dns_rebinding_forged_host_and_wrong_port_are_rejected(self):
        for host in ('evil.example','127.0.0.1:9999','localhost.evil.example','127.0.0.1:'+str(self.server.server_port)+'@evil.example'):
            self.assertEqual(self.request('/api/export',headers={'Host':host})[0],403)

    def test_duplicate_headers_and_ambiguous_body_framing_are_rejected(self):
        for name,values in (('Host',['localhost:1','localhost:2']),('Content-Length',['2','3']),
                            ('Origin',['https://evil.example','https://evil.example'])):
            connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
            connection.putrequest('POST','/api/bot/start',skip_host=True)
            if name!='Host':connection.putheader('Host','127.0.0.1:'+str(self.server.server_port))
            connection.putheader('Content-Type','application/json');connection.putheader('X-Inwestapp-Token',self.token)
            for value in values:connection.putheader(name,value)
            connection.endheaders(b'{}');response=connection.getresponse()
            self.assertIn(response.status,(400,403));response.read();connection.close()
        self.assertEqual(self.request('/api/bot/start','POST','',{'Transfer-Encoding':'chunked'},token=True)[0],400)

    def test_size_json_type_duplicate_fields_and_nonfinite_numbers(self):
        headers={'Content-Type':'application/json'}
        for raw in ('{"risk":NaN}','{"risk":Infinity}','{"instrument":"BTC","instrument":"SOL"}','[]','\ud800'):
            payload=raw.encode('utf-8','surrogatepass')
            self.assertEqual(self.request('/api/bot/start','POST',payload,headers,token=True)[0],400)
        self.assertEqual(self.request('/api/bot/start','POST','x'*256_001,headers,token=True)[0],413)
        self.assertEqual(self.request('/api/bot/start','POST','{}',{'Content-Type':'text/plain'},token=True)[0],415)

    def test_concurrent_heavy_work_and_burst_are_bounded(self):
        state=http_security.state(self.server)
        state.heavy.acquire();state.heavy.acquire()
        try:
            status,headers,_=self.request('/api/analyze?mode=demo')
            self.assertEqual(status,429);self.assertEqual(headers['Retry-After'],'5')
        finally:state.heavy.release();state.heavy.release()
        state=http_security.State()
        with patch('http_security.time.monotonic',return_value=100):
            self.assertTrue(all(state.admit() for _ in range(160)));self.assertFalse(state.admit())
        with patch('http_security.time.monotonic',return_value=161):self.assertTrue(state.admit())

    def test_request_target_limit_and_unexpected_errors_never_leak_details(self):
        self.assertEqual(self.request('/api/health?'+('x'*4096))[0],400)
        with patch('server.user_data.export_data',side_effect=RuntimeError('SECRET-SHOULD-NOT-LEAK')):
            status,_,raw=self.request('/api/export')
        self.assertEqual(status,500);self.assertNotIn(b'SECRET',raw);self.assertNotIn(b'Traceback',raw)


class SupplyAndNetworkTests(unittest.TestCase):
    def test_network_rejects_untrusted_hosts_schemes_userinfo_ports_and_controls(self):
        for url in ('http://www.okx.com/','file:///etc/passwd','https://127.0.0.1/',
                    'https://169.254.169.254/latest/meta-data','https://www.okx.com.evil.example/',
                    'https://user:password@www.okx.com/','https://www.okx.com:444/',
                    'https://www.okx.com/\nsecret','https://www.okx.com/#fragment',
                    'https://www.okx.com\\@evil.example/'):
            with self.subTest(url=url),self.assertRaises(ValueError):network_guard.validate(url)
        self.assertEqual(network_guard.validate('https://www.okx.com/api/v5/public/time').hostname,'www.okx.com')

    def test_public_transport_never_follows_redirects_and_limits_response(self):
        handler=network_guard.NoRedirect()
        self.assertIsNone(handler.redirect_request(None,None,None,None,None,None))
        with patch('network_guard.urllib.request.build_opener') as build:
            network_guard.open_url('https://www.okx.com/api/v5/public/time')
        self.assertIsInstance(build.call_args.args[0],network_guard.NoRedirect)
        with patch('network_guard.open_url',return_value=io.BytesIO(b'x'*101)):
            with self.assertRaises(ValueError):network_guard.read('https://www.okx.com/',limit=100)
        with patch('network_guard.urllib.request.build_opener') as build:
            with self.assertRaises(ValueError):network_guard.open_url('https://evil.example/')
            build.assert_not_called()

    def test_webhook_cannot_target_loopback_or_metadata(self):
        for url in ('https://127.0.0.1/','https://169.254.169.254/','https://localhost/','https://x.internal/',
                    'https://10.0.0.1/','http://notify.example/','https://u:p@notify.example/'):
            with self.assertRaises(ValueError):network_guard.validate_webhook(url)
        network_guard.validate_webhook('https://notify.example/owner-token')

    def test_secret_write_does_not_follow_predictable_temp_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'private'/'keys.json';target.parent.mkdir()
            victim=root/'victim';victim.write_text('untouched')
            predictable=target.with_suffix('.tmp')
            try:predictable.symlink_to(victim)
            except OSError:self.skipTest('No symlink privilege on this platform')
            secure_store.write(target,{'apiKey':'test-value'})
            self.assertEqual(victim.read_text(),'untouched')
            self.assertEqual(secure_store.read(target),{'apiKey':'test-value'})

    def test_package_tamper_missing_manifest_and_extra_code_are_detected(self):
        manifest=json.loads((release_integrity.ROOT/release_integrity.MANIFEST).read_text())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in [release_integrity.MANIFEST,*manifest['files']]:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(release_integrity.ROOT/name,target)
            self.assertTrue(release_integrity.verify(root)['verified'])
            file=root/'web/security.js';original=file.read_bytes();file.write_bytes(original+b'\n// tampered')
            self.assertFalse(release_integrity.verify(root)['verified']);file.write_bytes(original)
            extra=root/'unreviewed.py';extra.write_text('raise RuntimeError("not imported")')
            self.assertIn('unreviewed.py',release_integrity.verify(root)['changedFiles']);extra.unlink()
            (root/release_integrity.MANIFEST).unlink();self.assertFalse(release_integrity.verify(root)['verified'])


class ExtendedInstrumentTests(unittest.TestCase):
    def test_all_crypto_contexts_candles_and_market_mappings_are_consistent(self):
        self.assertEqual(len(instrument_catalog.CRYPTO),16)
        self.assertEqual(set(okx_data.SYMBOLS),set(instrument_catalog.CRYPTO))
        for key in instrument_catalog.CRYPTO:
            cfg=paper_bot.configuration({'instrument':key,'source':'okx','market':'perpetual','engine':'agents'})
            self.assertEqual(cfg['currency'],'USDT');self.assertEqual(okx_data.symbol(key,'perpetual'),key+'-USDT-SWAP')
            rows=demo_bars(key,'15m');self.assertEqual(len(rows),900);self.assertGreater(rows[-1]['close'],0)
            self.assertIn(key,news_data.QUERIES)

    def test_browser_catalogue_matches_backend_without_execution(self):
        text=(release_integrity.ROOT/'web/instruments.js').read_text()
        payload=text.split('Object.freeze(',1)[1].rsplit(');',1)[0];items=json.loads(payload)
        self.assertEqual([i['id'] for i in items],list(instrument_catalog.INSTRUMENTS))
        for item in items:self.assertEqual(item['name'],instrument_catalog.INSTRUMENTS[item['id']]['name'])

    def test_news_filter_does_not_mix_new_assets_with_oil_or_ordinary_words(self):
        self.assertTrue(news_data.matches('SOL','Solana price rallies in crypto market'))
        self.assertTrue(news_data.matches('DOGE','Dogecoin token update'))
        self.assertFalse(news_data.matches('SOL','WTI oil production falls'))
        self.assertFalse(news_data.matches('DOT','Connect the dot in a drawing'))
        self.assertFalse(news_data.matches('NEAR','A nearby star is near Earth'))


if __name__=='__main__':unittest.main()
