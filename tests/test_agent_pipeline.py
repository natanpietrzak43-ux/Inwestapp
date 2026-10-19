import copy
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

import agent_pipeline
import paper_bot as bot
import user_data


def fixture(now):
    end=int(now//3600)*3600
    rows=[{'date':datetime.fromtimestamp(end-(230-i)*3600,timezone.utc).isoformat(),'open':100,'high':101,'low':99,'close':100,'volume':1000} for i in range(230)]
    ind={'ema20':99,'ema50':98,'ema200':97,'rsi':60,'atr':1,'adx':25,'obv':2000,'obvEma':1000,'obvPrevious':1500,'hasVolume':True,'bbMid':99,'bbLower':95,'bbUpper':105}
    return {'mode':'live','source':'okx','currency':'USDT','instrument':{'id':'XLM'},'timeframe':'1h','bars':rows,'indicators':[ind],
            'lastDate':rows[-1]['date'],'fetchedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),'stale':False,'historyGuard':{'passed':True}}


def quote(now,price=100,spread=.02):
    return {'instrument':'XLM','status':'ok','currency':'USDT','source':'okx','provider':'OKX','sourceSymbol':'XLM-USDT',
            'price':price,'bid':price-spread/2,'ask':price+spread/2,'timestamp':now,'asOf':datetime.fromtimestamp(now,timezone.utc).isoformat()}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.temp.name});self.env.start();self.now=time.time()
        self.cfg={'instrument':'XLM','timeframe':'1h','source':'okx','engine':'agents','capital':10000,'risk':1,'costs':10,'slippage':5,'daily_loss':3,'max_exposure':25}
        bot.start(self.cfg);self.run=bot.current_state()['run_id'];self.a=fixture(self.now);self.q=quote(self.now)
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def evaluate(self,a=None,q=None):return agent_pipeline.evaluate(a or self.a,q or self.q,bot.current_state()['config'],bot.current_state(),self.now)
    def buy(self):
        bot.advance(self.run,self.q,self.a,now=self.now)
        bot.advance(self.run,quote(self.now+1),self.a,now=self.now+1)
        return bot.current_state()['position']
    def test_full_path_and_independent_risk_approval(self):
        r=self.evaluate();self.assertEqual(r['action'],'BUY');self.assertEqual([s['id'] for s in r['stages']],['data','quality','trend','momentum','volume','regime','context','supervisor','risk'])
        self.assertEqual(r['stages'][-2]['status'],'BUY');self.assertEqual(r['stages'][-1]['status'],'approved')
        self.assertLessEqual(r['plan']['notional'],2500);self.assertLessEqual(r['plan']['estimatedStopLoss'],100)
    def test_supervisor_cannot_overrule_spread_veto(self):
        r=self.evaluate(q=quote(self.now,spread=2));self.assertEqual(r['stages'][-2]['status'],'BUY');self.assertEqual(r['action'],'WAIT');self.assertIn('Spread',r['reason']);self.assertIsNone(r['plan'])
    def test_incompatible_currency_pair_and_missing_market_data_block(self):
        for q in [{**self.q,'currency':'USD'},{**self.q,'sourceSymbol':'XRP-USDT'},{**self.q,'status':'error'},{**self.q,'bid':float('nan')},{**self.q,'timestamp':self.now-121},{**self.q,'bid':200,'ask':200.01}]:
            with self.subTest(q=q):self.assertEqual(self.evaluate(q=q)['action'],'WAIT')
    def test_quality_checks_gaps_future_candles_and_source_identity(self):
        cases=[]
        for changes in [{'source':'reference'},{'currency':'USD'},{'mode':'demo'},{'mode':'csv'},{'instrument':{'id':'BTC'}},{'timeframe':'4h'},{'historyGuard':{'passed':False}}]:
            cases.append({**self.a,**changes})
        gap=copy.deepcopy(self.a);gap['bars'].pop(50);cases.append(gap)
        old=copy.deepcopy(self.a);old['bars']=old['bars'][:-2];old['lastDate']=old['bars'][-1]['date'];cases.append(old)
        future=copy.deepcopy(self.a);future['bars'][-1]['date']=datetime.fromtimestamp(self.now+3600,timezone.utc).isoformat();cases.append(future)
        for a in cases:
            with self.subTest(changes=a.get('source')):self.assertEqual(self.evaluate(a=a)['action'],'WAIT')
    def test_latest_closed_candle_is_valid_late_in_current_hour(self):
        later=int(self.now//3600)*3600+3500
        a=fixture(later);q=quote(later)
        self.assertEqual(agent_pipeline.evaluate(a,q,bot.current_state()['config'],bot.current_state(),later)['stages'][1]['status'],'passed')
    def test_disagreement_yields_wait_without_extra_indicator_votes(self):
        a=copy.deepcopy(self.a);a['indicators'][-1]['rsi']=40
        r=self.evaluate(a=a);self.assertEqual(r['action'],'WAIT');self.assertEqual(len([s for s in r['stages'] if s['id']=='momentum']),1)
    def test_paper_entry_uses_later_ask_plus_slippage_and_records_audit(self):
        bot.advance(self.run,self.q,self.a,now=self.now);self.assertIsNone(bot.current_state()['position'])
        bot.advance(self.run,quote(self.now-1),self.a,now=self.now+1);self.assertIsNone(bot.current_state()['position'])
        p=self.buy();self.assertIsNotNone(p);self.assertAlmostEqual(p['entry'],100.01*1.0005)
        self.assertLessEqual(p['notional'],2500);self.assertIsNotNone(p['entryCycle']);self.assertEqual(p['entryAudit']['execution']['action'],'BUY')
        self.assertIn('agent_cycles',user_data.export_data()['tables']);self.assertEqual(user_data.journal()['summary']['closed'],0)
    def test_pending_entry_is_cancelled_if_data_or_risk_deteriorates(self):
        for bad in ['spread','analysis']:
            bot.start(self.cfg);self.run=bot.current_state()['run_id'];bot.advance(self.run,self.q,self.a,now=self.now)
            self.assertIsNotNone(bot.current_state()['pending'])
            q=quote(self.now+1,spread=2) if bad=='spread' else quote(self.now+1)
            bot.advance(self.run,q,None if bad=='analysis' else self.a,now=self.now+1)
            self.assertIsNone(bot.current_state()['position']);self.assertIsNone(bot.current_state()['pending']);self.assertEqual(bot.cycles()[0]['action'],'WAIT')
    def test_concurrent_cycles_cannot_duplicate_entry(self):
        bot.advance(self.run,self.q,self.a,now=self.now)
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:bot.advance(self.run,quote(self.now+1),self.a,now=self.now+1),range(4)))
        self.assertEqual(len([e for e in bot.status()['events'] if e['kind']=='buy']),1)
    def test_stop_executes_bid_after_fees_even_without_analysis(self):
        p=self.buy();bot.stop();bot.advance(self.run,quote(self.now+2,price=95),None,now=self.now+2)
        trade=bot.status()['trades'][0];expected=p['units']*94.99*.9995*.999-p['notional']-p['entryFee']
        self.assertAlmostEqual(trade['pnl'],expected);self.assertEqual(trade['currency'],'USDT');self.assertEqual(trade['exitAudit']['execution']['action'],'SELL')
        self.assertIsNotNone(trade['entryAudit']);self.assertFalse(bot.current_state()['active'])
    def test_manual_close_works_without_candle_analysis(self):
        self.buy()
        with patch('paper_bot.time.time',return_value=self.now+2):bot.close_position()
        bot.advance(self.run,quote(self.now+3),None,now=self.now+3)
        self.assertIsNone(bot.current_state()['position']);self.assertEqual(bot.status()['trades'][0]['reason'],'Zamknięcie na żądanie użytkownika')
    def test_daily_loss_halts_and_cannot_be_reset_by_start(self):
        bot.start({**self.cfg,'daily_loss':.1});self.run=bot.current_state()['run_id'];self.buy()
        bot.advance(self.run,quote(self.now+2,price=95),self.a,now=self.now+2)
        self.assertEqual(bot.current_state()['riskHalted'],'daily');self.assertFalse(bot.current_state()['active'])
        with self.assertRaises(ValueError):bot.start({**self.cfg,'daily_loss':.1})
    def test_drawdown_halts_and_cannot_be_reset_by_start(self):
        bot.start({**self.cfg,'max_drawdown':1,'daily_loss':20});self.run=bot.current_state()['run_id'];self.buy()
        bot.advance(self.run,quote(self.now+2,price=90),self.a,now=self.now+2)
        self.assertEqual(bot.current_state()['riskHalted'],'drawdown')
        with self.assertRaises(ValueError):bot.start({**self.cfg,'max_drawdown':1,'daily_loss':20})
    def test_currency_switch_does_not_relabel_historical_account(self):
        self.buy();bot.advance(self.run,quote(self.now+2,price=95),now=self.now+2)
        with self.assertRaises(ValueError):bot.start({**self.cfg,'source':'reference'})
    def test_existing_config_migrates_as_classic_without_changing_cash(self):
        with bot.storage(True) as conn:
            s=bot._read(conn);s['config']={k:s['config'][k] for k in ('instrument','timeframe','preset','capital','risk','costs','slippage','daily_loss')};s['cash']=12345;bot._save(conn,s)
        migrated=bot.current_state();self.assertEqual(migrated['config']['engine'],'classic');self.assertEqual(migrated['config']['source'],'reference');self.assertEqual(migrated['cash'],12345)

    def test_archived_accounts_preserve_results_and_new_currency_is_separate(self):
        self.buy();bot.advance(self.run,quote(self.now+2,price=95),now=self.now+2);bot.stop()
        old=bot.current_state();self.assertGreater(old['tradeCount'],0)
        result=bot.start({**self.cfg,'source':'reference'},new_account=True)
        self.assertNotEqual(result['state']['accountId'],old['accountId']);self.assertEqual(result['state']['config']['currency'],'USD')
        self.assertEqual(result['trades'],[]);self.assertEqual(result['state']['cash'],10000);self.assertEqual(result['archives'][0]['realized'],old['realized'])
        exported=user_data.export_data()['tables'];self.assertEqual(len(exported['paper_accounts']),1);self.assertEqual(len(exported['paper_trades']),1)
    def test_new_account_requires_stopped_and_flat_account(self):
        with self.assertRaises(ValueError):bot.start(self.cfg,new_account=True)
        self.buy();bot.stop()
        with self.assertRaises(ValueError):bot.start(self.cfg,new_account=True)
    def test_slow_analysis_does_not_block_position_protection(self):
        import threading
        self.buy();entered=threading.Event();release=threading.Event()
        def slow(_):entered.set();release.wait(3);return self.a
        service=bot.Service(lambda key,source:quote(time.time(),price=95),slow);service.background=True
        try:
            started=time.monotonic();service.pulse();self.assertLess(time.monotonic()-started,1)
            self.assertTrue(entered.wait(1));self.assertIsNone(bot.current_state()['position'])
        finally:release.set();service.job['done'].wait(2)
    def test_no_reentry_on_stop_candle_and_no_replay_after_restart(self):
        self.buy();bot.advance(self.run,quote(self.now+2,price=95),self.a,now=self.now+2)
        bot.advance(self.run,quote(self.now+3),self.a,now=self.now+3)
        self.assertIsNone(bot.current_state()['pending']);self.assertIsNone(bot.current_state()['position'])
        bot.stop();bot.start(self.cfg);run=bot.current_state()['run_id']
        bot.advance(run,quote(self.now+4),self.a,now=self.now+4);self.assertIsNone(bot.current_state()['pending'])
    def test_invalid_limits_and_real_orders_are_rejected(self):
        for changes in [{'max_spread':0},{'max_drawdown':0},{'max_exposure':101},{'max_deviation':float('nan')},{'source':'okx','instrument':'GOLD'},{'mode':'live'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):bot.start({**self.cfg,**changes})
