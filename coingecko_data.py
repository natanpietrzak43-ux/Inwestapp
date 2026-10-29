"""Read-only CoinGecko Demo market context; never prices for order execution."""
from collections import deque
from datetime import datetime, timezone
import hashlib
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import network_guard
import secure_store
from instrument_catalog import INSTRUMENTS
from user_data import data_dir, database

BASE = 'https://api.coingecko.com/api/v3'
IDS = {'XRP':'ripple','XLM':'stellar','BTC':'bitcoin','ETH':'ethereum','SOL':'solana',
       'DOGE':'dogecoin','ADA':'cardano','LINK':'chainlink','AVAX':'avalanche-2','DOT':'polkadot',
       'LTC':'litecoin','BCH':'bitcoin-cash','UNI':'uniswap','ATOM':'cosmos','NEAR':'near','SUI':'sui'}
PATHS = {'markets':'/coins/markets','global':'/global','trending':'/search/trending'}
TTL = {'markets':60,'global':300,'trending':900}
_LOCK = threading.RLock()
_CACHE = {}
_ATTEMPTS = deque()
_IDENTITY = None
_COOLDOWN = 0


class FeedError(ValueError):
    """Only application-authored messages may cross the API boundary."""


def api_key():
    key = os.environ.get('COINGECKO_DEMO_API_KEY', '').strip()
    if not key:
        path = data_dir()/'private'/'coingecko.json'
        if not path.exists():return ''
        values = secure_store.read(path)
        if not isinstance(values, dict) or values.get('environment') != 'demo':
            raise ValueError('Konfiguracja CoinGecko musi dotyczyć API Demo.')
        key = values.get('key', '')
    if not isinstance(key, str) or len(key)>256 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise ValueError('Nieprawidłowa prywatna konfiguracja klucza CoinGecko.')
    return key


def monthly_budget():
    try:
        value = int(os.environ.get('COINGECKO_MONTHLY_BUDGET', '9000'))
        if not 100 <= value <= 10_000_000:raise ValueError()
        return value
    except ValueError:
        raise ValueError('COINGECKO_MONTHLY_BUDGET: liczba od 100 do 10000000.') from None


def usage(reserve=False):
    """Local request budget, not an assertion about provider billing/credits."""
    month = datetime.fromtimestamp(time.time(), timezone.utc).strftime('%Y-%m')
    budget = monthly_budget()
    with database() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS coingecko_usage(month TEXT PRIMARY KEY, requests INTEGER NOT NULL)')
        if reserve:conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT requests FROM coingecko_usage WHERE month=?', (month,)).fetchone()
        used = row['requests'] if row else 0
        if reserve:
            if used >= budget:raise FeedError('Osiągnięto miesięczny limit żądań CoinGecko tej aplikacji. Sprawdź plan i budżet API.')
            used += 1
            conn.execute('INSERT INTO coingecko_usage VALUES(?,?) ON CONFLICT(month) DO UPDATE SET requests=excluded.requests', (month, used))
    return {'monthUTC':month, 'requests':used, 'budget':budget, 'remaining':max(0,budget-used),
            'notice':'Licznik żądań tej aplikacji. Nie obejmuje innych klientów ani nie zastępuje limitów i rozliczeń dostawcy.'}


def status():
    try:
        configured = bool(api_key())
        error = None
    except ValueError as exc:
        configured = False;error = str(exc)
    return {'provider':'CoinGecko','environment':'demo','configured':configured,'readOnly':True,
            'error':error,'usage':usage(),'cacheSeconds':TTL,
            'notice':'Ceny zbiorcze w USD do przeglądu rynku. Brak bid/ask, zleceń i użycia w sygnałach bota. Wtyczka czatu nie konfiguruje API aplikacji.'}


def _identity(key):
    global _IDENTITY, _COOLDOWN
    identity = (str(data_dir().resolve()), hashlib.sha256(key.encode()).digest())
    if identity != _IDENTITY:
        _CACHE.clear();_ATTEMPTS.clear();_COOLDOWN = 0;_IDENTITY = identity


