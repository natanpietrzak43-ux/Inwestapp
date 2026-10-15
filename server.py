"""Single-user local server. No broker connection or automatic orders."""
import argparse
import csv
import io
import json
import random
import sqlite3
import user_data
from news_data import get_news
import math
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from analysis_engine import analyze, parameters
from market_data import INSTRUMENTS, get_quotes
from technical_tools import TOOLS, PRESETS, SOURCES, selection
from timeframes import TIMEFRAMES, candle_time, candle_closed, aggregate_hours

ROOT = Path(__file__).parent / 'web'
CACHE = {}
LOCK = threading.Lock()


def demo_bars(key, timeframe='1d'):
    rng = random.Random(key + '-inwestapp-v1')
    price = {'XRP': 1.8, 'XLM': .24, 'SILVER': 30, 'OIL': 68, 'GOLD': 2500}[key]
    today = datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    if timeframe=='1d':today=today.replace(hour=0)
    bars = []
    for i in range(900):
        date = today - timedelta(seconds=(900-i)*TIMEFRAMES[timeframe]['seconds'])
        if INSTRUMENTS[key]['kind'] != 'crypto' and date.weekday() > 4:
            continue
        op = price * math.exp(rng.gauss(0, .003))
        volatility = (.024 if key in ('XRP', 'XLM') else .012)/math.sqrt(86400/TIMEFRAMES[timeframe]['seconds'])
        price = op * math.exp(.0004 + .002 * math.sin(i / 45) + rng.gauss(0, volatility))
        bars.append({'date': date.isoformat() if timeframe!='1d' else date.strftime('%Y-%m-%d'), 'open': op, 'high': max(op, price) * (1+rng.uniform(.001, .015)),
                     'low': min(op, price) * (1-rng.uniform(.001, .015)), 'close': price, 'volume': rng.randint(100000, 300000)})
    return bars


def fetch_bars(key, timeframe='1h'):
    spec=TIMEFRAMES[timeframe]
    cache_key=(key,timeframe)
    with LOCK:
        cached = CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 60:
        return cached[1], cached[2]
    symbol = urllib.parse.quote(INSTRUMENTS[key]['symbol'], safe='')
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={spec["range"]}&interval={spec["providerInterval"]}'
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    result = payload['chart']['result'][0]
    quote = result['indicators']['quote'][0]
    now = datetime.now(timezone.utc)
    bars = []
    for i, timestamp in enumerate(result['timestamp']):
        when=datetime.fromtimestamp(timestamp,timezone.utc)
        date = when.isoformat() if timeframe!='1d' else when.strftime('%Y-%m-%d')
        if not candle_closed(date,'1h' if spec.get('aggregate') else timeframe,now) or any(quote[k][i] is None for k in ('open', 'high', 'low', 'close')):
            continue
        bars.append({'date': date, **{k: quote[k][i] for k in ('open', 'high', 'low', 'close')}, 'volume': quote['volume'][i] or 0})
    if spec.get('aggregate'):bars=aggregate_hours(bars,timeframe,now)
    fetched = datetime.now(timezone.utc).isoformat()
    with LOCK:
        CACHE[cache_key] = (time.time(), bars, fetched)
    return bars, fetched


