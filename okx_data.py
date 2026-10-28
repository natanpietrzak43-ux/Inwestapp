"""Read-only OKX spot/perpetual market data. No account or order endpoints.

USDT prices remain USDT. Closed candles only; gaps are never filled. A bounded
history cache makes subsequent requests incremental instead of reloading pages.
"""
import json
import math
import threading
import time
import urllib.parse
import urllib.request
import network_guard
from instrument_catalog import CRYPTO
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://www.okx.com'
SYMBOLS = {key: key+'-USDT' for key in CRYPTO}
BARS = {'15m':'15m','30m':'30m','1h':'1H','2h':'2H','4h':'4H','1d':'1Dutc'}
SECONDS = {'15m':900,'30m':1800,'1h':3600,'2h':7200,'4h':14400,'1d':86400}
MAX_BARS = 5000
_LOCKS = {(key,tf):threading.Lock() for key in SYMBOLS for tf in BARS}
CACHE_DIR = Path(__file__).parent / '.cache' / 'okx'


def symbol(key,market='spot'):
    if key not in SYMBOLS:raise ValueError('Wybierz kryptowalutę z katalogu OKX / USDT.')
    if market not in ('spot','perpetual'):raise ValueError('Nieprawidłowy rynek OKX.')
    return SYMBOLS[key]+('-SWAP' if market=='perpetual' else '')


def number(value, positive=True):
    if isinstance(value,bool):raise ValueError('Nieprawidłowa liczba z OKX.')
    n=float(value)
    if not math.isfinite(n) or (n<=0 if positive else n<0):raise ValueError('Nieprawidłowa liczba z OKX.')
    return n


def request(path,params):
    # Paths are internal constants, never accepted from remote research or forms.
    req=urllib.request.Request(BASE+path+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'Inwestapp/1.6','Accept':'application/json'})
    payload=network_guard.read_json(req)
    if payload.get('code')!='0' or not isinstance(payload.get('data'),list):raise ValueError('OKX nie udostępnił poprawnych danych rynkowych.')
    return payload['data']


def ticker(key,market='spot'):
    inst=symbol(key,market);rows=request('/api/v5/market/ticker',{'instId':inst})
    if len(rows)!=1 or rows[0].get('instId')!=inst:raise ValueError('Nieprawidłowy instrument z OKX.')
    q=rows[0];bid=number(q['bidPx']);ask=number(q['askPx']);stamp=number(q['ts'])/1000
    if bid>ask or not 0<=time.time()-stamp<=120:raise ValueError('Nieprawidłowy spread lub nieaktualny czas OKX.')
    result={'provider':'OKX','source':'okx','sourceSymbol':inst,'currency':'USDT','price':number(q['last']),
            'bid':bid,'ask':ask,'timestamp':stamp,'timingType':'exchange','delaySeconds':0,'marketState':'continuous'}
    if market=='perpetual':
        marks=request('/api/v5/public/mark-price',{'instType':'SWAP','instId':inst})
        if len(marks)!=1 or marks[0].get('instId')!=inst:raise ValueError('Brak poprawnego mark price kontraktu.')
        mark=marks[0];mark_stamp=number(mark['ts'])/1000
        if not 0<=time.time()-mark_stamp<=120:raise ValueError('Nieaktualny mark price kontraktu.')
        result.update(markPrice=number(mark['markPx']),markTimestamp=mark_stamp,market=market)
    return result


def _decode(row,tf,now,market='spot'):
    if not isinstance(row,list) or len(row)<9 or row[8] not in ('0','1'):raise ValueError('Nieprawidłowa świeca OKX.')
    ts=number(row[0])/1000
    if ts%SECONDS[tf]!=0:raise ValueError('Świeca OKX nie leży na granicy interwału UTC.')
    if row[8]=='0':return None
    if ts+SECONDS[tf]>now:raise ValueError('OKX oznaczył przyszłą świecę jako zakończoną.')
    values=[number(x) for x in row[1:5]];op,high,low,close=values
    if not low<=min(op,close)<=max(op,close)<=high:raise ValueError('Nieprawidłowy zakres OHLC z OKX.')
    date=datetime.fromtimestamp(ts,timezone.utc)
    return {'date':date.strftime('%Y-%m-%d') if tf=='1d' else date.isoformat(),
            **dict(zip(('open','high','low','close'),values)),'volume':number(row[6] if market=='perpetual' else row[5],False)}


def candles(key,tf='1h',market='spot'):
    inst=symbol(key,market)
    if tf not in BARS:raise ValueError('Nieprawidłowy interwał OKX.')
    with _LOCKS[(key,tf)]:
        path=CACHE_DIR/(inst+'-'+tf+'.json');cached=None
        try:
            cached=json.loads(path.read_text());rows=cached['bars']
            if cached.get('schema')!=1 or cached.get('symbol')!=inst or cached.get('timeframe')!=tf:cached=None
            if cached and 0<=time.time()-cached['savedAt']<30:return rows,cached['fetchedAt']
        except (OSError,ValueError,KeyError,TypeError):cached=None
        history={r['date']:r for r in cached['bars']} if cached else {}
        prior_last=max(history) if history else None;cursor=None;now=time.time();seen=set()
        target=min(MAX_BARS,max(400,int(180*86400/SECONDS[tf])))
        for _ in range(52):
            params={'instId':inst,'bar':BARS[tf],'limit':'100'}
            if cursor is not None:params['after']=str(cursor)
            page=request('/api/v5/market/history-candles',params)
            if not page:break
            oldest=min(int(number(r[0])) for r in page)
            if cursor is not None and oldest>=cursor:raise ValueError('Paginacja OKX nie przesuwa historii wstecz.')
            reached=False
            for raw in page:
                bar=_decode(raw,tf,now,market)
                if bar is None:continue
                date=bar['date']
                if date in seen and history[date]!=bar:raise ValueError('Sprzeczne duplikaty świec z OKX.')
                seen.add(date);history[date]=bar
                if prior_last and date<=prior_last:reached=True
            if reached or len(seen)>=target or len(page)<100:break
            cursor=oldest;time.sleep(.12)  # at most ~8 requests/s, below public history limit
        rows=sorted(history.values(),key=lambda x:x['date'])[-target:]
        if len(rows)<220:raise ValueError('OKX nie zwrócił co najmniej 220 zamkniętych świec.')
        # A failed request above never returns old cache as a successful update.
        fetched=datetime.now(timezone.utc).isoformat();result={'schema':1,'symbol':inst,'timeframe':tf,'savedAt':time.time(),'fetchedAt':fetched,'bars':rows}
        try:
            CACHE_DIR.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result));temp.replace(path)
        except OSError:pass  # storage failure does not invent a market-data failure
        return rows,fetched
