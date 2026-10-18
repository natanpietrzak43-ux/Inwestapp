import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import paper_bot as bot


def quote(value=100,stamp=None,key='XRP'):
    return {'instrument':key,'status':'ok','price':value,'timestamp':time.time() if stamp is None else stamp,'asOf':'2026-10-18T10:00:00+00:00','currency':'USD','provider':'test'}
def analysis(action='BUY',candle='2026-10-18T09:00:00+00:00',passed=True,**extra):
    return dict({'mode':'live','lastDate':candle,'decision':{'action':action,'reason':'test'},'historyGuard':{'passed':passed},'indicators':[{'atr':1}],'stale':False},**extra)


class PaperBotTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.dir.name});self.env.start()
        self.now=time.time();self.config={'instrument':'XRP','capital':10000,'costs':10,'slippage':5,'risk':1,'daily_loss':10};bot.start(self.config);self.run=bot.current_state()['run_id']
    def tearDown(self):self.env.stop();self.dir.cleanup()
    def buy(self):
        bot.advance(self.run,quote(stamp=self.now),analysis(),now=self.now)
        bot.advance(self.run,quote(stamp=self.now+1),now=self.now+1)
        return bot.current_state()['position']

    def test_decision_does_not_fill_on_a_quote_from_before_decision(self):
        bot.advance(self.run,quote(stamp=self.now-1),analysis(),now=self.now)
        s=bot.current_state();self.assertIsNone(s['position']);self.assertEqual(s['pending']['side'],'BUY')
        bot.advance(self.run,quote(stamp=self.now-1),now=self.now+1);self.assertIsNone(bot.current_state()['position'])
        bot.advance(self.run,quote(stamp=self.now+2),now=self.now+2);self.assertIsNotNone(bot.current_state()['position'])

    def test_entry_cost_slippage_and_cash_are_consistent(self):
        p=self.buy();self.assertAlmostEqual(p['entry'],100.05)
        s=bot.current_state();self.assertAlmostEqual(s['cash'],10000-p['units']*100.05*1.001)
        self.assertGreaterEqual(s['cash'],-1e-8);self.assertLess(p['stop'],p['entry']);self.assertGreater(p['target'],p['entry'])

    def test_stop_loss_first_observed_price_and_both_fees(self):
        p=self.buy();bot.advance(self.run,quote(value=95,stamp=self.now+2),now=self.now+2)
        r=bot.status();trade=r['trades'][0];fill=95*.9995
        expected=p['units']*fill*.999-p['notional']-p['entryFee']
        self.assertAlmostEqual(trade['pnl'],expected);self.assertAlmostEqual(r['state']['cash'],10000+expected)
        self.assertIsNone(r['state']['position']);self.assertEqual(r['state']['tradeCount'],1)

    def test_concurrent_cycles_do_not_duplicate_a_fill(self):
        bot.advance(self.run,quote(stamp=self.now),analysis(),now=self.now)
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(lambda _:bot.advance(self.run,quote(stamp=self.now+1),analysis(),now=self.now+1),range(5)))
        events=[e for e in bot.status()['events'] if e['kind']=='buy'];self.assertEqual(len(events),1)

    def test_guard_stale_demo_and_partial_selection_do_not_queue_entry(self):
        for a in [analysis(passed=False),analysis(stale=True),analysis(mode='demo'),analysis(action='WAIT')]:
            bot.advance(self.run,quote(stamp=self.now),a,now=self.now);self.assertIsNone(bot.current_state()['pending'])
            bot.start(self.config);self.run=bot.current_state()['run_id']

    def test_missing_or_old_price_never_executes_stop(self):
        p=self.buy()
        for q in [quote(value=1,stamp=self.now-500),{**quote(value=1),'status':'error'},{**quote(value=1),'currency':'EUR'},quote(value=1,stamp=self.now+1000)]:
            bot.advance(self.run,q,now=self.now+2);self.assertIsNotNone(bot.current_state()['position'])
        self.assertEqual(bot.current_state()['tradeCount'],0)
        self.assertFalse(bot.status()['state']['valuationFresh'])

    def test_stop_cancels_entry_but_keeps_position_protection(self):
        bot.advance(self.run,quote(stamp=self.now),analysis(),now=self.now);bot.stop();self.assertIsNone(bot.current_state()['pending'])
        bot.start(self.config);self.run=bot.current_state()['run_id'];self.buy();bot.stop()
        bot.advance(self.run,quote(value=95,stamp=self.now+2),now=self.now+2)
        self.assertIsNone(bot.current_state()['position']);self.assertFalse(bot.current_state()['active'])

    def test_order_expires_without_inventing_historical_price(self):
        bot.advance(self.run,quote(stamp=self.now),analysis(),now=self.now)
        bot.advance(self.run,quote(stamp=self.now+1300),now=self.now+1300)
        self.assertIsNone(bot.current_state()['position']);self.assertIsNone(bot.current_state()['pending'])
        self.assertTrue(any(e['kind']=='expired' for e in bot.status()['events']))

    def test_daily_limit_disables_new_entries(self):
        bot.stop();bot.start({**self.config,'daily_loss':.1});self.run=bot.current_state()['run_id'];self.buy()
        bot.advance(self.run,quote(value=50,stamp=self.now+2),now=self.now+2)
        self.assertFalse(bot.current_state()['active']);self.assertIsNone(bot.current_state()['position'])
        self.assertIn('Limit',bot.status()['trades'][0]['reason'])

    def test_close_request_needs_next_fresh_quote(self):
        self.buy()
        with patch('paper_bot.time.time',return_value=self.now+3):bot.close_position()
        bot.advance(self.run,quote(value=100.5,stamp=self.now+2),now=self.now+3);self.assertIsNotNone(bot.current_state()['position'])
        bot.advance(self.run,quote(value=100.5,stamp=self.now+4),now=self.now+4);self.assertIsNone(bot.current_state()['position'])

    def test_configuration_and_real_order_mode_are_rejected(self):
        for changes in [{'instrument':'DOGE'},{'mode':'live'},{'risk':99},{'capital':float('inf')},{'daily_loss':0},{'preset':'external_code'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):bot.start({**self.config,**changes})
        self.buy()
        with self.assertRaises(ValueError):bot.start({**self.config,'instrument':'BTC'})

    def test_worker_analysis_failure_preserves_risk_monitor(self):
        self.buy();service=bot.Service(lambda _:quote(value=95),lambda _:(_ for _ in ()).throw(OSError()))
        service.pulse();self.assertIsNone(bot.current_state()['position']);self.assertIn('analizy',bot.current_state()['status'])

    def test_stale_cycle_after_configuration_change_is_ignored(self):
        old=self.run;bot.start({**self.config,'instrument':'BTC'})
        bot.advance(old,quote(),analysis());self.assertIsNone(bot.current_state()['pending'])

    def test_research_record_cannot_be_marked_verified_by_payload(self):
        result=bot.save_research({'fetchedAt':'2026-10-18','verified':True,'content':{'code':'untrusted'}})
        self.assertFalse(result['verified']);self.assertEqual(len(bot.research_records()),1)

    def test_export_contains_paper_account_without_touching_manual_journal(self):
        import user_data
        self.buy();bot.advance(self.run,quote(value=95,stamp=self.now+2),now=self.now+2)
        exported=user_data.export_data()['tables'];self.assertIn('paper_state',exported);self.assertEqual(len(exported['paper_trades']),1)
        self.assertEqual(user_data.journal()['summary']['closed'],0)

    def test_initial_capital_change_before_trades_resets_daily_baseline(self):
        bot.advance(self.run,quote(stamp=self.now),now=self.now)
        bot.stop();bot.start({**self.config,'capital':20000})
        s=bot.current_state();self.assertEqual(s['cash'],20000);self.assertEqual(s['dayEquity'],20000);self.assertIsNone(s['day'])
