import os
import tempfile
import time
import unittest
from unittest.mock import patch

from analysis_engine import analyze,indicators
from custom_indicators import ema_first,mercado_indicators
from market_data import INSTRUMENTS,get_quotes
from news_data import matches
from server import demo_bars
from technical_tools import combined_decision,tool_reading
import user_data


class NewEmaTests(unittest.TestCase):
    def test_first_price_seed_and_alpha_independent_of_legacy_ema(self):
        self.assertEqual(ema_first([10,12,8],3),[10,11,9.5])
        close=[100,111,122]
        r=mercado_indicators(close)
        self.assertEqual(r[0]['emaM1'],100)
        self.assertEqual(r[1]['emaM1'],101)
        self.assertAlmostEqual(r[1]['emaM2'],100+11*2/90)
        self.assertAlmostEqual(r[1]['emaM3'],100+11*2/201)
        self.assertFalse(r[-1]['emaMercadoReady'])
        self.assertFalse(mercado_indicators([100]*200)[198]['emaMercadoReady'])
        self.assertTrue(mercado_indicators([100]*200)[199]['emaMercadoReady'])

    def test_ema_requires_order_and_close_confirmation(self):
        ind={'emaM1':3,'emaM2':2,'emaM3':1,'emaMercadoReady':True}
        self.assertEqual(tool_reading('ema_mercado',{'close':4},ind,'trend')['state'],'bull')
        self.assertEqual(tool_reading('ema_mercado',{'close':2.5},ind,'trend')['state'],'neutral')
        self.assertEqual(tool_reading('ema_mercado',{'close':.5},{**ind,'emaM1':1,'emaM3':3},'trend')['state'],'bear')
        self.assertEqual(tool_reading('ema_mercado',{'close':4},{**ind,'emaMercadoReady':False},'trend')['state'],'missing')

    def test_prefix_invariance_new_ema(self):
        close=[100+i%13-i/10 for i in range(500)]
        full=mercado_indicators(close)
        for count in (21,89,200,350):self.assertEqual(full[:count],mercado_indicators(close[:count]))

    def test_ema_counts_as_one_trend_group(self):
        ind={'ema20':4,'ema50':3,'ema200':1,'emaM1':4,'emaM2':3,'emaM3':1,'emaMercadoReady':True,'rsi':55,'adx':25,'atr':.1,'obv':30,'obvEma':20,'obvPrevious':10,'hasVolume':True}
        bar={'close':5,'low':4.5}
        selected=['ema_mercado','rsi','adx','obv']
        r=combined_decision(bar,ind,selected)
        self.assertEqual(r['action'],'BUY');self.assertEqual(r['total'],5)
        self.assertEqual(combined_decision(bar,ind,selected+['ema'])['total'],5)
        self.assertEqual(combined_decision(bar,{**ind,'emaM2':.5},selected)['action'],'WAIT')


class NewAssetsTests(unittest.TestCase):
    def test_instruments_symbols_and_real_data_contract(self):
        for key in ('BTC','ETH'):
            self.assertEqual(INSTRUMENTS[key]['symbol'],key+'-USD')
            self.assertEqual(INSTRUMENTS[key]['kind'],'crypto')
            rows=demo_bars(key,'1h');r=analyze(rows,timeframe='1h',tools=['ema_mercado','rsi','adx','obv'])
            self.assertEqual(r['timeframe'],'1h');self.assertEqual(r['selectedTools'][0],'ema_mercado')
            self.assertIn('emaM3',r['indicators'][-1])

    def test_news_matching_does_not_confuse_assets_or_substrings(self):
        self.assertTrue(matches('BTC','Bitcoin BTC rally'));self.assertFalse(matches('BTC','XRP oil rally'))
        self.assertTrue(matches('ETH','Ethereum upgrade'));self.assertTrue(matches('ETH','Ether ETFs'))
        self.assertFalse(matches('ETH','Whether the weather improves'));self.assertFalse(matches('ETH','Bitcoin rally'))

    def test_new_assets_in_alerts_journal_and_forecasts(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'INWESTAPP_DATA_DIR':root}):
            for key in ('BTC','ETH'):
                user_data.add_alert({'instrument':key,'direction':'above','price':1})
                now=user_data.now_iso()
                user_data.save_trade({'instrument':key,'quantity':.25,'entry_price':100,'entry_at':now,'exit_price':110,'exit_at':now,'fees':.5})
                user_data.save_forecast({'instrument':key,'analyst':'Test','target_price':120,'issued_at':now,'horizon_days':90,'source_url':'https://example.com/test'})
            quotes=[{'instrument':key,'price':100,'status':'ok','currency':'USD','timestamp':time.time()-150,'asOf':user_data.now_iso(),'provider':'test'} for key in ('BTC','ETH')]
            self.assertEqual(user_data.evaluate_alerts(quotes),[]) # Crypto age gate is 120s.
            events=user_data.evaluate_alerts([{**q,'timestamp':time.time()} for q in quotes]);self.assertEqual(len(events),2)
            self.assertEqual(user_data.journal()['summary']['realized'],4)
            self.assertEqual(user_data.forecast_summary('BTC',90)['basisSymbol'],'BTC-USD')
            self.assertEqual(user_data.forecast_summary('ETH',90)['activeCount'],1)


