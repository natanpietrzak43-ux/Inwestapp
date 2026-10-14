import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from analysis_engine import indicators, validate_bars, analyze, backtest, history_guard
from server import demo_bars, fetch_bars, CACHE
from technical_tools import combined_decision, extra_indicators, selection, PRESETS, TOOLS
from timeframes import candle_closed


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.bars=demo_bars('XRP')

    def test_bollinger_population_standard_deviation(self):
        rows=[{**b,'close':float(i+1)} for i,b in enumerate(self.bars)]
        ind=indicators(rows)[19]
        self.assertEqual(ind['bbMid'],10.5)
        self.assertAlmostEqual(ind['bbUpper'],10.5+2*(33.25**.5))
        self.assertAlmostEqual(ind['bbLower'],10.5-2*(33.25**.5))

    def test_obv_rise_fall_equal_and_momentum(self):
        rows=[{**b,'close':100+i,'volume':10} for i,b in enumerate(self.bars)]
        rows[0]['close'],rows[1]['close'],rows[2]['close'],rows[3]['close']=100,101,100,100
        result=indicators(rows)
        self.assertEqual([r['obv'] for r in result[:4]],[0,10,0,0])
        self.assertAlmostEqual(result[20]['momentum'],100*120/110)

    def test_ichimoku_cloud_uses_earlier_window(self):
        rows=[{**b,'high':float(100+i),'low':float(90+i),'close':float(95+i)} for i,b in enumerate(self.bars)]
        result=indicators(rows)
        self.assertIsNone(result[76]['cloudB'])
        self.assertEqual(result[77]['cloudB'],(151+90)/2)
        self.assertEqual(result[77]['lagReference'],146)
        self.assertEqual(result[77]['cloudA'],(result[51]['tenkan']+result[51]['kijun'])/2)

    def test_alligator_shifts_and_zero_stochastic_range(self):
        flat=[{**b,'high':100,'low':100,'open':100,'close':100} for b in self.bars]
        result=indicators(flat)
        self.assertIsNone(result[19]['alligatorJaw'])
        self.assertEqual(result[20]['alligatorJaw'],100)
        self.assertEqual(result[17]['stochK'],50)
        self.assertEqual(result[17]['stochD'],50)
        self.assertEqual(result[-1]['fibonacci']['direction'],'unknown')

    def test_sar_reversal_is_causal(self):
        rows=[{**b,'high':102+i,'low':99+i,'close':101+i} for i,b in enumerate(self.bars)]
        rows[10].update(high=101,low=90,close=95)
        result=indicators(rows)
        self.assertLess(result[9]['sar'],rows[9]['close'])
        self.assertGreater(result[10]['sar'],rows[10]['close'])
        self.assertEqual(result[:10],indicators(rows[:10]))

    def test_all_fields_are_prefix_invariant(self):
        long=indicators(self.bars)
        for length in (78,200,400):
            self.assertEqual(long[:length],indicators(self.bars[:length]))

    def test_fibonacci_direction_and_levels(self):
        rows=[{**b,'low':100+i,'high':102+i,'close':101+i} for i,b in enumerate(self.bars)]
        fib=indicators(rows)[54]['fibonacci']
        self.assertEqual(fib['direction'],'up')
        self.assertEqual(fib['levels']['0.5'],128)
        self.assertAlmostEqual(fib['levels']['0.618'],156-56*.618)

    def test_groups_are_not_inflated_by_more_tools(self):
        ind=indicators(self.bars)[-1]
        base=combined_decision(self.bars[-1],ind)
        more=combined_decision(self.bars[-1],ind,list(TOOLS))
        self.assertEqual(base['total'],more['total'])
        self.assertEqual(more['total'],5)

    def test_empty_missing_volume_and_incomplete_sets_wait(self):
        ind=indicators(self.bars)[-1]
        for tools in ([],['rsi'],['ema','rsi','adx']):
            result=combined_decision(self.bars[-1],ind,tools)
            self.assertEqual(result['action'],'WAIT')
            self.assertTrue(result['missingGroups'])
        result=combined_decision(self.bars[-1],{**ind,'hasVolume':False})
        self.assertEqual(result['action'],'WAIT')
        self.assertIn(TOOLS['obv']['name'],result['unavailableTools'])

    def test_regime_range_buy_and_wrong_adx_wait(self):
        ind={'adx':15,'bbLower':90,'bbMid':100,'bbUpper':110,'stochK':25,'stochD':20,
             'obv':20,'obvEma':10,'obvPrevious':15,'hasVolume':True,'atr':2}
        bar={'close':92,'low':89}
        self.assertEqual(combined_decision(bar,ind,PRESETS['range']['tools'],'range')['action'],'BUY')
        self.assertEqual(combined_decision(bar,{**ind,'adx':25},PRESETS['range']['tools'],'range')['action'],'WAIT')

    def test_selection_validation(self):
        for tools in (['unknown'],[{}],'ema'):
            with self.assertRaises(ValueError):selection(tools)
        self.assertEqual(selection(['ema','ema']),['ema'])

    def test_history_guard_blocks_entry_but_allows_exit(self):
        stats={'trades':[],'returnPct':-5,'profitFactor':.8,'holdoutTrades':1,'holdoutPnl':-10}
        with patch('analysis_engine.backtest',return_value=stats):
            with patch('analysis_engine.decision',return_value={'action':'BUY','reason':'technical'}):
                result=analyze(self.bars)
                self.assertEqual(result['decision']['action'],'WAIT')
                self.assertEqual(result['decision']['technicalAction'],'BUY')
                self.assertFalse(result['historyGuard']['passed'])
            with patch('analysis_engine.decision',return_value={'action':'SELL','reason':'exit'}):
                self.assertEqual(analyze(self.bars)['decision']['action'],'SELL')
        eligible={'trades':[{} for _ in range(30)],'returnPct':4,'profitFactor':1.5,'holdoutTrades':5,'holdoutPnl':10}
        self.assertTrue(history_guard(eligible)['passed'])
        self.assertFalse(history_guard({**eligible,'holdoutPnl':-1})['passed'])


