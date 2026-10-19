"""Auditable local analytical agents. Deterministic rules, not LLM forecasts.

Analysts cannot execute trades. The supervisor combines groups without counting
correlated indicators as extra votes. The independent risk agent has final veto.
"""
import math
import time
import uuid
from datetime import datetime, timezone

from analysis_engine import validate_bars
from market_data import INSTRUMENTS
from technical_tools import PRESETS, combined_decision
from timeframes import TIMEFRAMES, candle_time

VERSION='1'


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def quality(analysis,quote,cfg,now):
    reasons=[];rows=[];tf=cfg['timeframe'];source=cfg.get('source','reference');key=cfg['instrument']
    currency='USDT' if source=='okx' else 'USD'
    if not analysis:reasons.append('Brak analizy zamkniętych świec od dostawcy.')
    else:
        try:rows=validate_bars(analysis['bars'],tf)
        except (ValueError,TypeError,KeyError,IndexError):reasons.append('Niepoprawne, niezamknięte lub zbyt krótkie OHLCV.')
        if analysis.get('mode')!='live' or analysis.get('stale'):reasons.append('Analiza demonstracyjna, importowana lub nieaktualna.')
        if analysis.get('source','reference')!=source or analysis.get('currency','USD')!=currency:reasons.append('Źródło lub waluta świec nie zgadza się z kontem.')
        if analysis.get('instrument',{}).get('id')!=key or analysis.get('timeframe')!=tf:reasons.append('Instrument lub interwał świec nie zgadza się z botem.')
        try:
            fetched=datetime.fromisoformat(analysis['fetchedAt'].replace('Z','+00:00'))
            if fetched.tzinfo is None or not -1<=now-fetched.timestamp()<=120:reasons.append('Brak aktualnego potwierdzenia pobrania świec (120 s).')
        except (ValueError,TypeError,KeyError):reasons.append('Brak czasu pobrania świec.')
    try:
        if (quote.get('status')!='ok' or quote.get('instrument')!=key or quote.get('currency')!=currency
            or not finite(quote.get('price')) or quote['price']<=0 or not finite(quote.get('timestamp'))
            or not 0<=now-quote['timestamp']<=(120 if INSTRUMENTS[key]['kind']=='crypto' else 1200)):
            reasons.append('Brak świeżej ceny zgodnej z instrumentem i walutą.')
        if source=='okx' and (quote.get('provider')!='OKX' or quote.get('sourceSymbol')!=key+'-USDT'):reasons.append('Cena nie pochodzi z wybranej pary OKX spot.')
        if source=='okx' and (not all(finite(quote.get(k)) and quote[k]>0 for k in ('bid','ask')) or quote['bid']>quote['ask']):reasons.append('Brak poprawnego bid/ask OKX.')
    except (TypeError,KeyError):reasons.append('Niepoprawny odczyt ceny.')
    if rows:
        step=TIMEFRAMES[tf]['seconds'];last=candle_time(rows[-1]['date'],tf).timestamp()
        if analysis.get('lastDate')!=rows[-1]['date']:reasons.append('Ostatnia data analizy nie zgadza się ze świecami.')
        if INSTRUMENTS[key]['kind']=='crypto':
            # Latest closed candle remains current until the next one closes;
            # allow 120 s for publishing that next candle, not 120 s per candle.
            if not 0<=now-(last+step)<step+120:reasons.append('Brakuje ostatniej oczekiwanej zamkniętej świecy.')
            stamps=[candle_time(r['date'],tf).timestamp() for r in rows]
            if any(b-a!=step for a,b in zip(stamps,stamps[1:])):reasons.append('Historia krypto ma luki; nie uzupełniono ich sztucznie.')
        if finite(quote.get('price')) and abs(quote['price']/rows[-1]['close']-1)*100>cfg.get('max_deviation',3):reasons.append('Cena odjechała za daleko od sygnału świecowego.')
        if source=='okx' and any(finite(quote.get(k)) and abs(quote[k]/rows[-1]['close']-1)*100>cfg.get('max_deviation',3) for k in ('bid','ask')):reasons.append('Wykonywalna cena bid/ask odjechała za daleko od świecy sygnału.')
    return {'id':'quality','name':'Kontrola jakości danych','status':'passed' if not reasons else 'blocked',
            'reasons':reasons,'bars':len(rows),'lastCandle':rows[-1]['date'] if rows else None},rows


