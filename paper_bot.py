"""One-instrument paper account: spot long or simulated isolated perpetuals.

No exchange credentials or authenticated order API.

Signals use closed candles; fills use the first fresh observed quote timestamped
AFTER the decision. Missed quotes are never reconstructed into pretend fills.
"""
import json
import math
import threading
import time
import uuid
import agent_pipeline
import leveraged_trading as leverage
import okx_data
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
        conn.execute('CREATE TABLE IF NOT EXISTS agent_cycles(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS paper_accounts(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS bot_backtests(id TEXT PRIMARY KEY,created_at TEXT,data TEXT NOT NULL)')
        if write:conn.execute('BEGIN IMMEDIATE')
        yield conn


def _read(conn):
    row=conn.execute('SELECT data FROM paper_state WHERE id=1').fetchone()
    if not row:return None
    state=json.loads(row['data'])
    state.setdefault('accountId','legacy')
    state['config']=configuration({**state['config'],'engine':state['config'].get('engine','classic')})
    state.setdefault('peakEquity',max(state['config']['capital'],state.get('lastEquity',state['cash'])))
    return state


def _save(conn,state):conn.execute('INSERT INTO paper_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(json.dumps(state),))
def event(conn,kind,detail):
    state=_read(conn)
    item={'id':str(uuid.uuid4()),'created_at':now_iso(),'kind':kind,'detail':detail,'accountId':state.get('accountId','legacy') if state else 'legacy'}
    conn.execute('INSERT INTO paper_events VALUES(?,?,?)',(item['id'],item['created_at'],json.dumps(item)))


def configuration(body):
    key=body.get('instrument','XRP');tf=body.get('timeframe','1h');preset=body.get('preset','balanced')
    if key not in INSTRUMENTS or tf not in TIMEFRAMES or preset not in PRESETS:raise ValueError('Nieprawidłowy instrument, interwał lub zestaw.')
    capital,risk,costs=parameters(body.get('capital',10000),body.get('risk',1),body.get('costs',10))
    source=body.get('source','reference');engine=body.get('engine','agents')
    if source not in ('reference','okx') or engine not in ('classic','agents'):raise ValueError('Nieprawidłowe źródło lub silnik bota.')
    if source=='okx' and INSTRUMENTS[key]['kind']!='crypto':raise ValueError('OKX: wybierz XRP, XLM, BTC lub ETH / USDT.')
    contract=leverage.options(body)
    if contract['market']=='perpetual' and (source!='okx' or engine!='agents' or INSTRUMENTS[key]['kind']!='crypto'):
        raise ValueError('Futures wymagają źródła OKX, zespołu agentów i instrumentu XRP/XLM/BTC/ETH.')
    return {'instrument':key,'timeframe':tf,'preset':preset,'capital':capital,'risk':risk,'costs':costs,
            **contract,
            'source':source,'engine':engine,'currency':'USDT' if source=='okx' else 'USD',
            'slippage':numeric(body.get('slippage',5),0,100),'daily_loss':numeric(body.get('daily_loss',3),.1,20),
            'max_drawdown':numeric(body.get('max_drawdown',10),1,50),'max_spread':numeric(body.get('max_spread',30),1,200),
            'max_exposure':numeric(body.get('max_exposure',25),1,100),'max_deviation':numeric(body.get('max_deviation',3),.1,15)}


def start(body,new_account=False):
    if body.get('mode','paper')!='paper':raise ValueError('Bot obsługuje wyłącznie handel papierowy.')
    config=configuration(body)
    with storage(True) as conn:
        state=_read(conn)
        if new_account and state:
            if state['active'] or state['position'] or state['pending']:raise ValueError('Przed utworzeniem nowego konta zatrzymaj bota i zamknij papierową pozycję.')
            conn.execute('INSERT INTO paper_accounts VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(state['accountId'],now_iso(),json.dumps(state)))
            state=None
        if state and state['position'] and state['config']!=config:raise ValueError('Najpierw zamknij papierową pozycję, zanim zmienisz konfigurację.')
        if state and state['tradeCount'] and state['config']['capital']!=config['capital']:raise ValueError('Kapitał początkowy istniejącego konta jest stały; zmień inne parametry.')
        if state and state['tradeCount'] and state['config']['currency']!=config['currency']:raise ValueError('Istniejące konto ma inną walutę. Nie przeliczamy USD i USDT 1:1. Zatrzymaj bota i wybierz Nowe konto symulacyjne; dotychczasowe wyniki zostaną zarchiwizowane.')
        if state and state['tradeCount'] and state['config']['market']!=config['market']:raise ValueError('Zmiana spot/futures wymaga Nowego konta symulacyjnego. Dotychczasowa historia pozostanie w archiwum.')
        if state and state.get('riskHalted')=='drawdown':raise ValueError('Konto przekroczyło limit obsunięcia. Start nie zeruje szczytu; oceń wyniki przed utworzeniem nowego konta symulacyjnego.')
        if state is None:
            state={'accountId':str(uuid.uuid4()),'cash':config['capital'],'position':None,'pending':None,'tradeCount':0,'realized':0,'day':None,'dayEquity':config['capital'],
                   'lastEquity':config['capital'],'lastQuote':None,'lastCandle':None,'lastDecision':None,'lastHeartbeat':None,'status':'Gotowy.'}
        elif not state['tradeCount'] and not state['position']:
            if state['config']['capital']!=config['capital'] or state['config']['currency']!=config['currency']:
                state.update({'day':None,'dayEquity':config['capital'],'lastEquity':config['capital'],'peakEquity':config['capital'],'lastQuote':None,'lastQuoteValid':False})
            state['cash']=config['capital']
        if state and state.get('riskHalted')=='daily' and state.get('day')==datetime.now(timezone.utc).date().isoformat():raise ValueError('Limit straty dziennej nadal obowiązuje do końca dnia UTC.')
        state.update({'config':config,'active':True,'run_id':str(uuid.uuid4()),'lastCandle':None,'lastCycle':None,'lastDecision':None,'riskHalted':None,'status':'Uruchomiono handel papierowy.'})
        state.setdefault('peakEquity',state['cash'])
        if not state.get('position'):state['pending']=None
        _save(conn,state);event(conn,'start','Uruchomiono papierowy model '+PRESETS[config['preset']]['name']+'. Brak rzeczywistych zleceń.')
    return status()


def stop():
    with storage(True) as conn:
        state=_read(conn)
        if state:
            state['active']=False
            if state.get('pending',{} ) and state['pending']['side'] in ('BUY','LONG','SHORT'):state['pending']=None
            state['status']='Nowe wejścia zatrzymane. Otwarta pozycja nadal podlega stopowi/celowi podczas pracy serwera.'
            _save(conn,state);event(conn,'stop',state['status'])
    return status()


def close_position():
    with storage(True) as conn:
        state=_read(conn)
        if not state or not state['position']:raise ValueError('Nie ma otwartej pozycji papierowej.')
        state['pending']={'side':'CLOSE' if state['config']['market']=='perpetual' else 'SELL','created':time.time(),'reason':'Zamknięcie na żądanie użytkownika'}
        _save(conn,state);event(conn,'order','Zlecono papierowe zamknięcie przy kolejnej świeżej cenie.')
    return status()


def current_state():
    with storage() as conn:return _read(conn)


def fresh(q,key,now=None,currency='USD',source='reference',market='spot'):
    now=time.time() if now is None else now
    try:return q.get('status')=='ok' and q.get('instrument')==key and q.get('currency')==currency and (source!='okx' or (q.get('provider')=='OKX' and q.get('sourceSymbol')==okx_data.symbol(key,market))) and 0<=now-q['timestamp']<=(120 if INSTRUMENTS[key]['kind']=='crypto' else 1200) and math.isfinite(q['price']) and q['price']>0 and (source!='okx' or (all(math.isfinite(q[k]) for k in ('bid','ask')) and 0<q['bid']<=q['ask'])) and (market!='perpetual' or (math.isfinite(q['markPrice']) and q['markPrice']>0 and 0<=now-q['markTimestamp']<=120))
    except (KeyError,TypeError):return False


def status():
    with storage() as conn:
        state=_read(conn)
        account=state['accountId'] if state else 'legacy'
        events=_records(conn,'paper_events',account,100)
        trades=_records(conn,'paper_trades',account,200)
        archives=[json.loads(r['data']) for r in conn.execute('SELECT data FROM paper_accounts ORDER BY created_at DESC LIMIT 30')]
    if state:
        quote=state.get('lastQuote') or {};valid=state.get('lastQuoteValid',False) and fresh(quote,state['config']['instrument'],currency=state['config']['currency'],source=state['config']['source'],market=state['config']['market'])
        state['valuationFresh']=valid;state['equity']=state['lastEquity'] if valid or not state['position'] else None
        state['dailyPnl']=state['lastEquity']-state['dayEquity'] if (valid or not state['position']) and state['day']==datetime.now(timezone.utc).date().isoformat() else None
    return {'mode':'paper','state':state,'events':events,'trades':trades,'workerSeconds':15,'cycles':cycles(),'archives':archives,
            'notice':'Spot: long bez dźwigni. Futures: symulacja long/short OKX USDT-SWAP, depozyt izolowany, dźwignia 1–10. Funding i maintenance margin są założeniami użytkownika, nie rozliczeniem OKX; ilość w jednostkach bazowych. Praca wymaga serwera, aktywny stan wznawia się po restarcie. Stop/cel na zaobserwowanych cenach. Agenci to lokalne reguły. Surowce: referencyjna ekspozycja z mnożnikiem 1.'}


def _sell(conn,state,q,reason,cycle_id=None):
    p=state['position'];cfg=state['config'];price=(q['bid'] if cfg['source']=='okx' else q['price'])*(1-cfg['slippage']/10000);proceeds=p['units']*price*(1-cfg['costs']/10000)
    pnl=proceeds-p['notional']-p['entryFee'];state['cash']+=proceeds;state['realized']+=pnl;state['tradeCount']+=1
    trade={**p,'id':str(uuid.uuid4()),'instrument':cfg['instrument'],'preset':cfg['preset'],'exit':price,'exit_at':q['asOf'],'pnl':pnl,'reason':reason,
           'exitFee':p['units']*price*cfg['costs']/10000,'quoteProvider':q['provider'],'created_at':now_iso(),
           'currency':cfg['currency'],'source':cfg['source'],'exitCycle':cycle_id,'accountId':state['accountId']}
    conn.execute('INSERT INTO paper_trades VALUES(?,?,?)',(trade['id'],trade['created_at'],json.dumps(trade)))
    state['position']=None;state['pending']=None;state['lastTradeId']=trade['id'];event(conn,'sell',f'Papierowe wyjście: {reason}. Wynik netto {cfg["currency"]} {pnl:.2f}.')


def _records(conn,table,account,limit):
    result=[]
    for row in conn.execute('SELECT data FROM '+table+' ORDER BY created_at DESC'):
        item=json.loads(row['data'])
        if item.get('accountId','legacy')==account:result.append(item)
        if len(result)>=limit:break
    return result


def cycles(limit=30):
    with storage() as conn:
        state=_read(conn)
        return _records(conn,'agent_cycles',state['accountId'] if state else 'legacy',limit)


def advance(run_id,quote,analysis=None,now=None,analysis_error=False):
    now=time.time() if now is None else now
    with storage(True) as conn:
        state=_read(conn)
        if not state or state['run_id']!=run_id:return
        if state['config']['market']=='perpetual':
            from futures_bot import advance as futures_advance
            futures_advance(conn,state,quote,analysis,now,analysis_error,event)
            _save(conn,state)
            return
        cfg=state['config'];agent_mode=cfg['engine']=='agents';cycle=None;executed=None
        state['lastHeartbeat']=now_iso();old_status=state['status']
        valid=fresh(quote,cfg['instrument'],now,cfg['currency'],cfg['source']);state['lastQuoteValid']=valid
        if valid:
            state['lastQuote']=quote;p=state['position'];fee=cfg['costs']/10000;slip=cfg['slippage']/10000
            mark=quote['bid'] if cfg['source']=='okx' else quote['price']
            equity=state['cash']+(p['units']*mark*(1-slip)*(1-fee) if p else 0)
            state['lastEquity']=equity;state['peakEquity']=max(state.get('peakEquity',equity),equity)
            day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
            if state['day']!=day:state['day']=day;state['dayEquity']=equity
            daily=equity<=state['dayEquity']*(1-cfg['daily_loss']/100)
            drawdown=agent_mode and equity<=state['peakEquity']*(1-cfg['max_drawdown']/100)
            if daily or drawdown:
                state['active']=False;state['pending']=None;state['riskHalted']='drawdown' if drawdown else 'daily'
                reason='Limit obsunięcia konta' if drawdown else 'Limit dziennej straty (UTC)'
                if p:_sell(conn,state,quote,reason);executed={'status':'filled','action':'SELL','reason':reason}
                state['status']=reason+': nowe wejścia zablokowane.'
            else:
                if p and mark<=p['stop']:_sell(conn,state,quote,'Stop loss — pierwsza zaobserwowana cena');executed={'status':'filled','action':'SELL','reason':'Stop loss'}
                elif p and mark>=p['target']:_sell(conn,state,quote,'Take profit — pierwsza zaobserwowana cena');executed={'status':'filled','action':'SELL','reason':'Take profit'}
                state['status']='Monitorowanie papierowego konta.' if state['active'] else 'Nowe wejścia zatrzymane; monitorowanie otwartej pozycji.'
            if executed:state['lastExitCandle']=analysis.get('lastDate') if analysis else state.get('lastCandle')
        else:state['status']='Brak świeżej poprawnej ceny — zlecenia i poziomy ochronne nie są wykonywane.'
        if agent_mode:
            cycle=agent_pipeline.evaluate(analysis,quote,cfg,state,now)
            cycle['accountId']=state['accountId']
            if cycle['action']=='BUY' and cycle['candle']==state.get('lastExitCandle'):
                cycle.update(action='WAIT',reason='Po wyjściu czekamy na następną zamkniętą świecę.',plan=None)
                cycle['stages'][-1].update(status='blocked',action='WAIT',reasons=[cycle['reason']],plan=None)
            state['lastCycle']=cycle['id']
        pending=state.get('pending')
        if pending and now-pending['created']>1200:
            state['pending']=None;event(conn,'expired','Papierowe zlecenie wygasło po 20 minutach bez odpowiedniej świeżej ceny.')
        elif pending and agent_mode and (pending['side']=='BUY' or pending.get('agent')) and cycle['action']!=pending['side']:
            state['pending']=None;event(conn,'cancel','Zlecenie anulowane po ponownej kontroli danych i ryzyka: '+cycle['reason'])
        elif pending and valid and quote['timestamp']>pending['created']:
            if pending['side']=='SELL' and state['position']:
                _sell(conn,state,quote,pending['reason'],cycle['id'] if cycle else None)
                executed={'status':'filled','action':'SELL','reason':pending['reason']};state['lastExitCandle']=analysis.get('lastDate') if analysis else state.get('lastCandle')
            elif pending['side']=='BUY' and state['active'] and not state['position']:
                fill=(quote['ask'] if cfg['source']=='okx' else quote['price'])*(1+cfg['slippage']/10000)
                plan=cycle['plan'] if agent_mode else risk_plan({'close':fill},{'atr':pending['atr']},state['cash'],cfg['risk'],cfg['costs'])
                if plan and plan['units']>0:
                    p={**plan,'entryFee':plan['notional']*cfg['costs']/10000,'entry_at':quote['asOf'],'signalCandle':pending['candle'],
                       'decisionAt':pending['created'],'entryCycle':cycle['id'] if cycle else None,'signalCycle':pending.get('cycle'),
                       'entryAudit':cycle if cycle else None}
                    state['cash']-=plan['notional']*(1+cfg['costs']/10000);state['position']=p
                    executed={'status':'filled','action':'BUY','reason':'Świeża cena po decyzji; ponowna zgoda ryzyka.'}
                    event(conn,'buy',f'Papierowe wejście: {cfg["instrument"]}, cena {fill:.6f} {cfg["currency"]}, jednostki {plan["units"]:.6f}.')
                state['pending']=None
        if valid:
            p=state['position'];mark=quote['bid'] if cfg['source']=='okx' else quote['price']
            if p and mark<=p['stop']:
                _sell(conn,state,quote,'Stop loss po koszcie wejścia',cycle['id'] if cycle else None)
                executed={'status':'filled','action':'SELL','reason':'Stop loss po koszcie wejścia'}
                state['lastExitCandle']=analysis.get('lastDate') if analysis else state.get('lastCandle')
            p=state['position'];state['lastEquity']=state['cash']+(p['units']*mark*(1-cfg['slippage']/10000)*(1-cfg['costs']/10000) if p else 0)
        if agent_mode:
            if executed and executed['action']=='SELL':
                cycle.update(action='SELL',reason=executed['reason'],plan=None)
                cycle['stages'].append({'id':'protection','name':'Agent ryzyka — ochrona / zamknięcie','status':'approved','reasons':[executed['reason']+'; wykonano po świeżej cenie. Wyjście ochronne nie wymaga nowego sygnału wskaźników.']})
            action=cycle['action'];candle=cycle['candle']
            if state['active'] and candle and not executed and not state.get('pending'):
                if action=='BUY' and not state['position']:
                    state['pending']={'side':'BUY','created':now,'candle':candle,'cycle':cycle['id'],'agent':True}
                elif action=='SELL' and state['position']:
                    state['pending']={'side':'SELL','created':now,'reason':'Sygnał agentów z zamkniętej świecy','cycle':cycle['id'],'agent':True}
            if executed:cycle['execution']=executed
            elif state.get('pending'):cycle['execution']={'status':'queued','action':state['pending']['side'],'reason':'Oczekiwanie na świeżą cenę po decyzji.'}
            else:cycle['execution']={'status':'WAIT','reason':cycle['reason']}
            cycle['account']={'cash':state['cash'],'equity':state['lastEquity'] if valid or not state['position'] else None,'realized':state['realized'],'closedTrades':state['tradeCount']}
            state['lastDecision']={'action':action,'reason':cycle['reason'],'candle':candle,'at':cycle['created_at']};state['lastCandle']=candle
            conn.execute('INSERT INTO agent_cycles VALUES(?,?,?)',(cycle['id'],cycle['created_at'],json.dumps(cycle)))
            conn.execute('DELETE FROM agent_cycles WHERE id IN (SELECT id FROM agent_cycles ORDER BY created_at DESC LIMIT -1 OFFSET 5000)')
            if state['position'] and state['position'].get('entryCycle')==cycle['id']:state['position']['entryAudit']=cycle
            if executed and executed['action']=='SELL':
                row=conn.execute('SELECT id,data FROM paper_trades WHERE id=?',(state['lastTradeId'],)).fetchone()
                if row:
                    trade=json.loads(row['data']);trade['exitCycle']=cycle['id'];trade['exitAudit']=cycle
                    conn.execute('UPDATE paper_trades SET data=? WHERE id=?',(json.dumps(trade),row['id']))
        elif state['active'] and analysis and analysis['lastDate']!=state['lastCandle']:
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
    def __init__(self,quote_provider,analysis_provider):
        self.quote_provider=quote_provider;self.analysis_provider=analysis_provider;self.shutdown=threading.Event();self.thread=None
        self.background=False;self.job=None;self.latest=None;self.latest_run=None;self.last_analysis_error=False
    def _analyze(self,job,config):
        try:job['result']=self.analysis_provider(config)
        except Exception:job['error']=True
        finally:job['done'].set()
    def pulse(self):
        state=current_state()
        if not state or not (state['active'] or state['position'] or state['pending']):return
        cfg=state['config'];analysis=None;analysis_error=False
        if self.background:
            # Slow initial pagination never blocks quote-based position protection.
            if self.job and self.job['done'].is_set():
                if self.job['run']==state['run_id']:
                    self.latest=self.job.get('result');self.latest_run=self.job['run'];self.last_analysis_error=self.job.get('error',False)
                self.job=None
            if self.latest_run==state['run_id']:
                analysis=self.latest;analysis_error=self.last_analysis_error
            if self.job is None and (state['active'] or cfg['engine']=='agents'):
                self.job={'run':state['run_id'],'done':threading.Event()}
                threading.Thread(target=self._analyze,args=(self.job,dict(cfg)),daemon=True).start()
        else:
            try:
                if state['active'] or cfg['engine']=='agents':analysis=self.analysis_provider(cfg)
            except Exception:analysis_error=True
        try:
            if cfg['market']=='perpetual':
                q={**okx_data.ticker(cfg['instrument'],'perpetual'),'instrument':cfg['instrument'],'status':'ok'}
                q['asOf']=datetime.fromtimestamp(q['timestamp'],timezone.utc).isoformat()
            else:q=self.quote_provider(cfg['instrument'],cfg['source'])
        except Exception:q={'status':'error','instrument':cfg['instrument']}
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
    def start(self):self.background=True;self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):self.shutdown.set();self.thread.join(timeout=2)


def save_research(record):
    record={**record,'id':str(uuid.uuid4()),'verified':False}
    with storage(True) as conn:conn.execute('INSERT INTO strategy_research VALUES(?,?,?)',(record['id'],record['fetchedAt'],json.dumps(record)))
    return record

def research_records():
    with storage() as conn:return [json.loads(r['data']) for r in conn.execute('SELECT data FROM strategy_research ORDER BY created_at DESC LIMIT 30')]


def save_backtest(report):
    record={**report,'id':str(uuid.uuid4()),'created_at':now_iso()}
    with storage(True) as conn:conn.execute('INSERT INTO bot_backtests VALUES(?,?,?)',(record['id'],record['created_at'],json.dumps(record)))
    return record


def backtest_records():
    with storage() as conn:
        return [{k:v for k,v in json.loads(r['data']).items() if k not in ('equity','trades','blockedEntries')} for r in conn.execute('SELECT data FROM bot_backtests ORDER BY created_at DESC LIMIT 20')]


def backtest_record(identifier):
    with storage() as conn:
        row=conn.execute('SELECT data FROM bot_backtests WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Nie znaleziono raportu historycznego.')
        return json.loads(row['data'])
