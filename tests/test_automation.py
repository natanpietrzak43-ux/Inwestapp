import copy
import hashlib
import hmac
import base64
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from decimal import Decimal

import contract_specs
import decision_engine
import demo_executor as demo
import execution_context
import okx_demo
import paper_bot
import runtime_ops
import secure_store
import shared_replay
import strategy_registry
import strategy_validation
from test_futures import fixture,quote,config
from server import demo_bars


def spec_row():
    return {'instId':'XLM-USDT-SWAP','ctType':'linear','ctValCcy':'XLM','settleCcy':'USDT','state':'live','ctVal':'100','ctMult':'1','lotSz':'.1','minSz':'.1','tickSz':'.01','maxMktSz':'1000','lever':'50'}
def tier_rows():return [{'instFamily':'XLM-USDT','minSz':'0','maxSz':'1000','mmr':'.005','maxLever':'20'}]


class Isolated(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.temp.name});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()


class SharedReplayTests(Isolated):
    def test_full_replay_drives_real_executor_without_changing_personal_state_or_environment(self):
        cfg=config();paper_bot.start(cfg);before=paper_bot.current_state();env=os.environ['INWESTAPP_DATA_DIR']
        a=fixture(time.time());rows=[{**r,'high':100.1,'low':99.9} for r in a['bars']];inds=[a['indicators'][0] for r in rows]
        with patch('shared_replay.indicators',return_value=inds),patch('decision_engine.evidence',return_value={'passed':True}):
            result=shared_replay.run(rows,cfg,spread_bps=0)
        self.assertTrue(result['historicalGuardReplayed']);self.assertEqual(result['metrics']['closedTrades'],1)
        trade=result['trades'][0];self.assertEqual(trade['signalCandle'],rows[219]['date']);self.assertGreater(trade['decisionAt'],0)
        self.assertGreater(trade['entryDate'],trade['signalCandle']);self.assertEqual(trade['reason'],'Koniec testu')
        self.assertAlmostEqual(result['metrics']['netPnl'],trade['pnl'])
        self.assertEqual(paper_bot.current_state(),before);self.assertEqual(os.environ['INWESTAPP_DATA_DIR'],env)
        self.assertIsNone(execution_context.root.get());self.assertIsNone(execution_context.clock.get())

    def test_causal_evidence_never_includes_later_epoch_candles(self):
        rows=demo_bars('XLM','1h');cfg=config();seen=[]
        def capture(rows_json,cfg_json):seen.extend(json.loads(rows_json));return {'passed':False}
        with patch('decision_engine._evidence',side_effect=capture):decision_engine.evidence(rows[:700],cfg)
        self.assertTrue(seen);self.assertLessEqual(seen[-1]['date'],rows[699]['date']);self.assertLess(len(seen),701)

    def test_context_storage_is_thread_local_and_released_after_errors(self):
        outcomes=[]
        def worker(index):
            with execution_context.replay(str(Path(self.temp.name)/str(index))):
                from user_data import data_dir
                outcomes.append((index,data_dir().name))
        threads=[threading.Thread(target=worker,args=(n,)) for n in (1,2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sorted(outcomes),[(1,'1'),(2,'2')]);self.assertIsNone(execution_context.root.get())


class ContractTests(unittest.TestCase):
    def test_balance_increase_cannot_exceed_the_approved_allocation_risk_ceiling(self):
        import leveraged_trading
        cfg=config(max_exposure=100)
        ordinary=leveraged_trading.plan(cfg,10000,10000,100,1,1)
        inflated=leveraged_trading.plan(cfg,1000000,1000000,100,1,1)
        self.assertEqual(ordinary['riskBudget'],inflated['riskBudget']);self.assertEqual(ordinary['units'],inflated['units'])
    def test_rounding_lots_ticks_and_stop_budget_preserves_cash_constraints(self):
        import leveraged_trading
        cfg=config();spec=contract_specs.parse(spec_row(),'XLM',tier_rows())
        for side in (1,-1):
            plan=leveraged_trading.plan(cfg,10000,10000,100.061,1,side)
            rounded=contract_specs.round_plan(plan,cfg,spec)
            self.assertEqual(Decimal(rounded['contracts'])%Decimal('.1'),0)
            self.assertEqual(Decimal(rounded['slTriggerPx'])%Decimal('.01'),0)
            self.assertLessEqual(rounded['estimatedStopLoss'],plan['riskBudget']+1e-8)
            self.assertLessEqual(rounded['units'],plan['units']);self.assertAlmostEqual(rounded['units'],float(Decimal(rounded['contracts'])*100))
    def test_invalid_contract_stale_spec_small_quantity_and_leverage_are_rejected(self):
        import leveraged_trading
        cfg=config();plan=leveraged_trading.plan(cfg,10000,10000,100,1,1)
        for change in ({'ctType':'inverse'},{'ctValCcy':'BTC'},{'settleCcy':'USD'},{'state':'suspend'}):
            with self.assertRaises(ValueError):contract_specs.parse({**spec_row(),**change},'XLM',tier_rows())
        spec=contract_specs.parse(spec_row(),'XLM',tier_rows())
        with self.assertRaises(ValueError):contract_specs.round_plan(plan,cfg,{**spec,'fetchedAt':time.time()-3601})
        with self.assertRaises(ValueError):contract_specs.round_plan({**plan,'units':.01},cfg,spec)
    def test_actual_funding_is_applied_once_and_future_settlement_is_not_used(self):
        import leveraged_trading as model
        cfg=config();p=model.plan(cfg,10000,10000,100,1,1,now=100)
        bundle={'funding':[{'timestamp':200,'rate':.001,'markPrice':101},{'timestamp':400,'rate':.5,'markPrice':999}]}
        with execution_context.replay('/tmp/unused-replay-context',bundle):
            model.funding(p,100,300,cfg);first=p['funding'];model.funding(p,100,301,cfg)
        self.assertAlmostEqual(first,p['units']*101*.001);self.assertEqual(p['funding'],first)


class TransportTests(Isolated):
    def test_demo_header_signature_path_and_body_are_exact_and_redirects_are_disabled(self):
        import urllib.request
        cfg=('synthetic-key','synthetic-secret','synthetic-passphrase');captured=[]
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        def request(req,timeout):captured.append(req);return Response(b'{"code":"0","data":[{"ordId":"test","sCode":"0"}]}')
        client=okx_demo.Client();client.offset=0;client.synced=time.monotonic()
        with patch('okx_demo.credentials',return_value=cfg),patch('okx_demo.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=request
            client.request('POST','/api/v5/trade/order',{'instId':'XLM-USDT-SWAP','sz':'1'})
        req=captured[0];headers={k.lower():v for k,v in req.header_items()}
        self.assertEqual(headers['x-simulated-trading'],'1');self.assertEqual(req.full_url,'https://www.okx.com/api/v5/trade/order')
        expected=base64.b64encode(hmac.new(cfg[1].encode(),(headers['ok-access-timestamp']+'POST/api/v5/trade/order').encode()+req.data,hashlib.sha256).digest()).decode()
        self.assertEqual(headers['ok-access-sign'],expected)
        with self.assertRaises(ValueError):client.request('POST','/api/v5/asset/withdrawal',{})
    def test_secret_store_is_private_and_not_in_export(self):
        import user_data
        path=Path(self.temp.name)/'private'/'okx-demo.json';secure_store.write(path,{'environment':'demo','key':'synthetic','secret':'hidden','passphrase':'test'})
        self.assertEqual(secure_store.read(path)['key'],'synthetic')
        if os.name!='nt':self.assertEqual(path.stat().st_mode&0o777,0o600)
        self.assertNotIn('synthetic',json.dumps(user_data.export_data()))


class OperationsTests(Isolated):
    def test_single_worker_lease_covers_different_http_ports_and_releases_on_close(self):
        first=runtime_ops.WorkerLease().acquire()
        try:
            with self.assertRaises(ValueError):runtime_ops.WorkerLease().acquire()
        finally:first.close()
        with runtime_ops.WorkerLease():pass
    def test_backup_integrity_and_offline_restore_preserves_previous_db(self):
        from tools.restore_backup import restore
        from user_data import database
        with database() as conn:conn.execute('CREATE TABLE witness(value INTEGER)');conn.execute('INSERT INTO witness VALUES(7)')
        backup=runtime_ops.backup();source=Path(self.temp.name)/'backups'/backup['file']
        with database() as conn:conn.execute('UPDATE witness SET value=9')
        self.assertFalse(restore(source)['applied'])
        with runtime_ops.WorkerLease():
            with self.assertRaises(ValueError):restore(source,True)
        self.assertTrue(restore(source,True)['applied'])
        with database() as conn:self.assertEqual(conn.execute('SELECT value FROM witness').fetchone()[0],7)
        self.assertTrue(list((Path(self.temp.name)/'backups').glob('before-restore-*.sqlite3')))
    def test_stale_heartbeat_and_unconfigured_notification_are_explicit(self):
        for name in ('paper-worker','demo-worker','supervisor'):runtime_ops.heartbeat(name,{'status':'running'})
        self.assertTrue(runtime_ops.status()['healthy'])
        from user_data import database
        with database() as conn:conn.execute('UPDATE runtime_heartbeats SET updated=?',(time.time()-100,))
        self.assertFalse(runtime_ops.status()['healthy']);runtime_ops.event('test','no secrets');runtime_ops.notify_pending()
        self.assertFalse(runtime_ops.status()['notificationConfigured'])
    def test_smtp_confirmation_updates_delivery_and_failures_do_not_expose_password(self):
        import notification_channel
        cfg={'host':'smtp.example.com','port':465,'username':'owner@example.com','password':'synthetic-private-password','sender':'owner@example.com','recipient':'owner@example.com'}
        secure_store.write(Path(self.temp.name)/'private'/'alerts.json',cfg)
        runtime_ops.event('test-mail','Operational message')
        with patch('notification_channel.smtplib.SMTP_SSL') as smtp:
            runtime_ops.notify_pending();smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        self.assertTrue(runtime_ops.status()['notificationConfigured']);self.assertEqual(runtime_ops.status()['events'][0]['delivered'],1)
        runtime_ops.event('test-mail-failure','Retry remains durable')
        with patch('notification_channel.smtplib.SMTP_SSL',side_effect=OSError(cfg['password'])):
            with self.assertRaises(ValueError) as error:runtime_ops.notify_pending()
        self.assertNotIn(cfg['password'],str(error.exception))
        self.assertTrue(any(e['delivered']==0 for e in runtime_ops.status()['events']))
        with self.assertRaises(ValueError):notification_channel.validate({**cfg,'recipient':'owner@example.com\nBcc: other@example.com'})


class RegistryTests(Isolated):
    def test_negative_validation_changed_parameters_or_code_cannot_be_approved(self):
        cfg=config();v=strategy_registry.register(cfg)
        bad=strategy_registry.save_validation({'fingerprint':v['fingerprint'],'eligible':False})
        with self.assertRaises(ValueError):strategy_registry.approve(v['id'],bad['id'],True)
        good=strategy_registry.save_validation({'fingerprint':v['fingerprint'],'eligible':True})
        with self.assertRaises(ValueError):strategy_registry.approve(v['id'],good['id'],False)
        strategy_registry.approve(v['id'],good['id'],True)
        self.assertTrue(strategy_registry.get(v['id'],True)['approved'])
        with patch('decision_engine.fingerprint',return_value='changed'):
            with self.assertRaises(ValueError):strategy_registry.get(v['id'],True)
        strategy_registry.revoke(v['id'])
        with self.assertRaises(ValueError):strategy_registry.get(v['id'],True)
    def test_hot_code_changes_require_restart_before_creating_an_approval(self):
        with patch('decision_engine.source_hash',return_value='different-source'):
            with self.assertRaises(ValueError):strategy_registry.register(config())


class FakeExchange:
    def __init__(self):self.remote={};self.positions=[];self.algos=[];self.posts=[];self.timeout=False;self.accept=True;self.partial=False;self.protection_fail=False
    def request(self,method,path,params=None):
        params=params or {}
        if method=='POST':self.posts.append((path,copy.deepcopy(params)))
        if path.endswith('/account/config'):return [{'posMode':'net_mode','perm':'read_only,trade','uid':'test-demo-user'}]
        if path.endswith('/account/balance'):return [{'details':[{'ccy':'USDT','eq':'10000','availBal':'10000'}]}]
        if path.endswith('/account/positions'):return copy.deepcopy(self.positions)
        if path.endswith('/orders-pending'):return [r for r in self.remote.values() if r['state'] in ('live','partially_filled')]
        if path.endswith('/orders-algo-pending'):return copy.deepcopy(self.algos)
        if path.endswith('/public/instruments'):return [spec_row()]
        if path.endswith('/market/ticker'):return [{'instId':'XLM-USDT-SWAP','last':'100','bidPx':'99.99','askPx':'100.01','ts':str(int(time.time()*1000))}]
        if path.endswith('/public/mark-price'):return [{'instId':'XLM-USDT-SWAP','markPx':'100','ts':str(int(time.time()*1000))}]
        if path.endswith('/public/position-tiers'):return tier_rows()
        if path.endswith('/trade-fee'):return [{'taker':'-.0005'}]
        if path.endswith('/set-leverage'):return [{}]
        if path.endswith('/trade/fills'):return [{'ordId':params['ordId'],'tradeId':'fill-'+params['ordId'],'fee':'-.01','feeCcy':'USDT'}]
        if path.endswith('/cancel-order'):
            self.remote[params['clOrdId']]['state']='canceled';return [{'sCode':'0'}]
        if path.endswith('/cancel-algos'):self.algos=[];return [{'sCode':'0'}]
        if path.endswith('/order-algo'):
            if self.protection_fail:raise okx_demo.ApiError('test-rejection')
            self.algos=[{**params,'algoId':'algo-test'}];return [{'algoId':'algo-test'}]
        if path.endswith('/trade/order') and method=='GET':
            if params['clOrdId'] not in self.remote:raise okx_demo.ApiError('51603')
            return [copy.deepcopy(self.remote[params['clOrdId']])]
        if path.endswith('/trade/order') and method=='POST':
            if self.accept:
                size=Decimal(params['sz'])/(2 if self.partial and not params.get('reduceOnly') else 1)
                row={'clOrdId':params['clOrdId'],'ordId':'o'+str(len(self.remote)),'state':'partially_filled' if self.partial and not params.get('reduceOnly') else 'filled','accFillSz':str(size),'avgPx':'100','instId':params['instId']}
                self.remote[params['clOrdId']]=row
                if params.get('reduceOnly'):self.positions=[]
                else:
                    self.positions=[{'instId':params['instId'],'pos':str(size if params['side']=='buy' else -size),'mgnMode':'isolated','posSide':'net','avgPx':'100','margin':'100'}]
            if self.timeout:raise okx_demo.UnknownOutcome('synthetic timeout')
            return [{'ordId':row['ordId'],'sCode':'0'}]
        raise AssertionError((method,path))


class DemoExecutionTests(Isolated):
    def setUp(self):
        super().setUp();self.cfg=config();v=strategy_registry.register(self.cfg)
        validation=strategy_registry.save_validation({'fingerprint':v['fingerprint'],'eligible':True});strategy_registry.approve(v['id'],validation['id'],True)
        with patch('okx_demo.configured',return_value=True):demo.start(v['id'])
        self.exchange=FakeExchange();self.executor=demo.Executor(self.exchange);self.now=time.time();self.a=fixture(self.now);self.q=quote(self.now)
    def pulse(self):self.executor.pulse(self.a,self.q)
    def order_posts(self):return [p for path,p in self.exchange.posts if path=='/api/v5/trade/order']
    def test_unknown_accepted_entry_is_reconciled_and_never_duplicated_after_restart(self):
        self.exchange.timeout=True;self.pulse();self.assertEqual(demo.orders()[0]['state'],'unknown');self.assertEqual(len(self.order_posts()),1)
        self.exchange.timeout=False;demo.Executor(self.exchange).pulse(self.a,self.q)
        self.assertEqual(len(self.order_posts()),1);self.assertTrue(demo.load()['protectionConfirmed']);self.assertFalse(demo.load()['active'])
    def test_unknown_unaccepted_entry_is_never_blindly_resubmitted(self):
        self.exchange.timeout=True;self.exchange.accept=False;self.pulse();self.pulse()
        self.assertEqual(len(self.order_posts()),1);self.assertEqual(demo.orders()[0]['state'],'unknown');self.assertEqual(demo.load()['halted'],'uncertain')
    def test_partial_fill_cancels_remainder_protects_actual_size_and_deduplicates_fills(self):
        self.exchange.partial=True;self.pulse();self.pulse();self.pulse()
        cancel=[p for path,p in self.exchange.posts if path.endswith('/cancel-order')];self.assertEqual(len(cancel),1)
        self.assertTrue(demo.load()['protectionConfirmed']);self.assertEqual(Decimal(self.exchange.algos[0]['sz']),abs(Decimal(self.exchange.positions[0]['pos'])))
        self.assertEqual(len(demo.status()['fills']),1)
    def test_protection_rejection_closes_reduce_only_and_halts_entries(self):
        self.exchange.protection_fail=True;self.pulse();self.pulse()
        closes=[p for p in self.order_posts() if p.get('reduceOnly')];self.assertEqual(len(closes),1)
        self.assertEqual(closes[0]['side'],'sell');self.assertFalse(demo.load()['active']);self.assertEqual(self.exchange.positions,[])
        self.assertEqual(demo.status()['environment'],'demo')
    def test_unmanaged_position_is_quarantined_and_never_closed(self):
        self.exchange.positions=[{'instId':'BTC-USDT-SWAP','pos':'1','mgnMode':'isolated','posSide':'net'}]
        self.pulse();self.assertFalse(demo.load()['active']);self.assertEqual(self.order_posts(),[])
    def test_unmanaged_algo_without_client_id_is_never_canceled(self):
        self.exchange.algos=[{'instId':'BTC-USDT-SWAP','algoId':'manual-algo'}]
        self.pulse();self.assertFalse(demo.load()['active'])
        self.assertFalse(any(path.endswith('/cancel-algos') for path,_ in self.exchange.posts))
    def test_ack_alone_does_not_confirm_protection_and_shutdown_keeps_native_orders(self):
        self.pulse();self.pulse();self.assertTrue(demo.load()['protectionConfirmed']);algos=copy.deepcopy(self.exchange.algos)
        demo.stop();self.assertEqual(self.exchange.algos,algos);self.assertFalse(demo.load()['active'])