def package(key, bars, mode, capital, risk, costs, fetched=None, timeframe='1d', tools=None, strategy='trend'):
    result = analyze(bars, capital, risk, costs,timeframe,tools,strategy)
    age_seconds=max(0,(datetime.now(timezone.utc)-candle_time(bars[-1]['date'],timeframe)).total_seconds())
    age=age_seconds/86400
    threshold=max(TIMEFRAMES[timeframe]['seconds']*3, (3 if INSTRUMENTS[key]['kind']=='crypto' else 6)*3600) if timeframe!='1d' else (2 if INSTRUMENTS[key]['kind']=='crypto' else 4)*86400
    stale = age_seconds>threshold
    result.update({'instrument': {'id': key, **INSTRUMENTS[key]}, 'mode': mode, 'fetchedAt': fetched,
                   'lastDate': bars[-1]['date'], 'stale': stale, 'ageDays': age,'ageSeconds':round(age_seconds), 'history':{'first':bars[0]['date'],'last':bars[-1]['date'],'availableDays':round((candle_time(bars[-1]['date'],timeframe)-candle_time(bars[0]['date'],timeframe)).total_seconds()/86400,1),'providerLimitDays':TIMEFRAMES[timeframe]['limitDays'] if mode=='live' else None,'aggregated':bool(TIMEFRAMES[timeframe].get('aggregate'))}})
    if mode == 'demo' or stale:
        result['decision']['modelAction'] = result['decision']['action']
        result['decision']['action'] = 'WAIT'
        result['decision']['reason'] = ('Dane demonstracyjne — brak rekomendacji transakcyjnej.' if mode == 'demo'
                                        else 'Dane są nieaktualne — poczekaj na aktualne notowania.')
    return result


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:self.wfile.write(raw)
        except (ConnectionError,TimeoutError):pass

    def allowed(self, write=False):
        host=self.headers.get('Host','')
        parsed=urllib.parse.urlparse('//'+host)
        if parsed.hostname not in ('localhost','127.0.0.1','::1'):
            self.send_json({'error':'Serwer jest przeznaczony do użytku lokalnego.'},403);return False
        origin=self.headers.get('Origin')
        if write and origin and origin != 'http://'+host:
            self.send_json({'error':'Niedozwolone źródło żądania.'},403);return False
        return True

    def do_GET(self):
        if not self.allowed():return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/health':
            return self.send_json({'status': 'ok', 'version': '1.3.0', 'instruments': list(INSTRUMENTS)})
        if parsed.path=='/api/catalog':
            return self.send_json({'tools':TOOLS,'presets':PRESETS,'timeframes':TIMEFRAMES,'sources':SOURCES})
        if parsed.path == '/api/quotes':
            query = urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
            key = query.get('instrument', [None])[0]
            if key is not None and key not in INSTRUMENTS:
                return self.send_json({'error': 'Nieprawidłowy instrument.'}, 400)
            snapshot=get_quotes([key] if key else None)
            try:snapshot['alertEvents']=user_data.evaluate_alerts(snapshot['quotes'])
            except (sqlite3.Error,OSError):snapshot['monitorError']='Nie udało się zapisać alertu w bazie. Sprawdź dostęp do folderu danych.'
            return self.send_json(snapshot)
        if parsed.path == '/api/analyze':
            query = urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
            key = query.get('instrument', ['XRP'])[0]
            mode = query.get('mode', ['live'])[0]
            if key not in INSTRUMENTS or mode not in ('live', 'demo'):
                return self.send_json({'error': 'Nieprawidłowy instrument lub tryb.'}, 400)
            try:
                timeframe=query.get('timeframe',['1h'])[0]
                strategy=query.get('strategy',['trend'])[0]
                if timeframe not in TIMEFRAMES:raise ValueError('Nieprawidłowy interwał.')
                tools=selection(query['tools'][0].split(',') if query.get('tools') and query['tools'][0] else ([] if 'tools' in query else None),strategy)
                args = parameters(query.get('capital', [10000])[0], query.get('risk', [1])[0], query.get('costs', [10])[0])
                if mode == 'demo':
                    bars, fetched = demo_bars(key,timeframe), None
                else:
                    try:
                        bars, fetched = fetch_bars(key,timeframe)
                    except Exception:
                        return self.send_json({'error': 'Nie udało się pobrać notowań z Yahoo Finance. Sprawdź dostęp do query1.finance.yahoo.com, spróbuj później albo zaimportuj CSV. Nie podstawiono danych demonstracyjnych.'}, 502)
                return self.send_json(package(key, bars, mode, *args, fetched=fetched,timeframe=timeframe,tools=tools,strategy=strategy))
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                return self.send_json({'error': str(exc)}, 400)
        if parsed.path in ('/api/alerts','/api/journal','/api/export','/api/forecasts','/api/news'):
            try:
                query=urllib.parse.parse_qs(parsed.query)
                if parsed.path=='/api/alerts':return self.send_json(user_data.list_alerts())
                if parsed.path=='/api/export':return self.send_json(user_data.export_data())
                if parsed.path=='/api/journal':
                    opened={r['instrument'] for r in user_data.raw_records('trades') if r['exit_price'] is None}
                    quotes=get_quotes(sorted(opened))['quotes'] if opened else []
                    return self.send_json(user_data.journal(quotes))
                key=user_data.instrument(query.get('instrument',['XRP'])[0])
                if parsed.path=='/api/news':return self.send_json(get_news(key))
                horizon=int(query.get('horizon',['90'])[0])
                quote=get_quotes([key])['quotes'][0]
                return self.send_json(user_data.forecast_summary(key,horizon,quote))
            except (ValueError,TypeError,KeyError) as exc:return self.send_json({'error':str(exc)},400)
            except (sqlite3.Error,OSError):return self.send_json({'error':'Baza danych jest niedostępna.'},503)
        paths = {'/workspace.js':'workspace.js', '/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if parsed.path not in paths:
            return self.send_json({'error': 'Nie znaleziono.'}, 404)
        file = ROOT / paths[parsed.path]
        raw = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8'}[file.suffix[1:]])
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        try:self.wfile.write(raw)
        except (ConnectionError,TimeoutError):pass

    def do_POST(self):return self.mutate('POST')
    def do_PUT(self):return self.mutate('PUT')
    def do_DELETE(self):return self.mutate('DELETE')

    def mutate(self,method):
        if not self.allowed(write=True):return
        try:
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.send_json({'error':'Wymagany typ application/json.'},415)
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=9_000_000:raise ValueError('Żądanie może mieć maksymalnie 9 MB.')
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('Wymagany obiekt JSON.')
            parts=urllib.parse.urlparse(self.path).path.strip('/').split('/')
            if len(parts)>=2 and parts[0]=='api' and parts[1] in ('alerts','trades','forecasts'):
                table=parts[1];identifier=parts[2] if len(parts)>2 else None
                if method=='DELETE' and identifier and len(parts)==3:
                    user_data.delete_record(table,identifier);return self.send_json({'ok':True})
                if method=='POST' and table=='alerts' and len(parts)==4 and parts[3]=='rearm':
                    user_data.rearm_alert(identifier);return self.send_json({'ok':True})
                if method=='PUT' and table=='trades' and identifier and len(parts)==3:
                    return self.send_json(user_data.save_trade(body,identifier))
                if method=='POST' and len(parts)==2:
                    function={'alerts':user_data.add_alert,'trades':user_data.save_trade,'forecasts':user_data.save_forecast}[table]
                    return self.send_json(function(body),201)
                return self.send_json({'error':'Nieprawidłowa operacja.'},400)
            if self.path!='/api/import' or method!='POST':return self.send_json({'error':'Nie znaleziono.'},404)
            if not isinstance(body.get('csv'),str):raise ValueError('Import wymaga tekstowego pola csv.')
            key = body.get('instrument')
            if key not in INSTRUMENTS:
                raise ValueError('Nieprawidłowy instrument.')
            reader = csv.DictReader(io.StringIO(body['csv'].lstrip('\ufeff')))
            if not set(('date', 'open', 'high', 'low', 'close', 'volume')).issubset(reader.fieldnames or []):
                raise ValueError('CSV wymaga kolumn: date,open,high,low,close,volume.')
            bars = list(reader)
            args = parameters(body.get('capital', 10000), body.get('risk', 1), body.get('costs', 10))
            return self.send_json(package(key, bars, 'csv', *args,timeframe=body.get('timeframe','1d'),tools=body.get('tools'),strategy=body.get('strategy','trend')))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            return self.send_json({'error': str(exc)}, 400)
        except (sqlite3.Error,OSError):
            return self.send_json({'error':'Baza danych jest niedostępna.'},503)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--open-browser', action='store_true', help='Otwórz aplikację w przeglądarce po uruchomieniu.')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f'http://{args.host}:{args.port}'
    print(f'Inwestapp v1.3: {url}', flush=True)
    if args.open_browser:
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nSerwer zatrzymany.', flush=True)
    finally:
        server.server_close()
