"""Durable, demo-only order state machine. Exchange snapshots are authoritative.

Network outcomes are never inferred from a timeout. Only one owner may run this
executor; server startup holds the common database worker lease.
"""
import hashlib
import json
import threading
import time
import uuid
from datetime import datetime,timezone
from decimal import Decimal
import contract_specs
import decision_engine
import okx_demo
import okx_data
import runtime_ops
import strategy_registry
from user_data import database,now_iso

MUTEX=threading.RLock()
TERMINAL={'filled','canceled','rejected'}


def schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS demo_state(id INTEGER PRIMARY KEY,data TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS demo_orders(id TEXT PRIMARY KEY,created_at TEXT,data TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS demo_fills(id TEXT PRIMARY KEY,created_at TEXT,data TEXT)')


def load():
    with database() as conn:
        schema(conn);row=conn.execute('SELECT data FROM demo_state WHERE id=1').fetchone()
    return json.loads(row['data']) if row else None


def save(state):
    with database() as conn:schema(conn);conn.execute('INSERT INTO demo_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(json.dumps(state),))


def orders():
    with database() as conn:schema(conn);return [json.loads(r['data']) for r in conn.execute('SELECT data FROM demo_orders ORDER BY created_at')]


def write_order(order):
    with database() as conn:
        schema(conn);conn.execute('INSERT INTO demo_orders VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(order['id'],order['created_at'],json.dumps(order)))


def status():
    with database() as conn:schema(conn);all_fills=[json.loads(r['data']) for r in conn.execute('SELECT data FROM demo_fills ORDER BY created_at DESC')]
    fills=all_fills[:100]
    state=load();slippages=[]
    for o in orders():
        if o.get('avgPx') and (o.get('plan') or {}).get('referencePx'):
            slippages.append(o['plan']['side']*(float(o['avgPx'])/o['plan']['referencePx']-1)*10000)
    return {'environment':'demo','configured':okx_demo.configured(),'state':state,'orders':orders()[-100:],'fills':fills,
            'executionMetrics':{'observedEntrySlippageBps':slippages[-100:],'latestEntrySlippageBps':slippages[-1] if slippages else None,
                                'equityChangeUSDT':state.get('lastEquity',state['config']['capital'])-state['config']['capital'] if state else None,
                                'netFeesUSDT':-sum(float(f.get('fee') or 0) for f in all_fills if f.get('feeCcy')=='USDT'),
                                'ledgerComplete':not any(o.get('auditIncomplete') for o in orders())},
            'notice':'Wyłącznie konto OKX Demo. Połączenie i zlecenia wymagają klucza demonstracyjnego oraz zatwierdzonej wersji. Timeout pozostawia stan nieznany; bot uzgadnia z giełdą i blokuje nowe wejścia.'}


def start(version_id):
    with MUTEX:
        version=strategy_registry.get(version_id,True);cfg=version['config']
        if cfg['market']!='perpetual' or cfg['source']!='okx' or cfg['engine']!='agents':raise ValueError('Wykonawca Demo obsługuje zatwierdzone USDT perpetual i zespół agentów.')
        if not okx_demo.configured():raise ValueError('Brak kluczy OKX Demo; użyj narzędzia konfiguracji poza czatem.')
        old=load()
        if old and (old.get('position') or any(o['state'] not in TERMINAL for o in orders())):raise ValueError('Najpierw uzgodnij i zamknij istniejące zlecenia/pozycję demo.')
        if old and (old.get('halted')=='drawdown' or (old.get('halted')=='daily' and old.get('day')==datetime.now(timezone.utc).date().isoformat())):raise ValueError('Zadziałał limit konta demo. Start nie zeruje limitów.')
        if old and old.get('halted') and not old.get('reconciled'):raise ValueError('Najpierw potwierdź uzgodnienie niepewnego stanu Demo.')
        state={**(old or {}),'active':True,'versionId':version_id,'config':cfg,'status':'Oczekiwanie na weryfikację konta i uzgodnienie stanu.',
               'reconciled':False,'updated_at':now_iso(),'manualClose':False,'halted':None}
        save(state);runtime_ops.event('demo_start','Zlecono start zatwierdzonej wersji wyłącznie na koncie demonstracyjnym.','demo')
    return status()


def stop(close=False):
    with MUTEX:
        state=load()
        if state:
            state.update(active=False,manualClose=bool(close),status='Nowe wejścia zatrzymane; monitorowanie i zlecenia ochronne pozostają aktywne.')
            save(state)
    return status()


def positive(value,allow_zero=False):return contract_specs.decimal(value,not allow_zero)


class Executor:
    def __init__(self,client=None):self.client=client or okx_demo.Client()
    def request(self,method,path,params=None):return self.client.request(method,path,params)
    def quote(self,cfg):
        inst=okx_data.symbol(cfg['instrument'],'perpetual')
        tick=self.request('GET','/api/v5/market/ticker',{'instId':inst});mark=self.request('GET','/api/v5/public/mark-price',{'instType':'SWAP','instId':inst})
        if len(tick)!=1 or len(mark)!=1 or tick[0].get('instId')!=inst or mark[0].get('instId')!=inst:raise ValueError('Nie potwierdzono instrumentu notowań Demo.')
        q=tick[0];m=mark[0];stamp=okx_data.number(q['ts'])/1000
        return {'status':'ok','instrument':cfg['instrument'],'sourceSymbol':inst,'currency':'USDT','provider':'OKX','environment':'demo',
                'price':okx_data.number(q['last']),'bid':okx_data.number(q['bidPx']),'ask':okx_data.number(q['askPx']),
                'timestamp':stamp,'asOf':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
                'markPrice':okx_data.number(m['markPx']),'markTimestamp':okx_data.number(m['ts'])/1000}
    def halt(self,state,reason,kind='review'):
        state.update(active=False,halted=kind,status=reason);save(state);runtime_ops.event('demo_halt',reason,'demo')
    def snapshot(self,cfg):
        account=self.request('GET','/api/v5/account/config')
        if len(account)!=1 or account[0].get('posMode')!='net_mode' or not account[0].get('uid'):raise ValueError('Konto Demo wymaga potwierdzonej tożsamości i net_mode; ustawienie nie jest zmieniane automatycznie.')
        perms=set(account[0].get('perm','').split(','))
        if 'trade' not in perms or 'withdraw' in perms:raise ValueError('Klucz Demo musi mieć odczyt/handel bez wypłat.')
        positions=self.request('GET','/api/v5/account/positions',{'instType':'SWAP'})
        opened=[p for p in positions if positive(abs(Decimal(p.get('pos') or '0')),True)>0]
        pending=self.request('GET','/api/v5/trade/orders-pending',{'instType':'SWAP'})
        algos=[]
        for kind in ('oco','conditional'):algos+=self.request('GET','/api/v5/trade/orders-algo-pending',{'instType':'SWAP','ordType':kind})
        balance=self.request('GET','/api/v5/account/balance',{'ccy':'USDT'})
        if len(balance)!=1:raise ValueError('Brak jednoznacznego salda USDT Demo.')
        detail=next((d for d in balance[0].get('details',[]) if d.get('ccy')=='USDT'),None)
        if not detail:raise ValueError('Brak salda USDT w odpowiedzi Demo.')
        eq=float(positive(detail['eq'],True));available=float(positive(detail.get('availBal') or '0',True))
        return {'positions':opened,'pending':pending,'algos':algos,'equity':eq,'available':available,
                'accountHash':hashlib.sha256(str(account[0].get('uid','')).encode()).hexdigest()}
    def reconcile_orders(self,state):
        for order in orders():
            if order['state'] in TERMINAL:continue
            try:
                rows=self.request('GET','/api/v5/trade/order',{'instId':order['instId'],'clOrdId':order['id']})
            except okx_demo.ApiError as error:
                if error.code=='51603':
                    if order['state']=='prepared':order['state']='canceled';write_order(order);continue
                    self.halt(state,'Nie odnaleziono zlecenia o niepewnym wyniku. Wymagana weryfikacja historii OKX Demo.','uncertain');continue
                raise
            if len(rows)!=1 or rows[0].get('clOrdId')!=order['id']:raise ValueError('Nie potwierdzono tożsamości zlecenia Demo.')
            row=rows[0];remote=row.get('state')
            if remote not in ('live','partially_filled','filled','canceled'):raise ValueError('Nieznany stan zlecenia Demo.')
            order.update(state=remote,ordId=row['ordId'],filled=row.get('accFillSz','0'),avgPx=row.get('avgPx',''),lastRead=now_iso())
            write_order(order)
            expired=remote=='live' and time.time()-datetime.fromisoformat(order['created_at']).timestamp()>10
            stopped_entry=order['kind']=='entry' and not state.get('active') and remote in ('live','partially_filled')
            if (remote=='partially_filled' or expired or stopped_entry) and not order.get('cancelAttempted'):
                order['cancelAttempted']=True;write_order(order)
                try:self.request('POST','/api/v5/trade/cancel-order',{'instId':order['instId'],'clOrdId':order['id']})
                except (okx_demo.ApiError,okx_demo.UnknownOutcome):pass
                runtime_ops.event('partial_fill','Częściowe wykonanie: wstrzymano wejścia, zlecono anulowanie pozostałej ilości.','demo')
            if Decimal(order.get('filled') or '0')>0:
                cursor=None
                for page in range(50):
                    params={'instType':'SWAP','instId':order['instId'],'ordId':order['ordId'],'limit':'100'}
                    if cursor is not None:params['after']=cursor
                    fills=self.request('GET','/api/v5/trade/fills',params)
                    with database() as conn:
                        schema(conn)
                        for fill in fills:
                            if fill.get('ordId')!=order['ordId']:raise ValueError('Wykonanie innego zlecenia.')
                            key=order['instId']+':'+str(fill['tradeId'])
                            conn.execute('INSERT OR IGNORE INTO demo_fills VALUES(?,?,?)',(key,now_iso(),json.dumps(fill)))
                    if len(fills)<100:break
                    oldest=fills[-1].get('billId')
                    if not oldest or (cursor is not None and int(oldest)>=int(cursor)):
                        order['auditIncomplete']=True;write_order(order);self.halt(state,'Nie potwierdzono pełnego dziennika wykonań Demo.');break
                    cursor=oldest
                else:
                    order['auditIncomplete']=True;write_order(order);self.halt(state,'Dziennik wykonań przekracza limit odczytu; wymagana weryfikacja.')
                if order['kind']=='entry' and order['request'].get('px') and order.get('avgPx'):
                    if Decimal(order['plan']['side'])*(Decimal(order['avgPx'])-Decimal(order['request']['px']))>0:
                        self.halt(state,'Cena wykonania Demo przekracza limit zlecenia. Nowe wejścia zablokowane.')
    def submit(self,state,body,kind,plan=None):
        # Persist BEFORE the network call. A crash in submitting/unknown is
        # reconciled by clOrdId and is never blindly re-submitted.
        identifier='iw'+uuid.uuid4().hex[:30];body={**body,'clOrdId':identifier}
        order={'id':identifier,'created_at':now_iso(),'state':'prepared','kind':kind,'instId':body['instId'],'request':body,'plan':plan}
        if kind=='entry' and getattr(self,'stop_event',None) is not None and self.stop_event.is_set():
            order['state']='canceled';write_order(order);return order
        write_order(order);order['state']='submitting';write_order(order)
        try:
            rows=self.request('POST','/api/v5/trade/order',body)
            if len(rows)!=1 or not rows[0].get('ordId'):raise okx_demo.UnknownOutcome('Brak identyfikatora giełdowego.')
            order.update(state='submitted',ordId=rows[0]['ordId'])
        except okx_demo.ApiError as error:order.update(state='rejected',errorCode=error.code)
        except Exception:
            order['state']='unknown';self.halt(state,'Nieznany wynik wysłania zlecenia. Nie ponawiamy wejścia; wymagane uzgodnienie.','uncertain')
        write_order(order);return order
    def close_owned(self,state,position,reason):
        existing=[o for o in orders() if o['kind']=='close' and o['state'] not in TERMINAL]
        if existing:return
        self.submit(state,{'instId':position['instId'],'tdMode':'isolated','posSide':'net','side':'sell' if Decimal(position['pos'])>0 else 'buy',
                           'ordType':'market','sz':str(abs(Decimal(position['pos']))),'reduceOnly':True},'close')
        state['status']=reason;save(state)
    def protection(self,state,position,entry,algos):
        plan=entry['plan'];size=abs(Decimal(position['pos']));side='sell' if Decimal(position['pos'])>0 else 'buy'
        expected={entry.get('protectionId')}
        expected.update(a.get('attachAlgoClOrdId') for a in entry['request'].get('attachAlgoOrds',[]))
        expected.discard(None)
        matches=[a for a in algos if a.get('algoClOrdId') in expected]
        if matches:
            a=matches[0]
            valid=(a.get('instId')==position['instId'] and a.get('side')==side and str(a.get('reduceOnly')).lower()=='true'
                   and Decimal(a.get('sz') or '0')>=size and Decimal(a.get('slTriggerPx') or '0')==Decimal(plan['slTriggerPx'])
                   and Decimal(a.get('tpTriggerPx') or '0')==Decimal(plan['tpTriggerPx']))
            if valid:return True
            self.halt(state,'Niezgodna ilość lub parametry ochrony Demo; zlecono zamknięcie zarządzanej pozycji.');self.close_owned(state,position,'Niezgodna ochrona');return False
        if entry.get('protectionState') in ('submitting','unknown','submitted'):
            self.halt(state,'Nie potwierdzono ochrony na giełdzie Demo; zlecono zamknięcie zarządzanej pozycji.');self.close_owned(state,position,'Brak potwierdzonej ochrony');return False
        identifier='ip'+uuid.uuid4().hex[:30];entry.update(protectionId=identifier,protectionState='submitting');write_order(entry)
        body={'instId':position['instId'],'tdMode':'isolated','posSide':'net','side':side,'ordType':'oco','sz':str(size),'reduceOnly':True,
              'algoClOrdId':identifier,'slTriggerPx':plan['slTriggerPx'],'slOrdPx':'-1','slTriggerPxType':'mark',
              'tpTriggerPx':plan['tpTriggerPx'],'tpOrdPx':'-1','tpTriggerPxType':'mark'}
        try:
            rows=self.request('POST','/api/v5/trade/order-algo',body)
            entry.update(protectionState='submitted',algoId=rows[0]['algoId']);write_order(entry)
            # Submission ACK is not proof of working protection. Confirm it.
            fresh=self.request('GET','/api/v5/trade/orders-algo-pending',{'instType':'SWAP','ordType':'oco','instId':position['instId']})
            return self.protection(state,position,entry,fresh)
        except Exception:
            entry['protectionState']='unknown';write_order(entry)
            self.halt(state,'Ochrona nie została potwierdzona; zlecono awaryjne reduce-only Demo.');self.close_owned(state,position,'Błąd ochrony');return False
    def pulse(self,analysis,quote):
        with MUTEX:
            state=load()
            if not state:return
            cfg=state['config'];self.reconcile_orders(state);snapshot=self.snapshot(cfg);inst=okx_data.symbol(cfg['instrument'],'perpetual')
            local=orders();ids={o['id'] for o in local}
            if any(o.get('clOrdId') not in ids for o in snapshot['pending']):self.halt(state,'Na koncie Demo są niezarządzane zlecenia. Nie są automatycznie anulowane.');return
            entries=[o for o in local if o['kind']=='entry' and o.get('plan') and not o.get('positionClosed') and Decimal(o.get('filled') or '0')>0]
            pos=snapshot['positions']
            if len(pos)>1 or any(p.get('instId')!=inst or p.get('mgnMode')!='isolated' or p.get('posSide') not in ('net','') for p in pos):self.halt(state,'Niezgodna lub niezarządzana pozycja Demo.');return
            if pos and not entries:self.halt(state,'Pozycja Demo nie ma zarządzanego zlecenia wejścia; wymagana ręczna weryfikacja.');return
            if state.get('accountHash') and state['accountHash']!=snapshot['accountHash']:self.halt(state,'Klucz wskazuje inne konto Demo.');return
            state.setdefault('baselineEquity',snapshot['equity']);state['accountHash']=snapshot['accountHash']
            equity=cfg['capital']+snapshot['equity']-state['baselineEquity'];now=time.time();day=datetime.now(timezone.utc).date().isoformat()
            if state.get('day')!=day:state.update(day=day,dayEquity=equity)
            state['peakEquity']=max(state.get('peakEquity',equity),equity)
            halted=decision_engine.risk_halt(equity,state['peakEquity'],state['dayEquity'],cfg)
            if halted:self.halt(state,'Limit obsunięcia alokacji Demo.' if halted=='drawdown' else 'Limit straty dnia alokacji Demo.',halted)
            state.update(lastEquity=equity,lastSnapshot=now,reconciled=True,updated_at=now_iso())
            if state.get('position') and not pos:state['lastExitCandle']=state.get('lastCandle')
            state['position']=pos[0] if pos else None
            if not pos:
                # Stale native protection must never affect a later position.
                owned_algos={o.get('protectionId') for o in local}
                for o in local:
                    owned_algos.update(a.get('attachAlgoClOrdId') for a in o['request'].get('attachAlgoOrds',[]))
                owned_algos.discard(None);owned_algos.discard('')
                stale=[a for a in snapshot['algos'] if a.get('algoClOrdId') in owned_algos]
                if stale:
                    self.request('POST','/api/v5/trade/cancel-algos',[{'instId':a['instId'],'algoId':a['algoId']} for a in stale])
                    state['status']='Usuwanie wcześniejszej ochrony; brak nowych wejść do potwierdzenia.';save(state);return
                if any(a.get('algoClOrdId') not in owned_algos for a in snapshot['algos']):self.halt(state,'Na koncie Demo są niezarządzane zlecenia algorytmiczne.');return
                for entry in entries:
                    if entry['state'] in TERMINAL:
                        entry['flatReads']=entry.get('flatReads',0)+1
                        if entry['flatReads']>=2:entry['positionClosed']=True
                        write_order(entry)
                if any(not e.get('positionClosed') for e in entries):state['status']='Potwierdzanie płaskiej pozycji po wykonaniu.';save(state);return
            if pos:
                entry=entries[-1]
                if Decimal(pos[0]['pos'])*Decimal(entry['plan']['side'])<=0 or abs(Decimal(pos[0]['pos']))>Decimal(entry.get('filled') or '0'):
                    self.halt(state,'Ilość lub kierunek pozycji Demo nie zgadza się ze zleceniem.');return
                protected=self.protection(state,pos[0],entry,snapshot['algos'])
                state['protectionConfirmed']=protected
                if state.get('manualClose') or state.get('halted') in ('drawdown','daily'):self.close_owned(state,pos[0],'Zamknięcie zarządzanej pozycji Demo')
            else:state['protectionConfirmed']=None
            if not state.get('halted'):
                state['status']='Stan Demo uzgodniony; '+('pozycja z potwierdzoną ochroną.' if pos and state.get('protectionConfirmed') else 'oczekiwanie na pełny sygnał.' if state['active'] else 'nowe wejścia zatrzymane.')
            save(state)
            if any(o['state'] not in TERMINAL for o in orders()):return
            # Expired/revoked versions block entries but do not remove protection.
            try:strategy_registry.get(state['versionId'],True)
            except ValueError:self.halt(state,'Wersja strategii nie ma aktualnego dopuszczenia Demo.');return
            from paper_bot import fresh
            valid=fresh(quote,cfg['instrument'],now,'USDT','okx','perpetual')
            local_position=None
            if pos:
                p=pos[0];size=float(abs(Decimal(p['pos'])));unit=float(entries[-1]['plan']['units'])/float(entries[-1]['plan']['contracts'])
                local_position={'side':1 if Decimal(p['pos'])>0 else -1,'units':size*unit,'entry':float(p['avgPx']),
                                'margin':float(p.get('margin') or entries[-1]['plan']['margin']),'funding':0}
            gate_state={**state,'cash':min(snapshot['available'],max(0,equity)),'position':local_position,'riskHalted':state.get('halted')}
            result=decision_engine.perpetual_entry(analysis,quote,cfg,gate_state,now,valid)
            state.update(lastDecision=result['action'],lastReason='; '.join(result['reasons']) or result['reason'],lastCandle=result['candle'])
            if result['action']=='CLOSE' and pos:self.close_owned(state,pos[0],'Przeciwny sygnał strategii')
            elif result['action'] in ('LONG','SHORT') and state['active'] and not pos and result['candle']!=state.get('lastSubmittedCandle'):
                spec=contract_specs.fetch(cfg['instrument'],lambda p,q:self.request('GET',p,q))
                fees=self.request('GET','/api/v5/account/trade-fee',{'instType':'SWAP','instFamily':cfg['instrument']+'-USDT'})
                if not fees or abs(float(fees[0]['taker']))*10000>cfg['costs']:raise ValueError('Prowizja Demo przekracza założenie zatwierdzonego testu.')
                plan=contract_specs.round_plan(result['plan'],cfg,spec)
                if Decimal(plan['margin'])>Decimal(str(snapshot['available'])):raise ValueError('Brak wolnego depozytu Demo.')
                self.request('POST','/api/v5/account/set-leverage',{'instId':inst,'mgnMode':'isolated','lever':str(cfg['leverage'])})
                # Re-read prices after potentially slow specification/account
                # calls. Never submit a stale plan; the limit bounds slippage.
                latest_quote=self.quote(cfg);latest_now=time.time()
                latest_valid=fresh(latest_quote,cfg['instrument'],latest_now,'USDT','okx','perpetual')
                latest=decision_engine.perpetual_entry(analysis,latest_quote,cfg,gate_state,latest_now,latest_valid)
                if latest['action']!=result['action'] or not latest['plan']:
                    state.update(lastDecision='WAIT',lastReason='Ponowna ocena przed zleceniem blokuje wejście.');save(state);return
                plan=contract_specs.round_plan(latest['plan'],cfg,spec)
                plan['referencePx']=latest_quote['ask'] if plan['side']==1 else latest_quote['bid']
                flat=self.request('GET','/api/v5/account/positions',{'instType':'SWAP','instId':inst})
                if any(Decimal(p.get('pos') or '0')!=0 for p in flat):self.halt(state,'Pozycja zmieniła się przed wysłaniem wejścia Demo.');return
                state['lastSubmittedCandle']=result['candle'];save(state)
                from decimal import ROUND_FLOOR,ROUND_CEILING
                tick=Decimal(spec['tickSz']);limit=(Decimal(str(plan['entry']))/tick).to_integral_value(rounding=ROUND_FLOOR if plan['side']==1 else ROUND_CEILING)*tick
                body={'instId':inst,'tdMode':'isolated','posSide':'net','side':'buy' if plan['side']==1 else 'sell','ordType':'limit','px':format(limit,'f'),'sz':plan['contracts'],
                      'attachAlgoOrds':[{'attachAlgoClOrdId':'ia'+uuid.uuid4().hex[:30],'slTriggerPx':plan['slTriggerPx'],'slOrdPx':'-1','slTriggerPxType':'mark',
                                         'tpTriggerPx':plan['tpTriggerPx'],'tpOrdPx':'-1','tpTriggerPxType':'mark'}]}
                submitted=self.submit(state,body,'entry',plan)
                if submitted['state']=='submitted':
                    # Do not wait for the next timer to protect an ACKed partial
                    # fill. Attached protection is still independently verified.
                    self.reconcile_orders(state)
                    current=self.request('GET','/api/v5/account/positions',{'instType':'SWAP','instId':inst})
                    current=[p for p in current if p.get('instId')==inst and Decimal(p.get('pos') or '0')!=0]
                    updated=next(o for o in orders() if o['id']==submitted['id'])
                    if len(current)==1 and Decimal(updated.get('filled') or '0')>0:
                        if abs(Decimal(current[0]['pos']))>Decimal(updated['filled']) or Decimal(current[0]['pos'])*Decimal(plan['side'])<=0:
                            self.halt(state,'Nie potwierdzono ilości/kierunku nowej pozycji Demo.')
                        else:
                            state['position']=current[0]
                            algos=[]
                            for kind in ('oco','conditional'):algos+=self.request('GET','/api/v5/trade/orders-algo-pending',{'instType':'SWAP','ordType':kind,'instId':inst})
                            state['protectionConfirmed']=self.protection(state,current[0],updated,algos)
            save(state)
            runtime_ops.heartbeat('demo-executor',{'status':'reconciled','active':state['active'],'position':bool(pos),'protectionConfirmed':state.get('protectionConfirmed')})


class Service:
    def __init__(self,analysis_provider):
        self.executor=Executor();self.analysis_provider=analysis_provider;self.shutdown=threading.Event();self.wake=threading.Event();self.thread=None;self.job=None;self.latest=None;self.latest_version=None
        self.executor.stop_event=self.shutdown
    def pulse(self):
        state=load()
        runtime_ops.heartbeat('demo-worker',{'status':'configured' if okx_demo.configured() else 'keys_missing'})
        if not state or not okx_demo.configured():runtime_ops.heartbeat('demo-executor',{'status':'idle'});return
        if not (state.get('active') or state.get('position') or any(o['state'] not in TERMINAL for o in orders())):runtime_ops.heartbeat('demo-executor',{'status':'idle'});return
        cfg=state['config'];analysis=None;q={}
        if self.job and self.job['done'].is_set():
            if self.job['version']==state['versionId']:self.latest=self.job.get('result');self.latest_version=self.job['version']
            self.job=None
        if self.latest_version==state['versionId']:analysis=self.latest
        if self.job is None and state['active']:
            job={'version':state['versionId'],'done':threading.Event()};self.job=job
            def analyze():
                try:job['result']=self.analysis_provider(dict(cfg))
                except Exception:job['result']=None
                finally:job['done'].set()
            threading.Thread(target=analyze,daemon=True).start()
        try:
            try:
                q=self.executor.quote(cfg)
            except Exception:pass
            self.executor.pulse(analysis,q)
        except Exception:
            runtime_ops.event('demo_cycle_error','Nie potwierdzono danych lub stanu giełdy Demo. Nowe wejścia wstrzymane do uzgodnienia.','demo')
            state=load();state.update(reconciled=False,status='Błąd uzgodnienia: brak nowych wejść. Ochrona giełdowa nie jest usuwana.');save(state)
    def run(self):
        while not self.shutdown.is_set():
            began=time.monotonic()
            try:self.pulse()
            except Exception:pass
            # Stream bursts coalesce into one authoritative REST snapshot.
            self.shutdown.wait(max(0,1-(time.monotonic()-began)))
            self.wake.wait(5);self.wake.clear()
    def start(self):
        from demo_stream import Feed
        self.feed=Feed(self.wake);self.feed.start()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):
        self.shutdown.set()
        self.wake.set()
        if hasattr(self,'feed'):self.feed.stop()
        if self.thread:self.thread.join(timeout=20)
