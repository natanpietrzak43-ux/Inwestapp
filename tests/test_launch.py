import io
import errno
import json
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
import socket
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch

import launch
import local_server
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
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':'1.6','status':'ok'}),patch('launch.subprocess.Popen') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launch.main([]),3)
        spawn.assert_not_called();browser.assert_not_called();self.assertIn('1.6',output.getvalue());self.assertIn('Ctrl+C',output.getvalue());self.assertIn('NIE zostala uruchomiona',output.getvalue())

    def test_unknown_program_on_port_is_not_killed_or_replaced(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value=None),patch('launch.subprocess.Popen') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),3)
        spawn.assert_not_called();browser.assert_not_called()

    def test_matching_existing_release_opens_without_second_worker(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':APP_VERSION,'features':FEATURES}),patch('launch.subprocess.Popen') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),0)
        spawn.assert_not_called();browser.assert_called_once_with('http://127.0.0.1:8000/?v='+APP_VERSION)

    def test_same_version_without_feature_contract_is_not_reused(self):
        with patch('launch.port_busy',return_value=True),patch('launch.running_release',return_value={'version':APP_VERSION}),patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),3)
        browser.assert_not_called()

    def test_free_port_starts_checked_server_with_exact_python_and_directory(self):
        with patch('launch.port_busy',return_value=False),patch('launch.subprocess.Popen') as spawn,redirect_stdout(io.StringIO()):
            spawn.return_value.wait.return_value=0
            self.assertEqual(launch.main(['--port','8123']),0)
        self.assertEqual(spawn.call_args.args[0],[launch.sys.executable,str(launch.ROOT/'server.py'),'--port','8123','--open-browser']);self.assertEqual(spawn.call_args.kwargs['cwd'],launch.ROOT)

    def test_ctrl_c_waits_for_owned_server_shutdown(self):
        with patch('launch.subprocess.Popen') as spawn,redirect_stdout(io.StringIO()):
            child=spawn.return_value;child.wait.side_effect=[KeyboardInterrupt(),0]
            self.assertEqual(launch.run_server(8000),0)
        self.assertEqual(child.wait.call_args.kwargs,{'timeout':50})
        child.terminate.assert_not_called();child.kill.assert_not_called()

    def test_dropped_connection_probe_does_not_report_a_free_port_as_busy(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        with patch('socket.create_connection',side_effect=TimeoutError('probe timed out')) as connect,patch('launch.run_server',return_value=0) as spawn,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main(['--port',str(port)]),0)
        connect.assert_not_called();spawn.assert_called_once()

    def test_permission_error_is_not_mislabeled_as_busy_and_starts_nothing(self):
        error=PermissionError(errno.EACCES,'Access denied');error.winerror=10013
        with patch('launch.port_busy',side_effect=error),patch('launch.running_release',return_value=None),patch('launch.subprocess.Popen') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launch.main([]),4)
        spawn.assert_not_called();browser.assert_not_called()
        self.assertIn('Access denied',output.getvalue());self.assertIn('odmowil dostepu',output.getvalue());self.assertNotIn('jest zajety',output.getvalue())

    def test_exclusive_existing_windows_app_can_be_identified_after_access_denied(self):
        with patch('launch.port_busy',side_effect=PermissionError(errno.EACCES,'Access denied')),patch('launch.running_release',return_value={'version':APP_VERSION,'features':FEATURES}),patch('launch.subprocess.Popen') as spawn,patch('launch.webbrowser.open') as browser,redirect_stdout(io.StringIO()):
            self.assertEqual(launch.main([]),0)
        spawn.assert_not_called();browser.assert_called_once()

    def test_bind_reports_actual_address_in_use_but_propagates_permission_errors(self):
        with patch('local_server.socket.socket') as factory:
            sock=factory.return_value.__enter__.return_value
            sock.bind.side_effect=OSError(errno.EADDRINUSE,'Address in use')
            self.assertTrue(launch.port_busy(8000))
            sock.bind.side_effect=PermissionError(errno.EACCES,'Access denied')
            with self.assertRaises(PermissionError):launch.port_busy(8000)

    def test_windows_bind_uses_exclusive_access_without_reuse(self):
        with patch('local_server.sys.platform','win32'),patch('local_server.socket.SO_EXCLUSIVEADDRUSE',-5,create=True),patch('local_server.socket.socket') as factory:
            sock=factory.return_value.__enter__.return_value
            self.assertFalse(launch.port_busy(8000))
            sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET,-5,1)
            sock.bind.assert_called_once_with(('127.0.0.1',8000))

    def test_windows_address_in_use_code_is_recognized(self):
        error=OSError('Address in use');error.winerror=10048
        self.assertTrue(local_server.address_in_use(error))

    def test_real_server_listener_cannot_be_rebound(self):
        server=local_server.LocalHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler)
        try:
            try:self.assertTrue(launch.port_busy(server.server_port))
            except PermissionError:
                # Windows exclusive listeners may report WSAEACCES instead.
                self.assertEqual(sys.platform,'win32')
            with self.assertRaises(OSError):local_server.LocalHTTPServer(('127.0.0.1',server.server_port),BaseHTTPRequestHandler)
        finally:server.server_close()

    def test_reads_version_from_actual_local_health_endpoint(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw=json.dumps({'status':'ok','version':'1.6','instruments':['XRP','XLM']}).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            try:self.assertTrue(launch.port_busy(server.server_port))
            except PermissionError:self.assertEqual(sys.platform,'win32')
            self.assertEqual(launch.running_release(server.server_port)['version'],'1.6')
            result=subprocess.run([sys.executable,str(launch.ROOT/'launch.py'),'--port',str(server.server_port)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,3);self.assertIn('Inwestapp 1.6',result.stdout);self.assertIn('NIE zostala uruchomiona',result.stdout)
        finally:server.shutdown();server.server_close();thread.join()