def _fetch(kind, key):
    global _COOLDOWN
    if kind not in PATHS:raise ValueError('Niedozwolony endpoint CoinGecko.')
    now = time.time()
    if now < _COOLDOWN:raise FeedError('Przerwa po błędzie lub limicie CoinGecko. Poczekaj przed ponownym pobraniem.')
    while _ATTEMPTS and _ATTEMPTS[0] <= now-60:_ATTEMPTS.popleft()
    if len(_ATTEMPTS)>=5:raise FeedError('Lokalny limit CoinGecko: do 5 żądań na minutę. Poczekaj chwilę.')
    params = {'vs_currency':'usd','ids':','.join(IDS.values()),'order':'market_cap_desc','per_page':'100',
              'page':'1','sparkline':'false','price_change_percentage':'24h,7d,30d'} if kind=='markets' else {}
    url = BASE + PATHS[kind] + ('?'+urllib.parse.urlencode(params) if params else '')
    request = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'Inwestapp/2.2',
                                                  'x-cg-demo-api-key':key})
    usage(reserve=True);_ATTEMPTS.append(now)
    try:
        payload = network_guard.read_json(request)
        if isinstance(payload,dict) and ('error' in payload or isinstance(payload.get('status'),dict) and payload['status'].get('error_code')):
            raise ValueError('CoinGecko nie potwierdził poprawnej odpowiedzi API Demo.')
        return payload
    except urllib.error.HTTPError as exc:
        wait = 60
        if exc.code==429:
            try:wait=max(60,min(3600,int(exc.headers.get('Retry-After','60'))))
            except (ValueError,TypeError):pass
        _COOLDOWN = now+wait
        if exc.code in (401,403):raise FeedError('CoinGecko odrzucił dostęp. Sprawdź klucz Demo API, jego plan i uprawnienia sieci.') from None
        if exc.code==429:raise FeedError('CoinGecko ograniczył liczbę żądań. Pobieranie chwilowo wstrzymane.') from None
        raise FeedError('CoinGecko nie udostępnił danych (HTTP '+str(exc.code)+').') from None
    except (OSError,ValueError):
        _COOLDOWN = now+60
        raise FeedError('Brak potwierdzonych danych CoinGecko. Sprawdź połączenie i konfigurację API; nie podstawiono innych cen.') from None


def number(value, positive=False):
    if isinstance(value,bool):raise ValueError('Nieprawidłowa liczba CoinGecko.')
    result = float(value)
    if not math.isfinite(result) or (positive and result<=0):raise ValueError('Nieprawidłowa liczba CoinGecko.')
    return result


def optional(value, minimum=None, maximum=None):
    if value is None:return None
    result = number(value)
    if minimum is not None and result<minimum or maximum is not None and result>maximum:
        raise ValueError('Wartość CoinGecko poza zakresem.')
    return result


def timestamp(value):
    if isinstance(value,str):
        date = datetime.fromisoformat(value.replace('Z','+00:00'))
        if date.tzinfo is None:raise ValueError('Brak strefy czasu CoinGecko.')
        stamp = date.timestamp()
    else:stamp = number(value,True)
    if not 0<stamp<=time.time()+60:raise ValueError('Nieprawidłowy czas CoinGecko.')
    return stamp


def markets(payload):
    if not isinstance(payload,list):raise ValueError('Nieprawidłowa lista cen CoinGecko.')
    allowed = set(IDS.values());by = {}
    for row in payload:
        if not isinstance(row,dict) or row.get('id') not in allowed or row['id'] in by:
            raise ValueError('Niezgodny lub powtórzony identyfikator CoinGecko.')
        by[row['id']] = row
    result = []
    for key, identifier in IDS.items():
        try:
            row = by[identifier]
            if row.get('symbol','').upper()!=key:raise ValueError('Niezgodny symbol CoinGecko.')
            price = number(row['current_price'],True);stamp = timestamp(row['last_updated'])
            ath = optional(row.get('ath'),minimum=0)
            result.append({'instrument':key,'id':identifier,'name':INSTRUMENTS[key]['name'],'currency':'USD',
                           'status':'ok','price':price,'asOf':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
                           'marketCap':optional(row.get('market_cap'),minimum=0),
                           'rank':optional(row.get('market_cap_rank'),minimum=1),
                           'volume24h':optional(row.get('total_volume'),minimum=0),
                           'change24h':optional(row.get('price_change_percentage_24h'),minimum=-100),
                           'change7d':optional(row.get('price_change_percentage_7d_in_currency'),minimum=-100),
                           'change30d':optional(row.get('price_change_percentage_30d_in_currency'),minimum=-100),
                           'circulatingSupply':optional(row.get('circulating_supply'),minimum=0),
                           'maxSupply':optional(row.get('max_supply'),minimum=0),'ath':ath,
                           'distanceFromAthPct':optional(100*(price/ath-1)) if ath else None,
                           'toAthPct':optional(100*(ath/price-1)) if ath else None})
        except (ValueError,KeyError,TypeError,OverflowError):
            result.append({'instrument':key,'id':identifier,'name':INSTRUMENTS[key]['name'],'status':'error',
                           'error':'Brak poprawnej ceny i czasu dla tego instrumentu. Nie zastąpiono inną monetą.'})
    return result


