"""Single-user SQLite journal, one-shot price alerts and attributed manual forecasts."""
import json
import math
import os
import sqlite3
import time
import uuid
import execution_context
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from market_data import INSTRUMENTS


def data_dir():
    if execution_context.root.get() is not None:return Path(execution_context.root.get())
    configured=os.environ.get('INWESTAPP_DATA_DIR')
    if configured:return Path(configured).expanduser()
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'Inwestapp'
    return Path(__file__).parent/'.data'


@contextmanager
def database():
    root=data_dir();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    conn=sqlite3.connect(root/'inwestapp.sqlite3',timeout=15)
    if os.name!='nt':(root/'inwestapp.sqlite3').chmod(0o600)
    conn.row_factory=sqlite3.Row
    try:
        conn.executescript('''CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,instrument TEXT,direction TEXT,price REAL,enabled INTEGER,created_at TEXT,triggered_at TEXT);
CREATE TABLE IF NOT EXISTS alert_events(id TEXT PRIMARY KEY,alert_id TEXT,instrument TEXT,price REAL,threshold REAL,direction TEXT,quote_at TEXT,source TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS forecasts(id TEXT PRIMARY KEY,data TEXT NOT NULL);''')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally:conn.close()


def now_iso():return datetime.fromtimestamp(execution_context.clock.get(),timezone.utc).isoformat() if execution_context.clock.get() is not None else datetime.now(timezone.utc).isoformat()
def numeric(value,minimum=0,maximum=1e12):
    result=float(value)
    if not math.isfinite(result) or not minimum<=result<=maximum:raise ValueError('Liczba poza dozwolonym zakresem.')
    return result
def instrument(value):
    if value not in INSTRUMENTS:raise ValueError('Nieprawidłowy instrument.')
    return value
def text(value,limit=1000):
    if not isinstance(value,str) or len(value)>limit:raise ValueError('Za długi lub nieprawidłowy tekst.')
    return value.strip()
def date(value):
    if not isinstance(value,str):raise ValueError('Podaj datę z godziną i strefą czasową.')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Data wymaga strefy czasowej.')
    if result>datetime.now(timezone.utc)+timedelta(minutes=1):raise ValueError('Data transakcji/prognozy nie może być przyszła.')
    return result.astimezone(timezone.utc)
def source_url(value):
    value=text(value,1000);url=urlparse(value)
    if url.scheme!='https' or not url.hostname or '.' not in url.hostname or url.username or url.password:
        raise ValueError('Źródło wymaga publicznego adresu https bez danych logowania.')
    return value


def list_alerts():
    with database() as conn:
        return {'alerts':[dict(r) for r in conn.execute('SELECT * FROM alerts ORDER BY created_at DESC')],
                'events':[dict(r) for r in conn.execute('SELECT * FROM alert_events ORDER BY created_at DESC LIMIT 100')]}


def add_alert(body):
    key=instrument(body.get('instrument'));direction=body.get('direction')
    if direction not in ('above','below'):raise ValueError('Wybierz cenę powyżej lub poniżej progu.')
    price=numeric(body.get('price'),1e-9)
    record={'id':str(uuid.uuid4()),'instrument':key,'direction':direction,'price':price,'enabled':1,'created_at':now_iso(),'triggered_at':None}
    with database() as conn:
        if conn.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]>=200:raise ValueError('Maksymalnie 200 alertów; usuń zbędne.')
        conn.execute('INSERT INTO alerts VALUES(:id,:instrument,:direction,:price,:enabled,:created_at,:triggered_at)',record)
    return record


def rearm_alert(identifier):
    with database() as conn:
        if not conn.execute('UPDATE alerts SET enabled=1,triggered_at=NULL WHERE id=?',(identifier,)).rowcount:raise ValueError('Nie znaleziono alertu.')


def delete_record(table,identifier):
    if table not in ('alerts','trades','forecasts'):raise ValueError('Nieprawidłowy typ rekordu.')
    with database() as conn:
        if not conn.execute('DELETE FROM '+table+' WHERE id=?',(identifier,)).rowcount:raise ValueError('Nie znaleziono rekordu.')