class HourlyTests(unittest.TestCase):
    def test_open_hour_is_rejected_and_closed_hour_accepted(self):
        now=datetime(2026,10,14,12,20,tzinfo=timezone.utc)
        self.assertFalse(candle_closed('2026-10-14T12:00:00Z','1h',now))
        self.assertTrue(candle_closed('2026-10-14T11:00:00Z','1h',now))
        self.assertFalse(candle_closed('2026-10-14','1d',now))

    def test_timezone_normalization_and_duplicate_instants(self):
        rows=demo_bars('XRP','1h')
        result=validate_bars(rows,'1h')
        self.assertIn('+00:00',result[-1]['date'])
        rows[-1]['date']=datetime.fromisoformat(rows[-2]['date']).astimezone(timezone(timedelta(hours=2))).isoformat()
        with self.assertRaises(ValueError):validate_bars(rows,'1h')
        rows=demo_bars('XRP')
        with self.assertRaises(ValueError):validate_bars(rows,'1h')

    def test_history_endpoint_filters_unfinished_hour(self):
        now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
        times=[int((now-timedelta(hours=h)).timestamp()) for h in (2,1,0)]
        quote={k:[100,100,100] for k in ('open','high','low','close','volume')}
        payload={'chart':{'result':[{'timestamp':times,'indicators':{'quote':[quote]}}]}}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_):pass
        CACHE.clear()
        with patch('server.urllib.request.urlopen',return_value=Response()) as fetch,patch('server.json.load',return_value=payload):
            rows,_=fetch_bars('XRP','1h')
        self.assertEqual(len(rows),2)
        self.assertIn('interval=60m',fetch.call_args.args[0].full_url)
        self.assertNotEqual(rows[-1]['date'],now.isoformat())
        CACHE.clear()

    def test_hourly_and_daily_presets_use_matching_backtest(self):
        for timeframe in ('1h','1d'):
            for preset in PRESETS.values():
                rows=demo_bars('XRP',timeframe)
                result=analyze(rows,timeframe=timeframe,tools=preset['tools'],strategy=preset['strategy'])
                independent=backtest(result['bars'],result['indicators'],tools=preset['tools'],strategy=preset['strategy'])
                self.assertEqual(result['backtest'],independent)


if __name__=='__main__':unittest.main()
