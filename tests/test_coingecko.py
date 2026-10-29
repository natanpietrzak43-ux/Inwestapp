import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit

import coingecko_data as cg
from instrument_catalog import CRYPTO
import market_data
import paper_bot
import secure_store
import user_data


def fixtures(now=None):
    now=time.time() if now is None else now
    rows=[{'id':identifier,'symbol':key.lower(),'current_price':2,'last_updated':datetime.fromtimestamp(now,timezone.utc).isoformat(),
           'market_cap':1000000000,'market_cap_rank':index+1,'total_volume':100000000,'price_change_percentage_24h':1,
           'price_change_percentage_7d_in_currency':2,'price_change_percentage_30d_in_currency':-3,
           'circulating_supply':500000000,'max_supply':None,'ath':4} for index,(key,identifier) in enumerate(cg.IDS.items())]
    return {'markets':rows,'global':{'data':{'updated_at':now,'total_market_cap':{'usd':2000000000000},
                        'total_volume':{'usd':100000000000},'market_cap_percentage':{'btc':55,'eth':15},'market_cap_change_percentage_24h_usd':2}},
            'trending':{'coins':[{'item':{'id':'unknown-token','name':'<script>not executed</script>','symbol':'TEST','market_cap_rank':None}}]}}


class CoinGeckoTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.directory.name,'COINGECKO_DEMO_API_KEY':'CG_TEST_NOT_A_REAL_KEY','COINGECKO_MONTHLY_BUDGET':'9000'})
        self.env.start();self.addCleanup(self.env.stop);self.addCleanup(self.directory.cleanup)
        self.now=time.time();self.data=fixtures(self.now)
        cg._CACHE.clear();cg._ATTEMPTS.clear();cg._IDENTITY=None;cg._COOLDOWN=0
        self.requests=[]

    def transport(self,request):
        self.requests.append(request)
        kind=next(k for k,path in cg.PATHS.items() if urlsplit(request.full_url).path.endswith(path))
        return copy.deepcopy(self.data[kind])

    def test_batch_all_ids_secret_only_in_header_and_no_execution_effect(self):
        before=paper_bot.status()['state']
        with patch('network_guard.read_json',side_effect=self.transport):r=cg.overview()
        self.assertEqual(len(self.requests),3);self.assertEqual(len(r['sections']['markets']['data']),16)
        self.assertEqual(set(cg.IDS),set(CRYPTO));self.assertEqual(r['currency'],'USD');self.assertTrue(r['readOnly'])
        for req in self.requests:
            self.assertEqual(urlsplit(req.full_url).hostname,'api.coingecko.com');self.assertNotIn('CG_TEST',req.full_url)
            self.assertEqual(dict((k.lower(),v) for k,v in req.header_items())['x-cg-demo-api-key'],'CG_TEST_NOT_A_REAL_KEY')
        params=parse_qs(urlsplit(self.requests[0].full_url).query)
        self.assertEqual(set(params['ids'][0].split(',')),set(cg.IDS.values()));self.assertEqual(params['vs_currency'],['usd'])
        self.assertEqual(paper_bot.status()['state'],before)

    def test_cache_and_distinct_context_ttls_do_not_spend_extra_requests(self):
        with patch('network_guard.read_json',side_effect=self.transport),patch('coingecko_data.time.time',return_value=self.now):
            first=cg.overview();second=cg.overview()
        self.assertEqual(len(self.requests),3);self.assertTrue(second['sections']['markets']['cached']);self.assertEqual(first['usage']['requests'],3)
        with patch('network_guard.read_json',side_effect=self.transport),patch('coingecko_data.time.time',return_value=self.now+61):r=cg.overview()
        self.assertEqual(len(self.requests),4);self.assertEqual(r['usage']['requests'],4)
        self.assertTrue(r['sections']['global']['cached']);self.assertTrue(r['sections']['trending']['cached'])

    def test_parallel_browser_requests_share_the_same_batches(self):
        from concurrent.futures import ThreadPoolExecutor
        with patch('network_guard.read_json',side_effect=self.transport):
            with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda _:cg.overview(),range(5)))
        self.assertEqual(len(self.requests),3);self.assertTrue(all(r['usage']['requests']==3 for r in results))

    def test_missing_key_is_reported_without_network_request(self):
        with patch.dict(os.environ,{'COINGECKO_DEMO_API_KEY':''}),patch('network_guard.read_json') as request:
            self.assertFalse(cg.status()['configured'])
            with self.assertRaisesRegex(ValueError,'Brak klucza'):cg.overview()
            request.assert_not_called()

    def test_private_store_and_key_rotation_never_export_credentials(self):
        with patch.dict(os.environ,{'COINGECKO_DEMO_API_KEY':''}):
            path=Path(self.directory.name)/'private'/'coingecko.json'
            secure_store.write(path,{'environment':'demo','key':'LOCAL_TEST_SECRET'})
            with patch('network_guard.read_json',side_effect=self.transport):cg.overview()
            self.assertTrue(cg.status()['configured'])
        with patch('network_guard.read_json',side_effect=self.transport):cg.overview()
        self.assertEqual(len(self.requests),6)
        output=json.dumps({'status':cg.status(),'export':user_data.export_data()})
        self.assertNotIn('LOCAL_TEST_SECRET',output);self.assertNotIn('CG_TEST_NOT_A_REAL_KEY',output)
        self.assertIn('coingecko_usage',user_data.export_data()['tables'])

    def test_header_injection_key_and_pro_configuration_are_rejected(self):
        with patch.dict(os.environ,{'COINGECKO_DEMO_API_KEY':'BAD\nInjected: value'}):
            with self.assertRaises(ValueError):cg.api_key()
        with patch.dict(os.environ,{'COINGECKO_DEMO_API_KEY':''}):
            secure_store.write(Path(self.directory.name)/'private'/'coingecko.json',{'environment':'pro','key':'TEST'})
            self.assertFalse(cg.status()['configured'])

    def test_network_outage_retains_old_prices_explicitly_stale(self):
        with patch('network_guard.read_json',side_effect=self.transport):cg.overview()
        with patch('network_guard.read_json',side_effect=OSError('secret transport details')),patch('coingecko_data.time.time',return_value=self.now+61):r=cg.overview()
        section=r['sections']['markets'];self.assertEqual(section['status'],'error');self.assertTrue(section['stale'])
        self.assertTrue(all(row['stale'] for row in section['data']));self.assertNotIn('secret transport details',json.dumps(r))

    def test_auth_failure_and_rate_limit_are_sanitized_and_cooled_down(self):
        for code in (401,403,429):
            cg._CACHE.clear();cg._ATTEMPTS.clear();cg._COOLDOWN=0
            error=urllib.error.HTTPError('https://api.coingecko.com/',code,'CG_TEST_NOT_A_REAL_KEY',{'Retry-After':'120'},io.BytesIO(b'CG_TEST_NOT_A_REAL_KEY'))
            with patch('network_guard.read_json',side_effect=error) as fetch:r=cg.overview()
            self.assertEqual(fetch.call_count,1);self.assertEqual(r['sections']['markets']['status'],'error')
            self.assertNotIn('CG_TEST_NOT_A_REAL_KEY',json.dumps(r))
            with patch('network_guard.read_json') as fetch:cg.overview()
            fetch.assert_not_called()

    def test_locally_enforced_monthly_budget_and_new_month(self):
        with patch.dict(os.environ,{'COINGECKO_MONTHLY_BUDGET':'100'}):
            cg.usage()
            with user_data.database() as conn:conn.execute('INSERT INTO coingecko_usage VALUES(?,?)',(cg.usage()['monthUTC'],100))
            with patch('network_guard.read_json') as fetch:r=cg.overview()
            fetch.assert_not_called();self.assertEqual(r['usage']['remaining'],0)
            self.assertIn('miesięczny limit',r['sections']['markets']['error'])
            with patch('coingecko_data.time.time',return_value=self.now+32*86400):self.assertEqual(cg.usage()['requests'],0)

    def test_per_minute_limit_and_bad_endpoint_do_not_contact_provider(self):
        with patch('network_guard.read_json',side_effect=self.transport):
            for _ in range(5):cg._fetch('markets',cg.api_key())
            with self.assertRaisesRegex(ValueError,'5 żądań'):cg._fetch('markets',cg.api_key())
        self.assertEqual(len(self.requests),5)
        with patch('network_guard.read_json') as fetch:
            with self.assertRaises(ValueError):cg._fetch('/account/withdraw',cg.api_key())
            fetch.assert_not_called()

    def test_missing_coin_is_not_replaced_by_another_asset(self):
        self.data['markets']=[row for row in self.data['markets'] if row['id']!='sui']
        with patch('network_guard.read_json',side_effect=self.transport):r=cg.overview()
        by={r['instrument']:r for r in r['sections']['markets']['data']}
        self.assertEqual(by['SUI']['status'],'error');self.assertNotIn('price',by['SUI']);self.assertEqual(by['BTC']['status'],'ok')

    def test_duplicate_and_foreign_ids_are_rejected(self):
        for extra in (self.data['markets'][0],{'id':'not-requested'}):
            with self.assertRaises(ValueError):cg.markets([*self.data['markets'],extra])

    def test_wrong_symbol_future_time_negative_and_nonfinite_price(self):
        for change in ({'symbol':'fake'},{'last_updated':datetime.fromtimestamp(self.now+600,timezone.utc).isoformat()},
                       {'current_price':-1},{'current_price':float('nan')},{'current_price':True},
                       {'ath':1e-308,'current_price':1e308}):
            rows=copy.deepcopy(self.data['markets']);rows[0].update(change)
            self.assertEqual(cg.markets(rows)[0]['status'],'error')

    def test_source_timestamp_determines_staleness_and_ath_is_only_arithmetic(self):
        self.data['markets'][0]['last_updated']=datetime.fromtimestamp(self.now-400,timezone.utc).isoformat()
        with patch('network_guard.read_json',side_effect=self.transport):r=cg.overview()
        row=r['sections']['markets']['data'][0]
        self.assertTrue(row['stale']);self.assertEqual(row['toAthPct'],100);self.assertEqual(row['distanceFromAthPct'],-50)
        self.assertIsNone(row['maxSupply']);self.assertNotIn('recommendation',row)

    def test_invalid_optional_context_does_not_remove_valid_market_prices(self):
        self.data['global']['data']['total_market_cap']['usd']='CG_TEST_NOT_A_REAL_KEY'
        with patch('network_guard.read_json',side_effect=self.transport):r=cg.overview()
        self.assertEqual(r['sections']['markets']['status'],'ok');self.assertEqual(r['sections']['global']['status'],'error')
        self.assertNotIn('CG_TEST_NOT_A_REAL_KEY',json.dumps(r));self.assertEqual(r['sections']['trending']['status'],'ok')

    def test_external_trending_text_stays_data_and_never_adds_instruments(self):
        with patch('network_guard.read_json',side_effect=self.transport):r=cg.overview()
        self.assertIn('<script>',r['sections']['trending']['data'][0]['name']);self.assertNotIn('unknown-token',CRYPTO)

    def test_execution_sources_do_not_accept_coingecko(self):
        with self.assertRaises(ValueError):paper_bot.configuration({'instrument':'BTC','source':'coingecko'})
        with self.assertRaises(ValueError):market_data.get_quote('BTC',source='coingecko')

    def test_invalid_budget_has_actionable_error(self):
        for value in ('not-a-number','0','-1','999999999'):
            with patch.dict(os.environ,{'COINGECKO_MONTHLY_BUDGET':value}),self.assertRaises(ValueError):cg.monthly_budget()


if __name__=='__main__':unittest.main()