def global_market(payload):
    row = payload['data'];stamp = timestamp(row['updated_at'])
    return {'marketCapUSD':number(row['total_market_cap']['usd'],True),
            'volume24hUSD':optional(row['total_volume'].get('usd'),minimum=0),
            'btcDominance':optional(row['market_cap_percentage'].get('btc'),minimum=0,maximum=100),
            'ethDominance':optional(row['market_cap_percentage'].get('eth'),minimum=0,maximum=100),
            'change24h':optional(row.get('market_cap_change_percentage_24h_usd'),minimum=-100),
            'asOf':datetime.fromtimestamp(stamp,timezone.utc).isoformat()}


def trending(payload):
    rows = payload['coins']
    if not isinstance(rows,list):raise ValueError('Nieprawidłowa lista popularności CoinGecko.')
    result = []
    for row in rows[:15]:
        item = row['item']
        if not all(isinstance(item.get(k),str) for k in ('id','name','symbol')):raise ValueError('Nieprawidłowa moneta z listy popularności.')
        result.append({'id':item['id'][:150],'name':item['name'][:150],'symbol':item['symbol'][:20],
                       'rank':optional(item.get('market_cap_rank'),minimum=1)})
    return result


def _section(kind, key):
    saved = _CACHE.get(kind);now = time.time()
    if saved and 0 <= now-saved['attemptAt'] < (60 if saved['status']=='error' else TTL[kind]):
        return {**saved,'cached':True}
    try:
        payload = _fetch(kind,key)
        data = {'markets':markets,'global':global_market,'trending':trending}[kind](payload)
        current = {'status':'ok','data':data,'fetchedAt':datetime.fromtimestamp(time.time(),timezone.utc).isoformat(),
                   'attemptAt':now,'error':None,'stale':False,'cached':False}
    except (ValueError,KeyError,TypeError,OverflowError) as error:
        message = str(error) if isinstance(error,FeedError) else 'Nieprawidłowy format danych CoinGecko. Odrzucono odpowiedź dostawcy.'
        current = {'status':'error','data':saved['data'] if saved else None,'fetchedAt':saved['fetchedAt'] if saved else None,
                   'attemptAt':now,'error':message,'stale':True,'cached':False}
    _CACHE[kind] = current
    return dict(current)


def overview():
    with _LOCK:
        key = api_key()
        if not key:raise ValueError('Brak klucza CoinGecko Demo. Uruchom Konfiguruj-CoinGecko.bat i wpisz klucz lokalnie, poza czatem.')
        _identity(key)
        sections = {kind:_section(kind,key) for kind in PATHS}
        now = time.time()
        market = sections['markets']
        if market['data'] is not None:
            market['data'] = [{**row,'ageSeconds':max(0,round(now-timestamp(row['asOf']))),
                              'stale':market['stale'] or now-timestamp(row['asOf'])>300}
                             if row['status']=='ok' else row.copy() for row in market['data']]
        global_data = sections['global']
        if global_data['data'] is not None:
            global_data['stale'] = global_data['stale'] or now-timestamp(global_data['data']['asOf'])>600
        return {'provider':'CoinGecko','currency':'USD','readOnly':True,'sections':sections,'usage':usage(),
                'cacheSeconds':TTL,'notice':'Dane zbiorcze wielu rynków, z opóźnieniem i buforem. Nie są ceną zlecenia OKX, prognozą analityków ani sygnałem bota. Odległość do ATH nie jest oczekiwanym zyskiem. Popularność wyszukiwań nie oznacza rekomendacji.'}
