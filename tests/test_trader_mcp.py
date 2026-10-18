import io
import json
import unittest
from unittest.mock import patch,MagicMock
import trader_mcp as mcp


class Response(io.BytesIO):
    def __init__(self,raw,headers=None):super().__init__(raw);self.headers=headers or {'Content-Type':'application/json'}


class McpTests(unittest.TestCase):
    def setUp(self):
        self.key=patch('trader_mcp.credential',return_value='private-test-key');self.key.start();self.block=patch('trader_mcp.access_block',return_value=None);self.block.start()
    def tearDown(self):self.block.stop();self.key.stop()

    def test_credentials_and_query_keys_are_redacted_recursively(self):
        value={'api_key':'secret','message':'https://mcp.trader.dev/mcp?key=private-test-key&x=1','nested':['private-test-key']}
        result=mcp.sanitize(value);self.assertNotIn('api_key',result);self.assertNotIn('private-test-key',json.dumps(result));self.assertIn('[REDACTED]',result['message'])

    def test_known_provider_block_does_not_retry_network(self):
        with patch('trader_mcp.access_block',return_value={'blocked':True,'error':'Cloudflare 1010','code':1010}),patch('trader_mcp.urllib.request.build_opener') as transport:
            self.assertFalse(mcp.status()['connected'])
            with self.assertRaises(ValueError):mcp.Client().initialize()
            transport.assert_not_called()

    def test_json_protocol_and_session_header(self):
        response=Response(json.dumps({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-03-26'}}).encode(),{'Content-Type':'application/json','Mcp-Session-Id':'session-one'})
        opener=MagicMock();opener.open.return_value=response
        with patch('trader_mcp.urllib.request.build_opener',return_value=opener):
            c=mcp.Client();r=c.request('initialize',{});self.assertEqual(c.session,'session-one');self.assertEqual(r['protocolVersion'],'2025-03-26')
        req=opener.open.call_args.args[0];self.assertTrue(req.full_url.startswith(mcp.ENDPOINT+'?key='));self.assertEqual(json.loads(req.data)['method'],'initialize')

    def test_sse_only_returns_matching_request_id(self):
        raw=b'data: {"jsonrpc":"2.0","method":"notification"}\n\ndata: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'
        opener=MagicMock();opener.open.return_value=Response(raw,{'Content-Type':'text/event-stream'})
        with patch('trader_mcp.urllib.request.build_opener',return_value=opener):self.assertEqual(mcp.Client().request('tools/list',{}),{'tools':[]})

    def test_write_tools_and_unknown_names_are_not_research(self):
        for name in ('place_order','delete_strategy','deploy_strategy','subscribe_strategy','execute_trade_strategy'):
            self.assertFalse(mcp.research_tool({'name':name,'description':'strategy','annotations':{'readOnlyHint':True}}))
        self.assertTrue(mcp.research_tool({'name':'search_strategies','description':'Find strategies'}))
        self.assertFalse(mcp.research_tool({'name':'run_backtest','description':'strategy creates a job'}))
        self.assertFalse(mcp.research_tool({'name':'get_balance','description':'account balance'}))

    def test_remote_tool_error_is_not_stored_as_success(self):
        with patch.object(mcp.Client,'initialize'),patch.object(mcp.Client,'tools',return_value=[{'name':'get_strategy','inputSchema':{'required':['id']}}]),patch.object(mcp.Client,'request',return_value={'isError':True}):
            with self.assertRaises(ValueError):mcp.fetch_research('get_strategy',{'id':'x'})
            with self.assertRaises(ValueError):mcp.fetch_research('get_strategy',{})
            with self.assertRaises(ValueError):mcp.fetch_research('execute_trade',{})

    def test_no_redirect_forwards_the_query_credential(self):
        self.assertIsNone(mcp.NoRedirect().redirect_request(None,None,None,None,None,None))


class BridgeTests(unittest.TestCase):
    def test_bridge_redacts_key_in_stdout_and_stderr(self):
        import os,subprocess,tempfile,shutil
        from pathlib import Path
        if not shutil.which('node'):self.skipTest('Node unavailable')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bridge=root/'bridge.cjs';bridge.write_bytes((Path(__file__).parents[1]/'tools/trader_mcp_bridge.cjs').read_bytes())
            stub=root/'npx';stub.write_text('#!/bin/sh\nprintf \'{"message":"https://mcp.trader.dev/mcp?key=private-test-key"}\\n\'\nprintf \'stderr private-test-key\\n\' >&2\n');stub.chmod(0o700)
            process=subprocess.run(['node',str(bridge)],env={**os.environ,'PATH':str(root)+os.pathsep+os.environ['PATH'],'TRADER_DEV_API_KEY':'private-test-key'},capture_output=True,text=True,timeout=5)
            self.assertEqual(process.returncode,0);self.assertNotIn('private-test-key',process.stdout+process.stderr);self.assertIn('[REDACTED]',process.stdout);self.assertIn('[REDACTED]',process.stderr)