def evaluate_alerts(quotes):
    valid={}
    for q in quotes:
        if q.get('status')!='ok' or q.get('currency')!='USD':continue
        key=q.get('instrument')
        if key not in INSTRUMENTS:continue
        age=time.time()-q.get('timestamp',0)
        if not -60<=age<=(120 if INSTRUMENTS[key]['kind']=='crypto' else 1200):continue
        valid[key]=q
    events=[]
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for alert in conn.execute('SELECT * FROM alerts WHERE enabled=1').fetchall():
            q=valid.get(alert['instrument'])
            if not q:continue
            hit=q['price']>=alert['price'] if alert['direction']=='above' else q['price']<=alert['price']
            if not hit:continue
            stamp=now_iso()
            if conn.execute('UPDATE alerts SET enabled=0,triggered_at=? WHERE id=? AND enabled=1',(stamp,alert['id'])).rowcount:
                event={'id':str(uuid.uuid4()),'alert_id':alert['id'],'instrument':alert['instrument'],'price':q['price'],
                       'threshold':alert['price'],'direction':alert['direction'],'quote_at':q['asOf'],'source':q['provider'],'created_at':stamp}
                conn.execute('INSERT INTO alert_events VALUES(:id,:alert_id,:instrument,:price,:threshold,:direction,:quote_at,:source,:created_at)',event);events.append(event)
    return events


def save_trade(body,identifier=None):
    record={'id':identifier or str(uuid.uuid4()),'instrument':instrument(body.get('instrument')),'direction':body.get('direction','long'),
            'quantity':numeric(body.get('quantity'),1e-9),'entry_price':numeric(body.get('entry_price'),1e-9),
            'multiplier':numeric(body.get('multiplier',1),1e-9,1e6),'fees':numeric(body.get('fees',0),0,1e9),
            'entry_at':date(body.get('entry_at')).isoformat(),'note':text(body.get('note',''))}
    if record['direction'] not in ('long','short'):raise ValueError('Nieprawidłowy kierunek transakcji.')
    closed=body.get('exit_price') not in ('',None)
    record['exit_price']=numeric(body['exit_price'],1e-9) if closed else None
    record['exit_at']=date(body.get('exit_at')).isoformat() if closed else None
    if closed and record['exit_at']<record['entry_at']:raise ValueError('Zamknięcie nie może poprzedzać otwarcia.')
    for field in ('stop_price','target_price'):
        record[field]=numeric(body[field],1e-9) if body.get(field) not in ('',None) else None
    sign=1 if record['direction']=='long' else -1
    if record['stop_price'] is not None and sign*(record['entry_price']-record['stop_price'])<=0:raise ValueError('Stop jest po niewłaściwej stronie wejścia.')
    if record['target_price'] is not None and sign*(record['target_price']-record['entry_price'])<=0:raise ValueError('Cel jest po niewłaściwej stronie wejścia.')
    if record['quantity']*record['entry_price']*record['multiplier']>1e15:raise ValueError('Zbyt duża ekspozycja.')
    with database() as conn:
        if identifier:
            if not conn.execute('UPDATE trades SET data=? WHERE id=?',(json.dumps(record),identifier)).rowcount:raise ValueError('Nie znaleziono transakcji.')
        else:conn.execute('INSERT INTO trades VALUES(?,?)',(record['id'],json.dumps(record)))
    return record


def raw_records(table):
    if table not in ('trades','forecasts'):raise ValueError('Nieprawidłowy typ rekordu.')
    with database() as conn:return [json.loads(r['data']) for r in conn.execute('SELECT data FROM '+table)]


