"""Public price snapshots with explicit source, timestamp and freshness metadata."""
import json
import math
import threading
import time
import urllib.parse
import urllib.request
import okx_data
import network_guard
from instrument_catalog import INSTRUMENTS
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

QUOTE_CACHE_SECONDS = 10
_CACHE = {}
_LOCKS = {(key,source): threading.Lock() for key in INSTRUMENTS for source in ('reference','okx')}


def read_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Inwestapp/1.5', 'Accept': 'application/json'})
    return network_guard.read_json(request)


def number(value, positive=False):
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError('Nieprawidłowa wartość notowania.')
    return result


def timestamp(value):
    if isinstance(value, str):
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError('Brak strefy czasowej notowania.')
        return result.timestamp()
    return number(value)


def fetch_coinbase(key):
    symbol = INSTRUMENTS[key]['symbol']
    quote = read_json(f'https://api.exchange.coinbase.com/products/{symbol}/ticker')
    return {'provider': 'Coinbase Exchange', 'sourceSymbol': symbol, 'price': number(quote['price'], True),
            'timestamp': timestamp(quote['time']), 'bid': number(quote['bid'], True), 'ask': number(quote['ask'], True),
            'timingType': 'exchange', 'delaySeconds': 0, 'marketState': 'continuous'}


def fetch_yahoo_quote(key):
    symbol = urllib.parse.quote(INSTRUMENTS[key]['symbol'], safe='')
    payload = read_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m')
    meta = payload['chart']['result'][0]['meta']
    if meta.get('currency') != 'USD':
        raise ValueError('Źródło zwróciło inną walutę niż USD.')
    delay = meta.get('exchangeDataDelayedBy')
    # Yahoo's exchangeDataDelayedBy is expressed in minutes.
    delay = number(delay) * 60 if delay is not None else None
    if delay is not None and delay < 0:
        raise ValueError('Nieprawidłowe opóźnienie notowania.')
    period = meta.get('currentTradingPeriod', {}).get('regular', {})
    state = 'unknown'
    if isinstance(period.get('start'), (int, float)) and isinstance(period.get('end'), (int, float)):
        state = 'open' if period['start'] <= time.time() < period['end'] else 'outside_session'
    return {'provider': 'Yahoo Finance', 'sourceSymbol': INSTRUMENTS[key]['symbol'],
            'price': number(meta['regularMarketPrice'], True), 'timestamp': timestamp(meta['regularMarketTime']),
            'bid': None, 'ask': None, 'timingType': 'reference', 'delaySeconds': delay, 'marketState': state}


def quote_freshness(quote, key):
    age = max(0, time.time() - quote['timestamp'])
    stale = age > (120 if INSTRUMENTS[key]['kind'] == 'crypto' else 600)
    return {**quote, 'asOf': datetime.fromtimestamp(quote['timestamp'], timezone.utc).isoformat(),
            'ageSeconds': round(age), 'stale': stale}


def get_quote(key,source='reference'):
    if source not in ('reference','okx'):raise ValueError('Nieprawidłowe źródło notowań.')
    actual='okx' if source=='okx' and INSTRUMENTS[key]['kind']=='crypto' else 'reference'
    cache_key=(key,actual)
    # Per-instrument lock prevents duplicate upstream requests from overlapping browser polls.
    with _LOCKS[cache_key]:
        cached = _CACHE.get(cache_key)
        if cached and time.monotonic() - cached['savedAt'] < QUOTE_CACHE_SECONDS:
            result = cached['result']
        else:
            last = cached['result'].get('lastQuote') if cached and cached['result']['status'] == 'error' else (cached['result'] if cached else None)
            try:
                quote = okx_data.ticker(key) if actual=='okx' else fetch_coinbase(key) if INSTRUMENTS[key]['kind'] == 'crypto' else fetch_yahoo_quote(key)
                if quote['timestamp'] <= 0 or quote['timestamp'] > time.time() + 60:
                    raise ValueError('Nieprawidłowy czas notowania.')
                if quote['bid'] is not None and quote['ask'] < quote['bid']:
                    raise ValueError('Nieprawidłowy spread.')
                result = {'currency':'USD', **quote, 'source':actual,'instrument': key, 'name': INSTRUMENTS[key]['name'],
                          'status': 'ok', 'receivedAt': datetime.now(timezone.utc).isoformat()}
            except Exception:
                provider = 'OKX' if actual=='okx' else 'Coinbase Exchange' if INSTRUMENTS[key]['kind'] == 'crypto' else 'Yahoo Finance'
                result = {'instrument': key, 'name': INSTRUMENTS[key]['name'], 'status': 'error', 'lastQuote': last,
                          'error': f'Brak połączenia lub prawidłowych danych z {provider}. Spróbuj ponownie później.'}
            _CACHE[cache_key] = {'savedAt': time.monotonic(), 'result': result}
    if result['status'] == 'ok':
        return quote_freshness(result, key)
    if result['lastQuote']:
        return {**result, 'lastQuote': {**quote_freshness(result['lastQuote'], key), 'stale': True}}
    return result


def get_quotes(keys=None,source='reference'):
    keys = list(INSTRUMENTS) if keys is None else keys
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(keys)))) as pool:
        quotes = list(pool.map(lambda key:get_quote(key,source), keys))
    return {'quotes': quotes, 'fetchedAt': datetime.now(timezone.utc).isoformat(), 'cacheSeconds': QUOTE_CACHE_SECONDS}
