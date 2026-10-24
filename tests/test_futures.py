import copy
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from datetime import datetime,timezone

import paper_bot as bot
import leveraged_trading as model
import bot_backtest
import okx_data
from server import demo_bars


def config(**extra):
    return bot.configuration({'instrument':'XLM','source':'okx','engine':'agents','market':'perpetual',
                              'leverage':3,'funding_bps':1,**extra})


def fixture(now,bear=False):
    end=int(now//3600)*3600
    bars=[{'date':datetime.fromtimestamp(end-(230-i)*3600,timezone.utc).isoformat(),
           'open':100.,'high':101.,'low':99.,'close':100.,'volume':1000} for i in range(230)]
    ind={'ema20':99,'ema50':98,'ema200':97,'rsi':60,'atr':1,'adx':25,'obv':2000,'obvEma':1000,'obvPrevious':1500,'hasVolume':True,'bbMid':99,'bbLower':95,'bbUpper':105}
    if bear:ind.update(ema20=101,ema50=102,ema200=103,rsi=40,obv=500,obvPrevious=700,bbMid=101)
    return {'mode':'live','source':'okx','market':'perpetual','currency':'USDT','instrument':{'id':'XLM'},'timeframe':'1h',
            'bars':bars,'indicators':[ind],'lastDate':bars[-1]['date'],'fetchedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),
            'stale':False,'historyGuard':{'passed':True}}


def quote(now,price=100):
    return {'status':'ok','instrument':'XLM','provider':'OKX','source':'okx','sourceSymbol':'XLM-USDT-SWAP','currency':'USDT',
            'timestamp':now,'asOf':datetime.fromtimestamp(now,timezone.utc).isoformat(),'price':price,'bid':price-.01,'ask':price+.01,'markPrice':price,'markTimestamp':now}


class FuturesMathTests(unittest.TestCase):
    def test_long_and_short_pnl_margin_and_fees_have_independent_expected_values(self):
        cfg=config(costs=10,slippage=0)
        for side,exit_price in [(1,103),(-1,97)]:
            p=model.plan(cfg,10000,10000,100,1,side)
            self.assertAlmostEqual(p['margin'],p['units']*100/3)
            free=10000-p['margin']-p['entryFee'];r=model.settlement(p,exit_price,cfg)
            expected=p['units']*3-p['units']*(100+exit_price)*.001
            self.assertAlmostEqual(r['pnl'],expected);self.assertAlmostEqual(free+r['credit'],10000+expected)
            self.assertLessEqual(p['estimatedStopLoss'],100)

    def test_leverage_does_not_multiply_account_equity_or_profit_again(self):
        one=config(leverage=1,max_exposure=100);ten=config(leverage=10,max_exposure=100)
        p1=model.plan(one,10000,10000,100,1,1);p10=model.plan(ten,10000,10000,100,1,1)
        self.assertAlmostEqual(p1['units'],p10['units']);self.assertAlmostEqual(p1['margin']/10,p10['margin'])
        self.assertAlmostEqual(model.settlement(p1,103,one)['pnl'],model.settlement(p10,103,ten)['pnl'])

    def test_funding_is_signed_at_utc_boundaries_and_never_double_counted(self):
        cfg=config(costs=0,funding_bps=10)
        for side in (1,-1):
            p=model.plan(cfg,10000,10000,100,1,side,now=28799)
            model.funding(p,100,28801,cfg);expected=side*p['units']*100*.001
            self.assertAlmostEqual(p['funding'],expected)
            model.funding(p,100,28802,cfg);self.assertAlmostEqual(p['funding'],expected)
            self.assertAlmostEqual(model.settlement(p,100,cfg)['pnl'],-expected)

    def test_liquidation_price_solves_maintenance_equation_and_limits_loss_to_margin(self):
        cfg=config(costs=10)
        for side in (1,-1):
            p=model.plan(cfg,10000,10000,100,1,side);liq=p['liquidationPrice']
            collateral=p['margin']+side*p['units']*(liq-100)
            self.assertAlmostEqual(collateral,p['units']*liq*(.005+.001))
            self.assertTrue(model.liquidated(p,liq,cfg))
            r=model.settlement(p,1 if side==1 else 1000,cfg,True)
            self.assertEqual(r['credit'],0);self.assertAlmostEqual(r['pnl'],-p['margin']-p['entryFee'])

    def test_stop_behind_liquidation_is_rejected(self):
        self.assertIsNone(model.plan(config(leverage=10),10000,10000,100,6,1))

    def test_slipped_stop_and_both_fees_respect_the_risk_budget(self):
        cfg=config(costs=20,slippage=15,max_exposure=100)
        for side in (1,-1):
            p=model.plan(cfg,10000,10000,100,1,side)
            result=model.settlement(p,p['stop']*(1-side*.0015),cfg)
            self.assertGreaterEqual(result['pnl'],-p['riskBudget']-1e-8)

    def test_short_requires_volume_and_context_confirmation_not_only_exit_signal(self):
        a=fixture(time.time(),True);cfg=config();ind=a['indicators'][-1]
        self.assertEqual(model.signal(a['bars'][-1],ind,cfg)['action'],'SHORT')
        self.assertEqual(model.signal(a['bars'][-1],{**ind,'obv':2000},cfg)['action'],'WAIT')

    def test_unsupported_futures_combinations_and_invalid_numeric_inputs_fail(self):
        for extra in ({'instrument':'GOLD'},{'source':'reference'},{'engine':'classic'},{'leverage':11},{'leverage':float('nan')},{'maintenance_margin':0},{'funding_bps':101}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):config(**extra)
        with self.assertRaises(ValueError):bot.configuration({'market':'spot','leverage':2})


class FuturesPaperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.temp.name});self.env.start()
        self.now=time.time();self.cfg=config();bot.start(self.cfg);self.run=bot.current_state()['run_id'];self.a=fixture(self.now)
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def enter(self,bear=False):
        a=fixture(self.now,bear)
        bot.advance(self.run,quote(self.now),a,now=self.now)
        bot.advance(self.run,quote(self.now+1),a,now=self.now+1)
        return bot.current_state()['position']

    def test_long_entry_reserves_margin_and_waits_for_a_later_quote(self):
        bot.advance(self.run,quote(self.now),self.a,now=self.now)
        self.assertIsNone(bot.current_state()['position']);self.assertEqual(bot.current_state()['pending']['side'],'LONG')
        bot.advance(self.run,quote(self.now-1),self.a,now=self.now+1);self.assertIsNone(bot.current_state()['position'])
        p=self.enter();self.assertEqual(p['side'],1);self.assertEqual(p['leverage'],3)
        self.assertAlmostEqual(bot.current_state()['cash'],10000-p['margin']-p['entryFee'])

    def test_short_entry_profit_and_audit_survive_restart(self):
        p=self.enter(True);self.assertIsNotNone(p);self.assertEqual(p['side'],-1)
        bot.advance(self.run,quote(self.now+2,95),None,now=self.now+2)
        s=bot.current_state();trade=bot.status()['trades'][0]
        self.assertGreater(trade['pnl'],0);self.assertAlmostEqual(s['cash'],10000+trade['pnl'])
        self.assertIsNotNone(trade['entryAudit']);self.assertIsNotNone(trade['exitAudit'])
        self.assertEqual(s['config']['market'],'perpetual')

    def test_missing_mark_wrong_contract_stale_or_spot_analysis_blocks_execution(self):
        for changes in ({'sourceSymbol':'XLM-USDT'},{'markTimestamp':self.now-121},{'markPrice':float('nan')},{'currency':'USD'}):
            bot.advance(self.run,{**quote(self.now),**changes},self.a,now=self.now)
            self.assertIsNone(bot.current_state()['position']);self.assertIsNone(bot.current_state()['pending'])
        bot.advance(self.run,quote(self.now),{**self.a,'market':'spot'},now=self.now)
        self.assertIsNone(bot.current_state()['pending'])

    def test_pending_entry_is_cancelled_after_history_guard_or_spread_deteriorates(self):
        bot.advance(self.run,quote(self.now),self.a,now=self.now);self.assertIsNotNone(bot.current_state()['pending'])
        bot.advance(self.run,quote(self.now+1),{**self.a,'historyGuard':{'passed':False}},now=self.now+1)
        self.assertIsNone(bot.current_state()['pending']);self.assertIsNone(bot.current_state()['position'])

    def test_stopping_keeps_short_stop_protection_without_analysis(self):
        self.enter(True);bot.stop();bot.advance(self.run,quote(self.now+2,106),None,now=self.now+2)
        self.assertIsNone(bot.current_state()['position']);self.assertFalse(bot.current_state()['active']);self.assertEqual(len(bot.status()['trades']),1)

    def test_manual_close_requires_later_quote_and_works_without_analysis(self):
        self.enter()
        with patch('paper_bot.time.time',return_value=self.now+2):bot.close_position()
        bot.advance(self.run,quote(self.now+1),None,now=self.now+2);self.assertIsNotNone(bot.current_state()['position'])
        bot.advance(self.run,quote(self.now+3),None,now=self.now+3);self.assertIsNone(bot.current_state()['position'])

    def test_liquidation_preserves_free_cash_and_cannot_reopen_on_same_candle(self):
        p=self.enter();free=bot.current_state()['cash']
        bot.advance(self.run,quote(self.now+2,50),self.a,now=self.now+2)
        self.assertAlmostEqual(bot.current_state()['cash'],free);self.assertIsNone(bot.current_state()['pending'])
        self.assertTrue(bot.status()['trades'][0]['liquidated'])

    def test_concurrent_cycles_cannot_duplicate_a_futures_fill(self):
        bot.advance(self.run,quote(self.now),self.a,now=self.now)
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:bot.advance(self.run,quote(self.now+1),self.a,now=self.now+1),range(4)))
        self.assertEqual(len([e for e in bot.status()['events'] if e['kind']=='open']),1)

    def test_market_change_requires_new_account_and_preserves_history(self):
        self.enter();bot.advance(self.run,quote(self.now+2,105),None,now=self.now+2);bot.stop()
        spot={**self.cfg,'market':'spot','leverage':1}
        with self.assertRaises(ValueError):bot.start(spot)
        old=bot.current_state()['accountId'];result=bot.start(spot,new_account=True)
        self.assertNotEqual(result['state']['accountId'],old);self.assertEqual(result['archives'][0]['config']['market'],'perpetual')