def journal(quotes=None):
    quotes={q['instrument']:q for q in quotes or []};records=[];realized=0;unrealized=0;missing=0;stale=0;wins=0;closed=0
    for original in raw_records('trades'):
        trade=dict(original);sign=1 if trade['direction']=='long' else -1;units=trade['quantity']*trade['multiplier']
        trade['status']='closed' if trade['exit_price'] is not None else 'open'
        q=quotes.get(trade['instrument'],{});mark=q.get('price') if q.get('status')=='ok' else None
        price=trade['exit_price'] if trade['status']=='closed' else mark
        pnl=(price-trade['entry_price'])*units*sign-trade['fees'] if price is not None else None
        trade.update({'pnl':pnl,'mark_price':mark,'quote_at':q.get('asOf'),'valuation_stale':q.get('stale',True),
                      'return_pct':100*pnl/(trade['entry_price']*units+trade['fees']) if pnl is not None else None})
        risk=abs(trade['entry_price']-trade['stop_price'])*units+trade['fees'] if trade['stop_price'] is not None else None
        reward=abs(trade['target_price']-trade['entry_price'])*units-trade['fees'] if trade['target_price'] is not None else None
        trade.update({'planned_risk':risk,'planned_reward':reward,'reward_risk':reward/risk if reward is not None and risk else None})
        if trade['status']=='closed':realized+=pnl;closed+=1;wins+=pnl>0
        elif pnl is None:missing+=1
        else:unrealized+=pnl;stale+=bool(trade['valuation_stale'])
        records.append(trade)
    records.sort(key=lambda r:r['entry_at'],reverse=True)
    return {'trades':records,'summary':{'realized':realized,'unrealized':unrealized if not missing else None,'unrealizedKnown':unrealized,
                'closed':closed,'open':len(records)-closed,'winRate':100*wins/closed if closed else None,'missingQuotes':missing,'staleQuotes':stale}}


def save_forecast(body):
    key=instrument(body.get('instrument'));horizon=int(body.get('horizon_days',90))
    if horizon not in (30,90,180,365):raise ValueError('Wybierz horyzont 30, 90, 180 lub 365 dni.')
    analyst=text(body.get('analyst',''),150)
    if not analyst:raise ValueError('Podaj autora lub instytucję prognozy.')
    record={'id':str(uuid.uuid4()),'instrument':key,'analyst':analyst,'target_price':numeric(body.get('target_price'),1e-9),
            'issued_at':date(body.get('issued_at')).isoformat(),'horizon_days':horizon,'source_url':source_url(body.get('source_url','')),
            'basis_symbol':INSTRUMENTS[key]['symbol'],'note':text(body.get('note','')),'origin':'user_verified'}
    with database() as conn:conn.execute('INSERT INTO forecasts VALUES(?,?)',(record['id'],json.dumps(record)))
    return record


def forecast_summary(key,horizon,quote=None):
    import statistics
    horizon=int(horizon)
    if horizon not in (30,90,180,365):raise ValueError('Nieprawidłowy horyzont prognozy.')
    entries=[r for r in raw_records('forecasts') if r['instrument']==key and r['horizon_days']==horizon]
    active={};now=datetime.now(timezone.utc)
    for r in sorted(entries,key=lambda r:r['issued_at']):
        issued=datetime.fromisoformat(r['issued_at'])
        if (now-issued).total_seconds()<=30*86400 and issued+timedelta(days=horizon)>now:
            active[' '.join(r['analyst'].casefold().split())]=r
    values=list(active.values());target=statistics.median(r['target_price'] for r in values) if values else None
    current=quote.get('price') if quote and quote.get('status')=='ok' else None
    return {'entries':sorted(entries,key=lambda r:r['issued_at'],reverse=True),'activeCount':len(values),'medianTarget':target,
            'expectedChangePct':100*(target/current-1) if target is not None and current and not quote.get('stale') else None,
            'currentPrice':current,'quoteAt':quote.get('asOf') if quote else None,'horizonDays':horizon,'basisSymbol':INSTRUMENTS[key]['symbol'],
            'kind':'user_verified_targets','notice':'Mediana wpisanych i zweryfikowanych przez użytkownika celów. To nie automatyczny konsensus rynku. Aktywne są prognozy z ostatnich 30 dni, dla jednego horyzontu; jeden głos na autora.'}


def export_data():
    with database() as conn:
        names=('alerts','alert_events','trades','forecasts','paper_state','paper_events','paper_trades','strategy_research','agent_cycles','paper_accounts','bot_backtests',
               'strategy_versions','strategy_validations','demo_state','demo_orders','demo_fills','ops_events','runtime_heartbeats')
        tables={table:[dict(r) for r in conn.execute('SELECT * FROM '+table)] for table in names if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()}
    return {'schemaVersion':1,'exportedAt':now_iso(),'tables':tables}
