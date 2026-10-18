"""Read-only strategy research via the user's fixed trader.dev MCP endpoint.

Remote content is data, never executable strategy code. Credentials never enter API output.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime,timezone

ENDPOINT='https://mcp.trader.dev/mcp'
_KNOWN_BLOCK=None


def credential():
    key=os.environ.get('TRADER_DEV_API_KEY','').strip()
    if key:return key
    p=Path.home()/'.codex/trader-dev/api-key'
    try:return p.read_text().strip()
    except OSError:return ''


def sanitize(value):
    key=credential()
    if isinstance(value,str):
        if key:value=value.replace(key,'[REDACTED]')
        return re.sub(r'([?&]key=)[^&\s"<>]+',r'\1[REDACTED]',value)
    if isinstance(value,list):return [sanitize(v) for v in value]
    if isinstance(value,dict):return {sanitize(k):sanitize(v) for k,v in value.items() if k.lower() not in ('apikey','api_key','authorization','accesstoken','access_token')}
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Client:
    def __init__(self):self.key=credential();self.session=None;self.next_id=0;self.version='2025-03-26'

    def request(self,method,params=None,notification=False):
        blocked=access_block()
        if blocked:raise ValueError(blocked['error'])
        if not self.key:raise ValueError('Brak konfiguracji klucza trader.dev. Skonfiguruj globalny MCP lub TRADER_DEV_API_KEY.')
        self.next_id+=1;body={'jsonrpc':'2.0','method':method}
        if params is not None:body['params']=params
        if not notification:body['id']=self.next_id
        headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.version}
        if self.session:headers['Mcp-Session-Id']=self.session
        req=urllib.request.Request(ENDPOINT+'?key='+urllib.parse.quote(self.key,safe=''),data=json.dumps(body).encode(),headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:
                self.session=response.headers.get('Mcp-Session-Id',self.session)
                if notification:return {}
                if 'text/event-stream' in response.headers.get('Content-Type',''):
                    chunks=[];size=0;payload=None
                    while True:
                        line=response.readline(2_000_001);size+=len(line)
                        if size>2_000_000:raise ValueError('Odpowiedź MCP jest za duża.')
                        if not line:break
                        if line.startswith(b'data:'):chunks.append(line[5:].strip())
                        elif not line.strip() and chunks:
                            candidate=json.loads(b'\n'.join(chunks));chunks=[]
                            if candidate.get('id')==body['id']:payload=candidate;break
                    if payload is None:raise ValueError('MCP nie zwrócił odpowiedzi na żądanie.')
                else:
                    raw=response.read(2_000_001)
                    if len(raw)>2_000_000:raise ValueError('Odpowiedź MCP jest za duża.')
                    payload=json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:detail=json.loads(exc.read(3000))
            except (ValueError,OSError):detail={}
            if detail.get('error_code')==1010:
                global _KNOWN_BLOCK
                _KNOWN_BLOCK={'blocked':True,'code':1010,'error':'trader.dev blokuje ten klient: Cloudflare 1010. Właściciel usługi musi dopuścić dostęp; automatyczne ponawianie wyłączone.'}
                raise ValueError(_KNOWN_BLOCK['error']) from None
            raise ValueError(f'trader.dev: HTTP {exc.code}. Sprawdź dostęp sieciowy i uprawnienia klucza.') from None
        except (OSError,urllib.error.URLError):raise ValueError('Brak połączenia z mcp.trader.dev. Dostęp może blokować sieć środowiska. Rejestracja MCP nie potwierdza połączenia.') from None
        if payload.get('id')!=body['id']:raise ValueError('Nieprawidłowy identyfikator odpowiedzi MCP.')
        if 'error' in payload:raise ValueError('MCP odrzucił żądanie: '+sanitize(str(payload['error'].get('message','błąd protokołu')))[:350])
        result=payload.get('result',{})
        if not isinstance(result,dict):raise ValueError('Nieprawidłowa odpowiedź MCP.')
        return sanitize(result)

    def initialize(self):
        result=self.request('initialize',{'protocolVersion':self.version,'capabilities':{},'clientInfo':{'name':'Inwestapp','version':'1.5.0'}})
        self.version=result.get('protocolVersion',self.version);self.request('notifications/initialized',notification=True)
        return result

    def tools(self):
        result=[];cursor=None
        for _ in range(10):
            page=self.request('tools/list',{'cursor':cursor} if cursor else {})
            result+=page.get('tools',[]);cursor=page.get('nextCursor')
            if not cursor:return result
        raise ValueError('Katalog MCP przekracza limit 10 stron; nie pobrano kompletnej listy.')


def research_tool(tool):
    name=tool.get('name','').lower();description=tool.get('description','').lower()
    if not re.search(r'strateg',name+' '+description):return False
    if re.search(r'order|execute_trade|place_trade|cancel|delete|deploy|payment|subscribe|credential|password|secret|api_key|account',name) or tool.get('annotations',{}).get('destructiveHint') is True:return False
    return tool.get('annotations',{}).get('readOnlyHint') is True or bool(re.match(r'^(search|find|list|get|fetch)[_\-.]',name))


def access_block():
    if _KNOWN_BLOCK:return _KNOWN_BLOCK
    try:
        record=json.loads((Path.home()/'.codex/trader-dev/access-status.json').read_text())
        return record if record.get('blocked') else None
    except (OSError,ValueError):return None


def status():
    blocked=access_block()
    if blocked:return {'configured':bool(credential()),'connected':False,'tools':[],'error':blocked['error'],'blockCode':blocked.get('code'),'checkedAt':blocked.get('checkedAt')}
    if not credential():return {'configured':False,'connected':False,'tools':[],'error':'Brak klucza trader.dev.'}
    try:
        client=Client();info=client.initialize();tools=client.tools()
        return {'configured':True,'connected':True,'server':info.get('serverInfo',{}),'tools':[t for t in tools if research_tool(t)],
                'totalTools':len(tools),'checkedAt':datetime.now(timezone.utc).isoformat(),
                'notice':'Udostępniamy wyłącznie narzędzia badawcze do strategii. Pobranie materiału nie weryfikuje skuteczności strategii.'}
    except (ValueError,TypeError,KeyError) as exc:return {'configured':True,'connected':False,'tools':[],'error':sanitize(str(exc))[:700]}


def fetch_research(name,arguments):
    if not isinstance(name,str) or not isinstance(arguments,dict) or len(json.dumps(arguments))>16000:raise ValueError('Nieprawidłowe argumenty MCP (maks. 16 KB).')
    client=Client();client.initialize();tools=client.tools();tool=next((t for t in tools if t.get('name')==name),None)
    if tool is None or not research_tool(tool):raise ValueError('To narzędzie nie jest dozwolonym narzędziem badawczym strategii.')
    schema=tool.get('inputSchema',{});required=schema.get('required',[])
    if any(k not in arguments for k in required):raise ValueError('Brakuje wymaganych argumentów narzędzia.')
    result=client.request('tools/call',{'name':name,'arguments':arguments})
    if result.get('isError'):raise ValueError('Usługa MCP zgłosiła błąd wykonania narzędzia; materiał nie został zapisany.')
    return {'provider':'trader.dev','tool':name,'arguments':sanitize(arguments),'fetchedAt':datetime.now(timezone.utc).isoformat(),
            'verified':False,'notice':'Zewnętrzny materiał źródłowy. Nie wykonujemy pobranego kodu ani nie potwierdzamy deklarowanych zysków.', 'content':sanitize(result)}
