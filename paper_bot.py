"""One-instrument, long-only paper account. No exchange credentials or order API.

Signals use closed candles; fills use the first fresh observed quote timestamped
AFTER the decision. Missed quotes are never reconstructed into pretend fills.
"""
import json
import math
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime,timezone

from analysis_engine import parameters,risk_plan
from market_data import INSTRUMENTS
from technical_tools import PRESETS
from timeframes import TIMEFRAMES
from user_data import database,now_iso,numeric


@contextmanager
def storage(write=False):
    with database() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS paper_state(id INTEGER PRIMARY KEY,data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS paper_events(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS paper_trades(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS strategy_research(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        if write:conn.execute('BEGIN IMMEDIATE')
        yield conn


def _read(conn):
    row=conn.execute('SELECT data FROM paper_state WHERE id=1').fetchone()
    return json.loads(row['data']) if row else None


def _save(conn,state):conn.execute('INSERT INTO paper_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(json.dumps(state),))
def event(conn,kind,detail):
    item={'id':str(uuid.uuid4()),'created_at':now_iso(),'kind':kind,'detail':detail}
    conn.execute('INSERT INTO paper_events VALUES(?,?,?)',(item['id'],item['created_at'],json.dumps(item)))


def configuration(body):
    key=body.get('instrument','XRP');tf=body.get('timeframe','1h');preset=body.get('preset','balanced')
    if key not in INSTRUMENTS or tf not in TIMEFRAMES or preset not in PRESETS:raise ValueError('Nieprawidłowy instrument, interwał lub zestaw.')
    capital,risk,costs=parameters(body.get('capital',10000),body.get('risk',1),body.get('costs',10))
    return {'instrument':key,'timeframe':tf,'preset':preset,'capital':capital,'risk':risk,'costs':costs,
            'slippage':numeric(body.get('slippage',5),0,100),'daily_loss':numeric(body.get('daily_loss',3),.1,20)}


def start(body):
    if body.get('mode','paper')!='paper':raise ValueError('Bot obsługuje wyłącznie handel papierowy.')
    config=configuration(body)
    with storage(True) as conn:
        state=_read(conn)
        if state and state['position'] and state['config']!=config:raise ValueError('Najpierw zamknij papierową pozycję, zanim zmienisz konfigurację.')
        if state and state['tradeCount'] and state['config']['capital']!=config['capital']:raise ValueError('Kapitał początkowy istniejącego konta jest stały; zmień inne parametry.')
        if state is None:
            state={'cash':config['capital'],'position':None,'pending':None,'tradeCount':0,'realized':0,'day':None,'dayEquity':config['capital'],
                   'lastEquity':config['capital'],'lastQuote':None,'lastCandle':None,'lastDecision':None,'lastHeartbeat':None,'status':'Gotowy.'}
        elif not state['tradeCount'] and not state['position']:
            if state['config']['capital']!=config['capital']:
                state.update({'day':None,'dayEquity':config['capital'],'lastEquity':config['capital'],'lastQuote':None})
            state['cash']=config['capital']
        state.update({'config':config,'active':True,'run_id':str(uuid.uuid4()),'lastCandle':None,'status':'Uruchomiono handel papierowy.'})
        if not state.get('position'):state['pending']=None
        _save(conn,state);event(conn,'start','Uruchomiono papierowy model '+PRESETS[config['preset']]['name']+'. Brak rzeczywistych zleceń.')
    return status()


def stop():
    with storage(True) as conn:
        state=_read(conn)
        if state:
            state['active']=False
            if state.get('pending',{} ) and state['pending']['side']=='BUY':state['pending']=None
            state['status']='Nowe wejścia zatrzymane. Otwarta pozycja nadal podlega stopowi/celowi podczas pracy serwera.'
            _save(conn,state);event(conn,'stop',state['status'])
    return status()


def close_position():
    with storage(True) as conn:
        state=_read(conn)
        if not state or not state['position']:raise ValueError('Nie ma otwartej pozycji papierowej.')
        state['pending']={'side':'SELL','created':time.time(),'reason':'Zamknięcie na żądanie użytkownika'}
        _save(conn,state);event(conn,'order','Zlecono papierowe zamknięcie przy kolejnej świeżej cenie.')
    return status()


def current_state():
    with storage() as conn:return _read(conn)


def fresh(q,key,now=None):
    now=time.time() if now is None else now
    try:return q.get('status')=='ok' and q.get('instrument')==key and q.get('currency')=='USD' and 0<=now-q['timestamp']<=(120 if INSTRUMENTS[key]['kind']=='crypto' else 1200) and math.isfinite(q['price']) and q['price']>0
    except (KeyError,TypeError):return False


def status():
    with storage() as conn:
        state=_read(conn)
        events=[json.loads(r['data']) for r in conn.execute('SELECT data FROM paper_events ORDER BY created_at DESC LIMIT 100')]
        trades=[json.loads(r['data']) for r in conn.execute('SELECT data FROM paper_trades ORDER BY created_at DESC LIMIT 200')]
    if state:
        quote=state.get('lastQuote') or {};valid=state.get('lastQuoteValid',False) and fresh(quote,state['config']['instrument'])
        state['valuationFresh']=valid;state['equity']=state['lastEquity'] if valid or not state['position'] else None
        state['dailyPnl']=state['lastEquity']-state['dayEquity'] if (valid or not state['position']) and state['day']==datetime.now(timezone.utc).date().isoformat() else None
    return {'mode':'paper','state':state,'events':events,'trades':trades,'workerSeconds':15,
            'notice':'Wyłącznie papierowa ekspozycja long w USD, bez dźwigni. Praca wymaga uruchomionego serwera; stan aktywny wznawia się po restarcie. Stop/cel działają na zaobserwowanych cenach, nie gwarantują wykrycia ruchów pomiędzy odczytami. Surowce to ekspozycja referencyjna z mnożnikiem 1, nie zlecenia futures/CFD.'}


def _sell(conn,state,q,reason):
    p=state['position'];cfg=state['config'];price=q['price']*(1-cfg['slippage']/10000);proceeds=p['units']*price*(1-cfg['costs']/10000)
    pnl=proceeds-p['notional']-p['entryFee'];state['cash']+=proceeds;state['realized']+=pnl;state['tradeCount']+=1
    trade={**p,'id':str(uuid.uuid4()),'instrument':cfg['instrument'],'preset':cfg['preset'],'exit':price,'exit_at':q['asOf'],'pnl':pnl,'reason':reason,
           'exitFee':p['units']*price*cfg['costs']/10000,'quoteProvider':q['provider'],'created_at':now_iso()}
    conn.execute('INSERT INTO paper_trades VALUES(?,?,?)',(trade['id'],trade['created_at'],json.dumps(trade)))
    state['position']=None;state['pending']=None;event(conn,'sell',f'Papierowe wyjście: {reason}. Wynik netto USD {pnl:.2f}.')


def advance(run_id,quote,analysis=None,now=None,analysis_error=False):
    now=time.time() if now is None else now
    with storage(True) as conn:
        state=_read(conn)
        if not state or state['run_id']!=run_id:return
        cfg=state['config'];state['lastHeartbeat']=now_iso();old_status=state['status']
        valid=fresh(quote,cfg['instrument'],now);state['lastQuoteValid']=valid
        if valid:
            state['lastQuote']=quote;p=state['position'];fee=cfg['costs']/10000;slip=cfg['slippage']/10000
            equity=state['cash']+(p['units']*quote['price']*(1-slip)*(1-fee) if p else 0)
            day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
            if state['day']!=day:state['day']=day;state['dayEquity']=equity
            breached=equity<=state['dayEquity']*(1-cfg['daily_loss']/100)
            if breached:
                state['active']=False;state['pending']=None
                if p:_sell(conn,state,quote,'Limit dziennej straty (UTC)')
                state['status']='Limit straty dnia: nowe wejścia zablokowane do kolejnego dnia UTC.'
            else:
                if p and quote['price']<=p['stop']:_sell(conn,state,quote,'Stop loss — pierwsza zaobserwowana cena')
                elif p and quote['price']>=p['target']:_sell(conn,state,quote,'Take profit — pierwsza zaobserwowana cena')
                pending=state.get('pending')
                if pending and now-pending['created']>1200:
                    state['pending']=None;event(conn,'expired','Papierowe zlecenie wygasło po 20 minutach bez odpowiedniej świeżej ceny.')
                elif pending and quote['timestamp']>=pending['created']:
                    if pending['side']=='SELL' and state['position']:_sell(conn,state,quote,pending['reason'])
                    elif pending['side']=='BUY' and state['active'] and not state['position']:
                        fill=quote['price']*(1+slip);plan=risk_plan({'close':fill},{'atr':pending['atr']},state['cash'],cfg['risk'],cfg['costs'])
                        if plan['units']>0:
                            p={**plan,'entryFee':plan['notional']*fee,'entry_at':quote['asOf'],'signalCandle':pending['candle'],'decisionAt':pending['created']}
                            state['cash']-=plan['notional']*(1+fee);state['position']=p;event(conn,'buy',f'Papierowe wejście: {cfg["instrument"]}, cena {fill:.6f}, jednostki {plan["units"]:.6f}.')
                        state['pending']=None
                if state['position'] and quote['price']<=state['position']['stop']:_sell(conn,state,quote,'Stop loss po koszcie wejścia')
                state['status']='Monitorowanie papierowego konta.' if state['active'] else 'Nowe wejścia zatrzymane; monitorowanie otwartej pozycji.'
            p=state['position'];state['lastEquity']=state['cash']+(p['units']*quote['price']*(1-slip)*(1-fee) if p else 0)
        else:state['status']='Brak świeżej poprawnej ceny — zlecenia i poziomy ochronne nie są wykonywane.'
        if state['active'] and analysis and analysis['lastDate']!=state['lastCandle']:
            state['lastCandle']=analysis['lastDate'];decision=analysis['decision'];state['lastDecision']={'action':decision['action'],'reason':decision['reason'],'candle':analysis['lastDate'],'at':now_iso()}
            event(conn,'signal',decision['action']+': '+decision['reason'])
            if not analysis.get('stale') and analysis.get('mode')=='live':
                if decision['action']=='BUY' and not state['position'] and not state['pending'] and analysis.get('historyGuard',{}).get('passed'):
                    atr=analysis['indicators'][-1]['atr']
                    if atr is not None and atr>0:state['pending']={'side':'BUY','created':now,'atr':atr,'candle':analysis['lastDate']}
                elif decision['action']=='SELL' and state['position'] and not state['pending']:state['pending']={'side':'SELL','created':now,'reason':'Sygnał wyjścia z zamkniętej świecy'}
        if analysis_error and state['active']:state['status']='Ceny są monitorowane, ale nie udało się pobrać świec/analizy — brak nowych sygnałów.'
        if state['status']!=old_status:event(conn,'status',state['status'])
        _save(conn,state)


class Service:
    def __init__(self,quote_provider,analysis_provider):self.quote_provider=quote_provider;self.analysis_provider=analysis_provider;self.shutdown=threading.Event();self.thread=None
    def pulse(self):
        state=current_state()
        if not state or not (state['active'] or state['position'] or state['pending']):return
        cfg=state['config'];q=self.quote_provider(cfg['instrument']);analysis=None;analysis_error=False
        try:
            if state['active']:analysis=self.analysis_provider(cfg)
        except Exception:analysis_error=True
        if not self.shutdown.is_set():advance(state['run_id'],q,analysis,analysis_error=analysis_error)
    def run(self):
        while not self.shutdown.is_set():
            try:self.pulse()
            except Exception:
                # Do not log provider URLs/credentials or invent successful executions.
                try:
                    with storage(True) as conn:
                        s=_read(conn)
                        if s:s['status']='Błąd cyklu bota; brak potwierdzenia wykonania. Sprawdź dane i bazę.';s['lastHeartbeat']=now_iso();_save(conn,s)
                except Exception:pass
            self.shutdown.wait(15)
    def start(self):self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):self.shutdown.set();self.thread.join(timeout=2)


def save_research(record):
    record={**record,'id':str(uuid.uuid4()),'verified':False}
    with storage(True) as conn:conn.execute('INSERT INTO strategy_research VALUES(?,?,?)',(record['id'],record['fetchedAt'],json.dumps(record)))
    return record

def research_records():
    with storage() as conn:return [json.loads(r['data']) for r in conn.execute('SELECT data FROM strategy_research ORDER BY created_at DESC LIMIT 30')]