class BotReplayTests(unittest.TestCase):
    def setUp(self):
        self.bars=[{**b,'open':100.,'high':100.1,'low':99.9,'close':100.} for b in demo_bars('XLM','1h')[:230]]
        self.inds=[{'atr':1} for b in self.bars]
    def run_replay(self,cfg=None,bars=None,side='LONG',**extra):
        rows=bars or self.bars
        def signal(bar,ind,cfg):return {'action':side if bar['date']==rows[199]['date'] else 'WAIT'}
        with patch('bot_backtest.indicators',return_value=self.inds),patch('bot_backtest.model.signal',side_effect=signal):
            return bot_backtest.research_run(rows,cfg or config(costs=10,slippage=10,funding_bps=0),spread_bps=0,**extra)

    def test_replay_fills_next_open_with_both_fees_and_slippage_and_force_closes(self):
        r=self.run_replay();self.assertEqual(r['metrics']['closedTrades'],1);t=r['trades'][0]
        self.assertEqual(t['entryDate'],self.bars[200]['date']);self.assertAlmostEqual(t['entry'],100.1);self.assertAlmostEqual(t['exit'],99.9)
        expected=t['units']*(99.9-100.1)-t['units']*(100.1+99.9)*.001
        self.assertAlmostEqual(t['pnl'],expected);self.assertAlmostEqual(r['metrics']['netPnl'],expected)
        self.assertFalse(r['historicalGuardReplayed'])

    def test_short_is_profitable_on_a_decline_and_future_does_not_change_prior_fills(self):
        changed=copy.deepcopy(self.bars)
        for b in changed[201:]:b.update(open=99,high=99.1,low=98.9,close=99)
        r=self.run_replay(bars=changed,side='SHORT');self.assertGreater(r['metrics']['netPnl'],0)
        r0=self.run_replay(side='SHORT');self.assertEqual(r['trades'][0]['entry'],r0['trades'][0]['entry'])

    def test_ohlc_ambiguity_uses_stop_before_target(self):
        changed=copy.deepcopy(self.bars);changed[201].update(low=97,high=104)
        r=self.run_replay(bars=changed);self.assertEqual(r['trades'][0]['reason'],'Stop loss')

    def test_gap_through_liquidation_loses_margin_but_not_all_account(self):
        changed=copy.deepcopy(self.bars)
        for b in changed[201:]:b.update(open=50,high=50.1,low=49.9,close=50)
        r=self.run_replay(bars=changed);self.assertEqual(r['metrics']['liquidations'],1)
        self.assertGreater(r['metrics']['finalEquity'],0);self.assertTrue(r['trades'][0]['liquidated'])

    def test_date_filter_and_bad_ranges_do_not_invent_history(self):
        for dates in ({'start_date':'2100-01-01'},{'start_date':'2026-10-02','end_date':'2026-10-01'},{'end_date':'oops'}):
            with self.assertRaises(ValueError):self.run_replay(**dates)

    def test_insufficient_history_and_excessive_spread_fail_or_block(self):
        with self.assertRaises(ValueError):bot_backtest.research_run(self.bars[:200],config())
        with patch('bot_backtest.indicators',return_value=self.inds),patch('bot_backtest.model.signal',return_value={'action':'LONG'}):
            r=bot_backtest.research_run(self.bars,config(max_spread=1),spread_bps=10)
        self.assertEqual(r['metrics']['closedTrades'],0);self.assertGreater(r['blockedCount'],0)

    def test_daily_loss_resets_on_next_utc_day_but_drawdown_never_resets_in_replay(self):
        from datetime import timedelta
        zero=datetime(2026,9,1,tzinfo=timezone.utc)
        rows=[{**b,'date':(zero+timedelta(hours=i-200)).isoformat(),'low':97.} for i,b in enumerate(self.bars)]
        with patch('bot_backtest.indicators',return_value=self.inds),patch('bot_backtest.model.signal',return_value={'action':'LONG'}):
            daily=bot_backtest.research_run(rows,config(costs=0,slippage=0,funding_bps=0,daily_loss=.5,max_drawdown=50),spread_bps=0)
            drawdown=bot_backtest.research_run(rows,config(costs=0,slippage=0,funding_bps=0,daily_loss=20,max_drawdown=1),spread_bps=0)
        self.assertEqual(daily['metrics']['closedTrades'],2)
        self.assertEqual(drawdown['metrics']['closedTrades'],1)

    def test_later_price_changes_do_not_change_earlier_equity_with_real_indicators(self):
        rows=demo_bars('XLM','1h');changed=copy.deepcopy(rows);cut=750
        for b in changed[cut:]:
            for k in ('open','high','low','close'):b[k]*=1.8
        first=bot_backtest.research_run(rows,config());second=bot_backtest.research_run(changed,config())
        self.assertEqual(first['equity'][:cut-200],second['equity'][:cut-200])
