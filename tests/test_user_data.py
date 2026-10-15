import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

import user_data as db


def stamp(days=0):return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
def quote(key='XRP',value=2,age=0):return {'instrument':key,'status':'ok','price':value,'timestamp':time.time()-age,'asOf':stamp(),'provider':'test','currency':'USD','stale':age>120}
def trade(**changes):return dict({'instrument':'XRP','quantity':10,'entry_price':2,'entry_at':stamp(2),'exit_price':3,'exit_at':stamp(1),'fees':1},**changes)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.temp.name});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()

    def test_alert_fires_once_and_rearms(self):
        a=db.add_alert({'instrument':'XRP','direction':'above','price':2})
        self.assertEqual(db.evaluate_alerts([quote(value=1.9)]),[])
        self.assertEqual(len(db.evaluate_alerts([quote()])),1)
        self.assertEqual(db.evaluate_alerts([quote()]),[])
        self.assertEqual(db.list_alerts()['alerts'][0]['enabled'],0)
        db.rearm_alert(a['id']);self.assertEqual(len(db.evaluate_alerts([quote()])),1)
        self.assertEqual(len(db.list_alerts()['events']),2)

    def test_alert_concurrent_polls_do_not_duplicate(self):
        db.add_alert({'instrument':'XRP','direction':'below','price':3})
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda _:db.evaluate_alerts([quote()]),range(5)))
        self.assertEqual(sum(map(len,results)),1)
        self.assertEqual(len(db.list_alerts()['events']),1)

    def test_alert_rejects_stale_failed_future_or_wrong_currency(self):
        db.add_alert({'instrument':'XRP','direction':'above','price':1})
        for q in [quote(age=121),quote(age=-61),{**quote(),'status':'error'},{**quote(),'currency':'EUR'}]:self.assertEqual(db.evaluate_alerts([q]),[])
        db.add_alert({'instrument':'GOLD','direction':'above','price':1})
        self.assertEqual(len(db.evaluate_alerts([quote('GOLD',age=900)])),1)
        db.rearm_alert(next(a['id'] for a in db.list_alerts()['alerts'] if a['instrument']=='GOLD'))
        self.assertEqual(db.evaluate_alerts([quote('GOLD',age=1201)]),[])

    def test_realized_long_short_multiplier_and_costs(self):
        db.save_trade(trade()) # +9
        db.save_trade(trade(direction='short',entry_price=4,exit_price=3,multiplier=5,fees=2)) # +48
        result=db.journal();self.assertEqual(result['summary']['realized'],57)
        self.assertEqual(result['summary']['winRate'],100)
        self.assertEqual(result['summary']['closed'],2)

    def test_open_missing_and_stale_values_are_explicit(self):
        db.save_trade(trade(exit_price=None,exit_at=None))
        self.assertIsNone(db.journal()['summary']['unrealized'])
        self.assertEqual(db.journal([quote(value=1)])['summary']['unrealized'],-11)
        self.assertEqual(db.journal([quote(value=1,age=200)])['summary']['staleQuotes'],1)
        self.assertIsNone(db.journal([{**quote(),'status':'error'}])['summary']['unrealized'])

    def test_edit_close_delete_and_persistent_export(self):
        saved=db.save_trade(trade(exit_price=None,exit_at=None,stop_price=1,target_price=4))
        r=db.journal([quote()])['trades'][0];self.assertEqual(r['planned_risk'],11);self.assertEqual(r['planned_reward'],19)
        db.save_trade(trade(),saved['id']);self.assertEqual(db.journal()['summary']['realized'],9)
        self.assertEqual(len(db.export_data()['tables']['trades']),1)
        db.delete_record('trades',saved['id']);self.assertEqual(db.raw_records('trades'),[])

    def test_invalid_trade_values_and_dates(self):
        for changes in [{'quantity':-1},{'fees':'nan'},{'entry_at':stamp(-2)},{'exit_at':stamp(4)},{'stop_price':3},{'target_price':1},{'multiplier':float('inf')},{'direction':'bad'}]:
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):db.save_trade(trade(**changes))

    def forecast(self,**changes):
        return db.save_forecast(dict({'instrument':'XRP','analyst':'Example Bank','target_price':3,'issued_at':stamp(1),'horizon_days':90,'source_url':'https://example.com/research'},**changes))

    def test_forecasts_deduplicate_author_and_filter_age_horizon(self):
        self.forecast(issued_at=stamp(2),target_price=2)
        self.forecast(analyst=' EXAMPLE   bank ',target_price=4)
        self.forecast(analyst='Second',target_price=6)
        self.forecast(analyst='Old',issued_at=stamp(31),target_price=100)
        self.forecast(analyst='Other horizon',horizon_days=180,target_price=99)
        r=db.forecast_summary('XRP',90,quote());self.assertEqual(r['activeCount'],2);self.assertEqual(r['medianTarget'],5);self.assertEqual(r['expectedChangePct'],150)
        self.assertEqual(r['kind'],'user_verified_targets')
        self.assertIsNone(db.forecast_summary('XRP',90,quote(age=200))['expectedChangePct'])
        self.assertIsNone(db.forecast_summary('XRP',90)['expectedChangePct'])

    def test_forecasts_do_not_invent_defaults_and_require_attribution(self):
        r=db.forecast_summary('XRP',90,quote());self.assertEqual(r['activeCount'],0);self.assertIsNone(r['expectedChangePct'])
        for changes in [{'analyst':''},{'source_url':'javascript:alert(1)'},{'source_url':'https://user:password@example.com'},{'horizon_days':7},{'issued_at':stamp(-1)}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.forecast(**changes)
