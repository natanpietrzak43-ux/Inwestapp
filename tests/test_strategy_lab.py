import unittest
from unittest.mock import patch
from server import demo_bars
from analysis_engine import indicators,backtest
from strategy_lab import compare
from technical_tools import PRESETS

class StrategyLabTests(unittest.TestCase):
    def test_chronological_test_uses_independent_cash_and_full_prior_warmup(self):
        bars=demo_bars('BTC','1h');r=compare(bars,'1h');split=r['initialBars']+200
        self.assertEqual(r['testBars'],len(bars)-split);self.assertEqual(r['splitDate'],bars[split]['date'])
        self.assertEqual(len(r['rows']),5);inds=indicators(bars)
        for row in r['rows']:
            p=PRESETS[row['id']];s=backtest(bars,inds,tools=p['tools'],strategy=p['strategy'],start_index=split)
            self.assertEqual(row['test']['returnPct'],s['returnPct']);self.assertEqual(row['test']['trades'],len(s['trades']))
            self.assertAlmostEqual(row['test']['netPnl'],10000*s['returnPct']/100)
        self.assertFalse(r['sourceCodeParityVerified'])

    def test_initial_period_does_not_change_when_future_prices_change(self):
        bars=demo_bars('XRP','1h');r1=compare(bars,'1h');split=r1['initialBars']+200
        changed=[dict(b) for b in bars]
        for b in changed[split:]:
            for key in ('open','high','low','close'):b[key]*=2
        r2=compare(changed,'1h')
        self.assertEqual([r['initial'] for r in r1['rows']],[r['initial'] for r in r2['rows']])

    def test_not_enough_history_is_rejected(self):
        with self.assertRaises(ValueError):compare(demo_bars('XRP','1h')[-300:],'1h')

    def test_backtest_cannot_start_without_history_or_at_end(self):
        bars=demo_bars('XRP','1h');inds=indicators(bars)
        for start in (0,199,len(bars)):
            with self.assertRaises(ValueError):backtest(bars,inds,start_index=start)

    def test_separate_slippage_is_charged_on_both_sides(self):
        from unittest.mock import patch
        bars=demo_bars('XRP','1h')[:220]
        bars=[{**b,'open':100.,'high':100.,'low':100.,'close':100.} for b in bars]
        inds=[{'atr':1} for _ in bars]
        decisions=[{'action':'BUY'}]+[{'action':'SELL'}]*19
        with patch('analysis_engine.decision',side_effect=decisions):r=backtest(bars,inds,costs=10,slippage=10)
        t=r['trades'][0];self.assertAlmostEqual(t['entry'],100.1);self.assertAlmostEqual(t['exit'],99.9)
        expected=t['units']*(99.9*.999-100.1*1.001)
        self.assertAlmostEqual(t['pnl'],expected);self.assertEqual(r['slippageBps'],10)

    def test_invalid_slippage_is_rejected(self):
        bars=demo_bars('XRP','1h');inds=indicators(bars)
        for slip in (-1,101,float('nan')):
            with self.assertRaises(ValueError):backtest(bars,inds,slippage=slip)