def risk(proposal,quality_result,analysis,quote,cfg,state):
    reasons=list(quality_result['reasons']);plan=None;action=proposal['action'];p=state.get('position')
    if action=='BUY':
        if not state.get('active'):reasons.append('Nowe wejścia są zatrzymane.')
        if p:reasons.append('Na koncie jest już jedna pozycja.')
        if state.get('riskHalted'):reasons.append('Konto zatrzymane przez limit ryzyka; potrzebne świadome wznowienie.')
        if not analysis or not analysis.get('historyGuard',{}).get('passed'):reasons.append('Strategia nie przeszła minimalnej blokady historycznej.')
        equity=state.get('lastEquity',state['cash']);peak=state.get('peakEquity',equity);baseline=state.get('dayEquity',equity)
        if peak>0 and (peak-equity)/peak*100>=cfg.get('max_drawdown',10):reasons.append('Przekroczono maksymalne obsunięcie konta.')
        if baseline>0 and equity<=baseline*(1-cfg['daily_loss']/100):reasons.append('Przekroczono limit straty dnia UTC.')
        bid,ask=quote.get('bid'),quote.get('ask')
        if finite(bid) and finite(ask) and 0<bid<=ask:
            spread=(ask-bid)/((ask+bid)/2)*10000
            if spread>cfg.get('max_spread',30):reasons.append('Spread przekracza limit wejścia.')
        elif cfg.get('source')=='okx':reasons.append('Nie można zmierzyć spreadu OKX.')
        try:
            atr=analysis['indicators'][-1]['atr'];entry=(ask if cfg.get('source')=='okx' else quote['price'])*(1+cfg['slippage']/10000)
            if not finite(atr) or atr<=0 or entry<=2*atr:raise ValueError()
            stop=entry-2*atr;target=entry+3*atr;fee=cfg['costs']/10000;slip=cfg['slippage']/10000
            # Include both commissions and a slipped stop execution in sizing.
            per_unit=entry*(1+fee)-stop*(1-slip)*(1-fee)
            budget=equity*cfg['risk']/100
            units=min(state['cash']/(entry*(1+fee)),budget/per_unit,equity*cfg.get('max_exposure',25)/100/entry)
            if not finite(units) or units<=0:raise ValueError()
            plan={'entry':entry,'stop':stop,'target':target,'units':units,'notional':entry*units,'riskBudget':budget,'rewardRisk':1.5,'estimatedStopLoss':per_unit*units}
        except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError):reasons.append('Brak poprawnego ATR lub środków do wyznaczenia pozycji.')
    elif action=='SELL' and not p:reasons.append('Brak pozycji long do zamknięcia; nie otwieramy shorta.')
    elif action=='WAIT':reasons.append(proposal['reason'])
    return {'id':'risk','name':'Agent ryzyka — prawo weta','status':'approved' if not reasons and action!='WAIT' else 'blocked',
            'action':action if not reasons else 'WAIT','reasons':list(dict.fromkeys(reasons)),'plan':plan if not reasons else None}


def evaluate(analysis,quote,cfg,state,now=None):
    now=time.time() if now is None else now
    check,rows=quality(analysis,quote,cfg,now);agents=[];technical=None
    if check['status']=='passed':
        try:
            preset=PRESETS[cfg['preset']]
            technical=combined_decision(rows[-1],analysis['indicators'][-1],preset['tools'],preset['strategy'])
            for group,label in [('trend','Agent trendu'),('momentum','Agent momentum'),('volume','Agent wolumenu'),('regime','Agent reżimu'),('context','Agent kontekstu')]:
                readings=[c for c in technical['checks'] if c['group']==group]
                states=[c['state'] for c in readings]
                vote='bull' if states and all(s=='bull' for s in states) else 'bear' if states and all(s=='bear' for s in states) else 'neutral'
                agents.append({'id':group,'name':label,'status':vote,'readings':readings,'reasons':[c['name']+': '+c['detail'] for c in readings] or ['Brak narzędzia w wybranym zestawie.']})
        except (KeyError,TypeError,ValueError,IndexError):
            check['status']='blocked';check['reasons'].append('Nie udało się obliczyć wymaganych odczytów agentów.')
    proposal={'action':technical['action'],'reason':technical['reason']} if technical else {'action':'WAIT','reason':'Kontrola danych nie pozwala wykonać analiz.'}
    if not agents:
        agents=[{'id':group,'name':label,'status':'skipped','reasons':['Wstrzymano po kontroli jakości danych.']} for group,label in [('trend','Agent trendu'),('momentum','Agent momentum'),('volume','Agent wolumenu'),('regime','Agent reżimu'),('context','Agent kontekstu')]]
    supervisor={'id':'supervisor','name':'Agent nadrzędny','status':proposal['action'],'reasons':[proposal['reason']],
                'groups':technical['groups'] if technical else []}
    gate=risk(proposal,check,analysis,quote,cfg,state)
    return {'id':str(uuid.uuid4()),'version':VERSION,'created_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
            'source':cfg.get('source','reference'),'currency':cfg.get('currency','USD'),'instrument':cfg['instrument'],'timeframe':cfg['timeframe'],
            'candle':check['lastCandle'],'quoteAt':quote.get('asOf'),'quotePrice':quote.get('price'),
            'stages':[{'id':'data','name':'Dane z giełdy','status':'received' if quote.get('status')=='ok' else 'blocked','reasons':[quote.get('provider','Brak źródła')+' · '+quote.get('sourceSymbol','brak pary')]},check,*agents,supervisor,gate],
            'action':gate['action'],'reason':'; '.join(gate['reasons']) if gate['reasons'] else proposal['reason'],
            'plan':gate['plan'],'execution':{'status':'not_submitted','reason':'Ocena nie jest wykonaniem transakcji.'}}
