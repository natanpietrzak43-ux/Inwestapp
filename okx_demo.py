"""Demo-only OKX authenticated transport. No live mode or arbitrary endpoints."""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

BASE='https://www.okx.com'
NAMES=('OKX_DEMO_API_KEY','OKX_DEMO_API_SECRET','OKX_DEMO_PASSPHRASE')
GET={'/api/v5/account/config','/api/v5/account/balance','/api/v5/account/positions','/api/v5/account/trade-fee',
     '/api/v5/trade/order','/api/v5/trade/orders-pending','/api/v5/trade/orders-algo-pending','/api/v5/trade/fills',
     '/api/v5/public/time','/api/v5/public/instruments','/api/v5/public/position-tiers'}
GET.update({'/api/v5/market/ticker','/api/v5/public/mark-price'})
POST={'/api/v5/trade/order','/api/v5/trade/cancel-order','/api/v5/trade/order-algo','/api/v5/trade/cancel-algos','/api/v5/account/set-leverage'}


class ApiError(ValueError):
    def __init__(self,code):self.code=str(code);super().__init__('OKX Demo odrzuciło żądanie (kod '+self.code+').')


class UnknownOutcome(ValueError):pass


def credentials():
    values={k:os.environ.get(k,'').strip() for k in NAMES}
    if all(values.values()):return tuple(values[k] for k in NAMES)
    from user_data import data_dir
    path=data_dir()/'private'/'okx-demo.json'
    try:
        import secure_store
        raw=secure_store.read(path)
        if raw.get('environment')!='demo':raise ValueError('Plik musi dotyczyć środowiska demo.')
        return tuple(str(raw.get(k,'')).strip() for k in ('key','secret','passphrase'))
    except FileNotFoundError:return ('','','')
    except (OSError,json.JSONDecodeError):raise ValueError('Nie można odczytać prywatnej konfiguracji OKX Demo.') from None


def configured():
    try:return all(credentials())
    except ValueError:return False


def sign(secret,timestamp,method,path,body=''):
    return base64.b64encode(hmac.new(secret.encode(),(timestamp+method+path+body).encode(),hashlib.sha256).digest()).decode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Client:
    environment='demo'
    def __init__(self):self.offset=None;self.synced=0
    def sync_time(self):
        start=time.monotonic()
        request=urllib.request.Request(BASE+'/api/v5/public/time',headers={'x-simulated-trading':'1','User-Agent':'Inwestapp/2.0'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=10) as r:payload=json.loads(r.read(16384))
            if payload.get('code')!='0':raise ValueError()
            server=float(payload['data'][0]['ts'])/1000
            elapsed=time.monotonic()-start
            if elapsed>5:raise ValueError()
            self.offset=server+elapsed/2-time.time();self.synced=time.monotonic()
        except Exception:raise ValueError('Nie potwierdzono czasu OKX Demo; brak nowych zleceń.') from None
    def request(self,method,path,params=None):
        method=method.upper()
        if method not in ('GET','POST') or path not in (GET if method=='GET' else POST):raise ValueError('Endpoint niedozwolony w kliencie demo.')
        key,secret,passphrase=credentials()
        public=path.startswith(('/api/v5/public/','/api/v5/market/'))
        if not public and not all((key,secret,passphrase)):raise ValueError('Brak kluczy OKX Demo. Skonfiguruj je poza czatem i repozytorium.')
        if self.offset is None or time.monotonic()-self.synced>60:self.sync_time()
        query='?'+urllib.parse.urlencode(params) if method=='GET' and params else ''
        body=json.dumps(params,separators=(',',':'),allow_nan=False) if method=='POST' else ''
        stamp=datetime.fromtimestamp(time.time()+self.offset,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'Inwestapp/2.0','x-simulated-trading':'1'}
        if not public:headers.update({'OK-ACCESS-KEY':key,'OK-ACCESS-PASSPHRASE':passphrase,'OK-ACCESS-TIMESTAMP':stamp,'OK-ACCESS-SIGN':sign(secret,stamp,method,path+query,body)})
        req=urllib.request.Request(BASE+path+query,data=body.encode() if body else None,headers=headers,method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError()
            result=json.loads(raw)
        except urllib.error.HTTPError as error:
            if method=='POST' and error.code>=500:raise UnknownOutcome('Nieznany wynik żądania demo; wymagane uzgodnienie stanu.') from None
            raise ApiError('HTTP'+str(error.code)) from None
        except (OSError,ValueError):raise UnknownOutcome('Brak potwierdzenia OKX Demo; nie powtarzaj zlecenia bez odczytu jego stanu.') from None
        if result.get('code')!='0':raise ApiError(result.get('code','unknown'))
        rows=result.get('data')
        if not isinstance(rows,list):raise UnknownOutcome('Nieprawidłowa odpowiedź OKX Demo.')
        if method=='POST':
            for row in rows:
                if row.get('sCode','0')!='0':raise ApiError(row['sCode'])
        return rows
