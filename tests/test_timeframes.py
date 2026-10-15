import unittest
from datetime import datetime,timedelta,timezone
from analysis_engine import validate_bars
from server import demo_bars
from timeframes import TIMEFRAMES,aggregate_hours,candle_closed

class TimeframeTests(unittest.TestCase):
    def test_all_intervals_preserve_distinct_candle_times(self):
        for tf in TIMEFRAMES:
            rows=validate_bars(demo_bars('XRP',tf),tf)
            self.assertEqual(len({r['date'] for r in rows}),len(rows))
            self.assertEqual('T' in rows[0]['date'],tf!='1d')

    def test_aggregation_ohlcv_utc_and_unclosed_bucket(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[{'date':(start+timedelta(hours=i)).isoformat(),'open':10+i,'high':12+i,'low':9+i,'close':11+i,'volume':i+1} for i in range(7)]
        now=start+timedelta(hours=7,minutes=30)
        h2=aggregate_hours(rows,'2h',now);self.assertEqual(len(h2),3)
        self.assertEqual([h2[0][k] for k in ('open','high','low','close','volume')],[10,13,9,12,3])
        h4=aggregate_hours(rows,'4h',now);self.assertEqual(len(h4),1);self.assertEqual(h4[0]['volume'],10)
        self.assertEqual(len(aggregate_hours(rows[1:],'2h',now)),2)

    def test_session_gaps_are_not_filled_with_synthetic_volume(self):
        rows=[{'date':f'2026-01-01T0{i}:00:00Z','open':1,'high':2,'low':.5,'close':1.5,'volume':3} for i in (0,1,3)]
        r=aggregate_hours(rows,'4h',datetime(2026,1,2,tzinfo=timezone.utc))
        self.assertEqual(len(r),1);self.assertEqual(r[0]['volume'],9)

    def test_m15_candle_closes_at_boundary(self):
        self.assertFalse(candle_closed('2026-01-01T12:00:00Z','15m',datetime(2026,1,1,12,14,tzinfo=timezone.utc)))
        self.assertTrue(candle_closed('2026-01-01T12:00:00Z','15m',datetime(2026,1,1,12,15,tzinfo=timezone.utc)))
