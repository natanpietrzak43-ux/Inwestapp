import copy
import unittest
from unittest.mock import patch

from analysis_engine import analyze, backtest, decision, indicators, parameters, validate_bars
from server import demo_bars, package


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.bars = demo_bars('XRP')

    def test_flat_market_rsi_and_adx(self):
        rows = [{**b, 'open': 100, 'close': 100, 'high': 101, 'low': 99, 'volume': 1000} for b in self.bars]
        ind = indicators(rows)[-1]
        self.assertEqual(ind['rsi'], 50)
        self.assertEqual(ind['adx'], 0)
        self.assertEqual(ind['atr'], 2)
        self.assertEqual(ind['macdHist'], 0)
        self.assertAlmostEqual(ind['ema200'], 100)
        self.assertEqual(decision(rows[-1], ind)['action'], 'WAIT')

    def test_rising_prices_rsi(self):
        rows = [{**b, 'open': 10+i, 'close': 10+i, 'high': 11+i, 'low': 9+i} for i,b in enumerate(self.bars)]
        self.assertEqual(indicators(rows)[-1]['rsi'], 100)

    def test_indicators_do_not_see_future(self):
        short = indicators(self.bars[:400])
        long = indicators(self.bars)
        self.assertEqual(short, long[:400])

    def test_ema200_seed_and_recurrence(self):
        rows = [{**b, 'close': float(i+1)} for i,b in enumerate(self.bars)]
        result = indicators(rows)
        self.assertIsNone(result[198]['ema200'])
        self.assertEqual(result[199]['ema200'], 100.5)
        expected = 201*(2/201)+100.5*(1-2/201)
        self.assertAlmostEqual(result[200]['ema200'], expected)

    def test_mandatory_confirmations(self):
        ind = {'sma200': 80, 'ema200': 85, 'ema20': 95, 'ema50': 90, 'adx': 25, 'rsi': 60,
               'macdHist': 1, 'atr': 2, 'obv':20,'obvEma':10,'obvPrevious':15,'hasVolume':True,
               'bbMid':99,'bbUpper':110,'bbLower':90}
        self.assertEqual(decision({'close':100,'low':99}, ind)['action'], 'BUY')
        for key, value in [('adx',10),('rsi',75),('atr',10),('ema20',85),('ema200',105),('obv',5),('bbMid',105)]:
            self.assertEqual(decision({'close':100,'low':99},{**ind,key:value})['action'],'WAIT')
        self.assertEqual(decision({'close':100,'low':99},{**ind,'macdHist':-1})['action'],'BUY')
        bear={**ind,'rsi':40,'ema20':85,'macdHist':-1}
        self.assertEqual(decision({'close':80,'low':79},bear)['action'],'SELL')

    def test_demo_never_recommends_trade(self):
        result = package('XRP', self.bars, 'demo', 10000, 1, 10)
        self.assertEqual(result['decision']['action'], 'WAIT')
        self.assertIn('modelAction', result['decision'])

    def test_stale_import_blocks_signal(self):
        result = package('XRP', self.bars[:400], 'csv', 10000, 1, 10)
        self.assertTrue(result['stale'])
        self.assertEqual(result['decision']['action'], 'WAIT')

    def test_invalid_data(self):
        for key, value in [('low',100000),('volume',-1),('close',float('nan')),('close',1e-320),('high',1e308)]:
            rows = copy.deepcopy(self.bars)
            rows[-1][key] = value
            with self.assertRaises(ValueError):
                validate_bars(rows)
        with self.assertRaises(ValueError):
            validate_bars(self.bars[:100])
        with self.assertRaises(ValueError):
            validate_bars([self.bars[0]]+self.bars)

    def test_parameter_limits(self):
        for args in [(99,1,10),(10000,0,10),(10000,4,10),(10000,1,-1),(float('inf'),1,10)]:
            with self.assertRaises(ValueError):
                parameters(*args)

    def test_engine_runs_all_instruments(self):
        for key in ('XRP','XLM','SILVER','OIL','GOLD'):
            result = analyze(demo_bars(key))
            self.assertGreater(len(result['backtest']['equity']), 20)
            self.assertGreaterEqual(result['backtest']['maxDrawdown'], 0)
            self.assertTrue(result['decision']['checks'])


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.bars = [{**b,'open':100,'close':100,'high':101,'low':99} for b in demo_bars('XRP')[:220]]
        self.inds = [{'atr':2} for _ in self.bars]

    def run_one_entry(self):
        def signal(bar, _, *args):
            return {'action': 'BUY' if bar['date'] == self.bars[199]['date'] else 'WAIT'}
        with patch('analysis_engine.decision',side_effect=signal):
            return backtest(self.bars,self.inds,10000,1,10)

    def test_next_open_entry(self):
        self.bars[200].update(open=105,close=105,high=106,low=104)
        result = self.run_one_entry()
        # Next bar opens below stop; exactly one entry executed on bar 200.
        self.assertEqual(result['trades'][0]['entryDate'], self.bars[200]['date'])
        self.assertEqual(result['trades'][0]['entry'], 105)

    def test_stop_first_when_both_levels_touched(self):
        self.bars[200].update(high=108,low=94)
        trade = self.run_one_entry()['trades'][0]
        self.assertEqual(trade['exit'], 96)
        self.assertEqual(trade['reason'], 'Stop loss')
        self.assertLess(trade['pnl'],0)

    def test_gap_stop_and_costs(self):
        self.bars[201].update(open=90,close=90,high=91,low=89)
        trade = self.run_one_entry()['trades'][0]
        self.assertEqual(trade['exit'],90)
        expected = trade['units']*(90*(1-.001)-100*(1+.001))
        self.assertAlmostEqual(trade['pnl'], expected)

    def test_final_signal_cannot_execute_without_next_bar(self):
        with patch('analysis_engine.decision',side_effect=lambda bar,_,*args: {'action':'BUY' if bar['date']==self.bars[-1]['date'] else 'WAIT'}):
            result = backtest(self.bars,self.inds)
        self.assertEqual(result['trades'],[])
        self.assertIsNone(result['openPosition'])
        self.assertEqual(result['returnPct'],0)

    def test_future_prices_cannot_change_prior_equity(self):
        def signal(bar,_,*args):
            return {'action':'BUY' if bar['date']==self.bars[199]['date'] else 'WAIT'}
        with patch('analysis_engine.decision',side_effect=signal):
            short=backtest(self.bars[:210],self.inds[:210])
            self.bars[215].update(open=500,high=501,low=499,close=500)
            long=backtest(self.bars,self.inds)
        self.assertEqual(short['equity'],long['equity'][:10])


if __name__ == '__main__':
    unittest.main()
