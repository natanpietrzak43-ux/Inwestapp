import io
import json
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch

import launch
from app_release import APP_VERSION,FEATURES


class LauncherTests(unittest.TestCase):
    def test_shipped_installation_is_complete(self):
        self.assertEqual(launch.installation_errors(),[])

    def test_missing_chart_and_mixed_html_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in (*launch.REQUIRED,*('web/'+n for n in launch.STATIC_PATHS.values())):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
            (root/'web/index.html').write_text('<html data-ui-version="1.6">')
            (root/'web/chart.js').unlink()
            errors=launch.installation_errors(root)
            self.assertTrue(any('chart.js' in e for e in errors));self.assertTrue(any('roznych wersji' in e for e in errors))

    def test_old_server_blocks_new_worker_and_is_never_opened(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':'1.6','status':'ok'}),patch('launch.subprocess.call') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launch.main([]),3)
        spawn.assert_not_called();browser.assert_not_called();self.assertIn('1.6',output.getvalue());self.assertIn('Ctrl+C',output.getvalue());self.assertIn('NIE zostala uruchomiona',output.getvalue())

    def test_unknown_program_on_port_is_not_killed_or_replaced(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value=None),patch('launch.subprocess.call') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),3)
        spawn.assert_not_called();browser.assert_not_called()

    def test_matching_existing_release_opens_without_second_worker(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':APP_VERSION,'features':FEATURES}),patch('launch.subprocess.call') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),0)
        spawn.assert_not_called();browser.assert_called_once_with('http://127.0.0.1:8000/?v='+APP_VERSION)

    def test_same_version_without_feature_contract_is_not_reused(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':APP_VERSION}),patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),3)
        browser.assert_not_called()

    def test_free_port_starts_checked_server_with_exact_python_and_directory(self):
        with patch('launch.port_busy',return_value=False),patch('launch.subprocess.call',return_value=0) as spawn,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main(['--port','8123']),0)
        self.assertEqual(spawn.call_args.args[0],[launch.sys.executable,str(launch.ROOT/'server.py'),'--port','8123','--open-browser']);self.assertEqual(spawn.call_args.kwargs['cwd'],launch.ROOT)

    def test_reads_version_from_actual_local_health_endpoint(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw=json.dumps({'status':'ok','version':'1.6','instruments':['XRP','XLM']}).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.assertTrue(launch.port_busy(server.server_port));self.assertEqual(launch.running_release(server.server_port)['version'],'1.6')
            result=subprocess.run([sys.executable,str(launch.ROOT/'launch.py'),'--port',str(server.server_port)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,3);self.assertIn('Inwestapp 1.6',result.stdout);self.assertIn('NIE zostala uruchomiona',result.stdout)
        finally:server.shutdown();server.server_close();thread.join()
