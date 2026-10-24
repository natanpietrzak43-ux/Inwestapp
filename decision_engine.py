"""Versioned causal strategy evidence and a shared perpetual entry gate."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from datetime import datetime,timezone
import agent_pipeline
import leveraged_trading as model
from timeframes import TIMEFRAMES,candle_time

VERSION='2.0.0'
REFRESH_BARS=24
LOOKBACK=2000


def risk_halt(equity,peak,day_equity,cfg):
    if equity<=peak*(1-cfg['max_drawdown']/100):return 'drawdown'
    if equity<=day_equity*(1-cfg['daily_loss']/100):return 'daily'
    return None


def source_hash():
    digest=hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(path.name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()


BOOT_CODE_HASH=source_hash()


def fingerprint(cfg):
    if source_hash()!=BOOT_CODE_HASH:raise ValueError('Pliki programu zmieniły się podczas pracy. Zatrzymaj serwer i uruchom pełną nową wersję przed walidacją lub startem Demo.')
    digest=hashlib.sha256(BOOT_CODE_HASH.encode())
    digest.update(json.dumps(cfg,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    return digest.hexdigest()


@lru_cache(maxsize=128)
def _evidence(rows_json,cfg_json):
    from bot_backtest import research_run
    rows=json.loads(rows_json);cfg=json.loads(cfg_json)
    import execution_context
    token=execution_context.market_data.set(None)
    try:report=research_run(rows,cfg,ledger=False)
    finally:execution_context.market_data.reset(token)
    return {'passed':report['historyGuard']['passed'],'metrics':report['metrics'],'evidenceEnd':rows[-1]['date'],
            'description':'Badanie reguł wyłącznie na świecach sprzed bieżącej epoki. Bez optymalizacji; nie dowodzi przyszłej przewagi.'}


def evidence(rows,cfg):
    step=TIMEFRAMES[cfg['timeframe']]['seconds']
    last_close=candle_time(rows[-1]['date'],cfg['timeframe']).timestamp()+step
    cutoff=int(last_close//(step*REFRESH_BARS))*step*REFRESH_BARS
    prior=[r for r in rows if candle_time(r['date'],cfg['timeframe']).timestamp()+step<=cutoff][-LOOKBACK:]
    if len(prior)<400:return {'passed':False,'reason':'Minimum 400 wcześniejszych świec do oceny strategii.','evidenceEnd':prior[-1]['date'] if prior else None}
    # Exact data/config form the cache key; revised prices cannot reuse old evidence.
    return dict(_evidence(json.dumps(prior,sort_keys=True,separators=(',',':')),json.dumps(cfg,sort_keys=True,separators=(',',':'))))


def analysis(rows,inds,cfg,now):
    rows=rows[-(LOOKBACK+REFRESH_BARS+1):];inds=inds[-(LOOKBACK+REFRESH_BARS+1):]
    technical=model.signal(rows[-1],inds[-1],cfg)
    guard=evidence(rows,cfg)
    action={'LONG':'BUY','SHORT':'SELL','CLOSE':'SELL','WAIT':'WAIT'}[technical['action']]
    return {'bars':rows,'indicators':inds,'historyGuard':guard,'lastDate':rows[-1]['date'],
            'decision':{'action':action if action!='BUY' or guard['passed'] else 'WAIT','reason':technical['reason'] if action!='BUY' or guard['passed'] else 'Kroczący filtr wcześniejszych danych blokuje wejście.'},
            'instrument':{'id':cfg['instrument']},'timeframe':cfg['timeframe'],'source':cfg['source'],
            'currency':cfg['currency'],'market':cfg['market'],'mode':'live','stale':False,
            'fetchedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),'engineVersion':VERSION}


def perpetual_entry(analysis,quote,cfg,state,now,valid=True):
    check,rows=agent_pipeline.quality(analysis,quote,cfg,now)
    if not valid:check['reasons'].append('Brak świeżego ticker i mark price kontraktu perpetual.')
    elif abs(quote['markPrice']/quote['price']-1)*100>cfg['max_deviation']:check['reasons'].append('Mark price odchyla się od ceny transakcyjnej ponad limit.')
    if check['reasons']:check['status']='blocked'
    technical=None
    if check['status']=='passed':
        try:technical=model.signal(rows[-1],analysis['indicators'][-1],cfg)
        except (KeyError,IndexError,ValueError,TypeError):check['reasons'].append('Niepoprawne odczyty wskaźników futures.');check['status']='blocked'
    action=technical['action'] if technical else 'WAIT';reason=technical['reason'] if technical else 'Kontrola jakości blokuje analizę.'
    p=state.get('position');plan=None;candle=check['lastCandle']
    if p:action='CLOSE' if (action=='LONG' and p['side']==-1) or (action=='SHORT' and p['side']==1) else 'WAIT'
    reasons=list(check['reasons'])
    if action in ('LONG','SHORT'):
        side=1 if action=='LONG' else -1
        if not state['active'] or state.get('riskHalted'):reasons.append('Nowe wejścia zatrzymane przez użytkownika lub limit ryzyka.')
        if cfg['direction'] not in ('both','long' if side==1 else 'short'):reasons.append('Ten kierunek wejścia jest wyłączony.')
        if not analysis.get('historyGuard',{}).get('passed'):reasons.append('Historyczny test modelu nie przeszedł filtra.')
        if candle==state.get('lastExitCandle'):reasons.append('Po wyjściu czekamy na następną zamkniętą świecę.')
        if valid and (quote['ask']-quote['bid'])/((quote['ask']+quote['bid'])/2)*10000>cfg['max_spread']:reasons.append('Spread przekracza limit wejścia.')
        equity=model.value(state['cash'],p,quote['markPrice'],cfg) if valid else state.get('lastEquity',state['cash'])
        if risk_halt(equity,state.get('peakEquity',equity),state.get('dayEquity',equity),cfg):reasons.append('Przekroczony limit kapitału.')
        if not reasons:
            fill=(quote['ask'] if side==1 else quote['bid'])*(1+side*cfg['slippage']/10000)
            plan=model.plan(cfg,state['cash'],equity,fill,analysis['indicators'][-1]['atr'],side,now)
            if not plan:reasons.append('Brak depozytu albo stop za modelową likwidacją.')
    elif action=='WAIT':reasons.append(reason)
    return {'quality':check,'technical':technical,'proposal':action,'action':action if not reasons else 'WAIT',
            'reason':reason,'reasons':reasons,'plan':plan,'candle':candle}
