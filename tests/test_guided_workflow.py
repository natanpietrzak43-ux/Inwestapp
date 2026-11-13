import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import backtest_jobs as jobs
import exchange_health
import execution_context
import paper_bot
from server import demo_bars,normalize_backtest,run_historical_test
from user_data import data_dir,export_data


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'INWESTAPP_DATA_DIR':self.temp.name});self.env.start()
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.env.stop);self.addCleanup(jobs.shutdown)

    def join(self,identifier):
        with jobs.LOCK:worker=jobs.WORKERS.get(identifier)
        if worker:worker[1].join(timeout=15);self.assertFalse(worker[1].is_alive())
        return jobs.records(identifier)

    def test_background_full_test_persists_report_and_does_not_mutate_account(self):
        cfg=normalize_backtest({'instrument':'XLM','mode':'demo','source':'okx','history_days':30},True)
        before=paper_bot.status()['state']
        job=jobs.submit(cfg,run_historical_test);result=self.join(job['id'])
        self.assertEqual(result['state'],'completed');report=paper_bot.backtest_record(result['report_id'])
        self.assertTrue(report['historicalGuardReplayed']);self.assertTrue(report['demo']);self.assertEqual(report['instrument'],'XLM')
        self.assertEqual(paper_bot.status()['state'],before);self.assertIn('backtest_jobs',export_data()['tables'])

    def test_one_simulation_at_a_time_and_cooperative_cancel(self):
        started=threading.Event();release=threading.Event()
        def worker(cfg,phase):
            phase('Odtwarzanie');started.set();release.wait(5);execution_context.check_cancelled();return {'id':'should-not-save'}
        job=jobs.submit(normalize_backtest({},True),worker);self.assertTrue(started.wait(2))
        with self.assertRaisesRegex(ValueError,'Trwa już'):jobs.submit(normalize_backtest({},True),worker)
        jobs.cancel(job['id']);release.set();result=self.join(job['id'])
        self.assertEqual(result['state'],'cancelled');self.assertIsNone(result['report_id']);self.assertEqual(paper_bot.backtest_records(),[])

    def test_restart_marks_incomplete_job_without_automatic_execution(self):
        started=threading.Event();release=threading.Event()
        def worker(cfg,phase):started.set();release.wait(3);execution_context.check_cancelled();return {'id':'none'}
        job=jobs.submit(normalize_backtest({},True),worker);started.wait(2);jobs.cancel(job['id']);release.set();self.join(job['id'])
        jobs.change(job['id'],state='running',phase='Interrupted process simulation')
        jobs.recover();self.assertEqual(jobs.records(job['id'])['state'],'interrupted');self.assertEqual(jobs.WORKERS,{})

    def test_worker_uses_captured_data_folder_and_hides_unexpected_errors(self):
        seen=[]
        def worker(cfg,phase):seen.append(str(data_dir()));raise RuntimeError('PRIVATE-DATA-DO-NOT-EXPOSE')
        job=jobs.submit(normalize_backtest({},True),worker);result=self.join(job['id'])
        self.assertEqual(seen,[self.temp.name]);self.assertEqual(result['state'],'failed');self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertIsNone(execution_context.root.get());self.assertIsNone(execution_context.cancellation.get())

    def test_input_normalization_strips_unknown_secrets_and_rejects_bad_modes(self):
        cfg=normalize_backtest({'apiKey':'NEVER-STORE','instrument':'BTC','history_days':90},True)
        self.assertNotIn('apiKey',cfg);self.assertEqual(cfg['history_days'],90)
        for change in ({'mode':'csv'},{'mode':'live-orders'},{'start_date':'bad'},{'history_days':999},
                       {'start_date':'2026-11-02','end_date':'2026-11-01'},{'execution_model':'remote-code'},
                       {'market_data':'contract','market':'spot'}):
            with self.subTest(change=change),self.assertRaises(ValueError):normalize_backtest(change,True)

    def test_cancellation_propagates_through_full_replay_and_releases_context(self):
        event=threading.Event();event.set();token=execution_context.cancellation.set(event)
        try:
            with self.assertRaises(execution_context.Cancelled):run_historical_test({'mode':'demo'})
        finally:execution_context.cancellation.reset(token)
        self.assertIsNone(execution_context.cancellation.get());self.assertIsNone(execution_context.root.get())


class ExchangeHealthTests(unittest.TestCase):
    def setUp(self):exchange_health.CACHE=None
    def test_cached_readonly_status_and_expired_success_fails_closed(self):
        now=time.time()
        with patch('exchange_health.time.time',return_value=now),patch('exchange_health.okx_data.request',return_value=[]) as call:
            first=exchange_health.snapshot();second=exchange_health.snapshot()
        self.assertTrue(first['entryAllowed']);self.assertEqual(first,second);call.assert_called_once_with('/api/v5/system/status',{'state':'ongoing'})
        with patch('exchange_health.time.time',return_value=now+61),patch('exchange_health.okx_data.request',side_effect=OSError('unsafe transport detail')):
            failed=exchange_health.snapshot()
        self.assertFalse(failed['entryAllowed']);self.assertFalse(failed['verified']);self.assertNotIn('unsafe',json.dumps(failed))

    def test_ongoing_notice_and_malformed_data_hold_new_entries(self):
        for rows in ([{'title':'Maintenance'}],[None]):
            exchange_health.CACHE=None
            with patch('exchange_health.okx_data.request',return_value=rows):result=exchange_health.snapshot()
            self.assertFalse(result['entryAllowed'])


if __name__=='__main__':unittest.main()