class BxtrenderTests(unittest.TestCase):
    def test_reference_values_from_independent_closed_form_calculation(self):
        # Reference calculated with 45-digit Decimal precision using EMA's
        # closed-form weighted sum and Wilder's weighted gain/loss sum.
        from custom_indicators import bxtrender_indicators
        values=[100+(i%11)*3-i//7 for i in range(100)]
        actual=bxtrender_indicators(values)
        expected={15:(-.5163316614528543,31.53575019793213,-.5163316614528543),
                  35:(-9.156476887656313,5.480016200508046,.9209288079336505),
                  99:(-1.2009420568940876,-4.003663892123911,5.386216878416545)}
        self.assertTrue(all(r['bxShort'] is None for r in actual[:15]))
        for i,row in expected.items():
            for key,value in zip(('bxShort','bxLong','bxT3'),row):self.assertAlmostEqual(actual[i][key],value,places=9)

    def test_rsi_seed_extremes_and_missing_history(self):
        from custom_indicators import rsi_wilder
        self.assertEqual(rsi_wilder([10,12,11,14],3)[:3],[None]*3)
        self.assertAlmostEqual(rsi_wilder([10,12,11,14],3)[3],100-100/(1+5),places=12)
        self.assertEqual(rsi_wilder([5,4,3,2],3),[None,None,None,0])
        self.assertEqual(rsi_wilder([2]*4,3),[None,None,None,100])
        self.assertEqual(rsi_wilder([None,None,10,11,12,13],3),[None,None,None,None,None,100])

    def test_confirmation_points_use_only_closed_past_and_current_values(self):
        from custom_indicators import bxtrender_indicators
        close=[100+(i%11)*3-i//7 for i in range(250)]
        full=bxtrender_indicators(close)
        self.assertTrue(any(r['bxTurnUp'] for r in full));self.assertTrue(any(r['bxTurnDown'] for r in full))
        for i,r in enumerate(full):
            if r['bxTurnUp'] or r['bxTurnDown']:
                a,b,c=[full[j]['bxT3'] for j in (i-2,i-1,i)]
                self.assertEqual(r['bxTurnUp'],c>b and b<a)
                self.assertEqual(r['bxTurnDown'],c<b and b>a)
                self.assertEqual(full[:i+1],bxtrender_indicators(close[:i+1]))

    def test_t3_constant_and_pine_histogram_colors(self):
        from custom_indicators import tillson_t3,histogram_color
        for value in tillson_t3([None]*15+[7]*30):
            if value is not None:self.assertAlmostEqual(value,7)
        for value,prev,color in [(2,1,'#00ff00'),(1,2,'#228b22'),(-1,-2,'#ff0000'),(-2,-1,'#8b0000')]:
            self.assertEqual(histogram_color(value,prev),color)
        self.assertIsNone(histogram_color(None,1))

    def test_conflicting_components_and_zero_are_neutral(self):
        from technical_tools import tool_reading
        for short,long,state in [(3,4,'bull'),(-3,-4,'bear'),(-3,4,'neutral'),(0,4,'neutral'),(None,4,'missing')]:
            ind={'bxShort':short,'bxLong':long,'bxT3':1}
            self.assertEqual(tool_reading('bxtrender',{'close':100},ind,'trend')['state'],state)

    def test_combination_and_backtest_use_the_selected_tools(self):
        from technical_tools import PRESETS
        from analysis_engine import backtest
        for key in ('BTC','ETH'):
            result=analyze(demo_bars(key,'1h'),timeframe='1h',tools=PRESETS['mercado_bx']['tools'])
            self.assertEqual(result['backtest'],backtest(result['bars'],result['indicators'],tools=PRESETS['mercado_bx']['tools']))
            self.assertEqual(result['decision']['total'],5)
            self.assertIn('bxtrender',[c['id'] for c in result['decision']['checks']])
