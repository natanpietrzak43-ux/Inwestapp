"""Forward-only paper execution for OKX linear perpetual market observations."""
import json
import uuid
from datetime import datetime,timezone
import agent_pipeline
import leveraged_trading as model
from decision_engine import risk_halt


def advance(conn,state,quote,analysis,now,analysis_error,event):
    from paper_bot import fresh
    cfg=state['config'];p=state['position'];executed=None;plan=None
    stamp=datetime.fromtimestamp(now,timezone.utc).isoformat()
    cycle={'id':str(uuid.uuid4()),'created_at':stamp,'version':'2','market':'perpetual',
           'accountId':state['accountId'],'source':cfg['source'],'currency':cfg['currency'],
           'instrument':cfg['instrument'],'timeframe':cfg['timeframe'],'stages':[],
           'quoteAt':quote.get('asOf'),'quotePrice':quote.get('price'),'candle':None}
    valid=fresh(quote,cfg['instrument'],now,cfg['currency'],cfg['source'],'perpetual')
    state.update(lastHeartbeat=stamp,lastQuoteValid=valid)
    def close(reason,liquidation=False):
        nonlocal p,executed
        fill=(quote['bid'] if p['side']==1 else quote['ask'])*(1-p['side']*cfg['slippage']/10000)
        result=model.settlement(p,fill,cfg,liquidation)
        trade={**p,**result,'id':str(uuid.uuid4()),'instrument':cfg['instrument'],'preset':cfg['preset'],
               'market':'perpetual','currency':'USDT','source':'okx','exit':fill,'exit_at':quote['asOf'],
               'created_at':stamp,'reason':reason,'accountId':state['accountId'],'exitCycle':cycle['id']}
        conn.execute('INSERT INTO paper_trades VALUES(?,?,?)',(trade['id'],stamp,json.dumps(trade)))
        state['cash']+=result['credit'];state['realized']+=result['pnl'];state['tradeCount']+=1
        state.update(position=None,pending=None,lastTradeId=trade['id'],lastExitCandle=analysis.get('lastDate') if analysis else state.get('lastCandle'))
        p=None;executed={'status':'filled','action':'CLOSE','reason':reason};event(conn,'close',reason)
    if valid:
        state['lastQuote']=quote;mark=quote['markPrice']
        if p:model.funding(p,mark,now,cfg)
        equity=model.value(state['cash'],p,mark,cfg)
        day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
        if state.get('day')!=day:state.update(day=day,dayEquity=equity)
        state['peakEquity']=max(state.get('peakEquity',equity),equity)
        if p and model.liquidated(p,mark,cfg):close('Likwidacja modelowa — utrata depozytu izolowanego',True)
        equity=model.value(state['cash'],p,mark,cfg)
        halted=risk_halt(equity,state['peakEquity'],state['dayEquity'],cfg)
        if halted:
            state.update(active=False,pending=None,riskHalted=halted)
            if p:close('Limit obsunięcia' if halted=='drawdown' else 'Limit straty dnia UTC')
        elif p:
            executable=quote['bid'] if p['side']==1 else quote['ask']
            if p['side']*(executable-p['stop'])<=0:close('Stop loss — pierwsza zaobserwowana cena')
            elif p['side']*(executable-p['target'])>=0:close('Take profit — pierwsza zaobserwowana cena')
    from decision_engine import perpetual_entry
    decision=perpetual_entry(analysis,quote,cfg,state,now,valid)
    check=decision['quality'];technical=decision['technical'];action=decision['proposal']
    reason=decision['reason'];reasons=decision['reasons'];plan=decision['plan'];candle=decision['candle'];final=decision['action']
    cycle['candle']=candle
    cycle['stages']=[{'id':'data','name':'Dane kontraktu OKX','status':'received' if valid else 'blocked','reasons':[quote.get('sourceSymbol','Brak kontraktu')]},check]
    for group,label in [('trend','Trend'),('momentum','Momentum'),('volume','Wolumen'),('regime','Reżim'),('context','Kontekst')]:
        readings=[r for r in technical['checks'] if r['group']==group] if technical else []
        cycle['stages'].append({'id':group,'name':'Agent: '+label,'status':'passed' if readings else 'skipped','reasons':[r['name']+': '+r['detail'] for r in readings]})
    cycle['stages'] += [{'id':'supervisor','name':'Agent nadrzędny','status':action,'reasons':[reason]},
                        {'id':'risk','name':'Agent ryzyka futures','status':'approved' if final!='WAIT' else 'blocked','reasons':reasons or ['Zgodność limitów i modelowego depozytu.']}]
    pending=state.get('pending')
    if pending and now-pending['created']>1200:state['pending']=None;pending=None
    if pending and pending['side'] in ('LONG','SHORT') and pending['side']!=final:state['pending']=None;pending=None
    if pending and valid and quote['timestamp']>pending['created']:
        if pending['side']=='CLOSE' and p:close(pending['reason'])
        elif pending['side']==final and plan and not p:
            p={**plan,'entry_at':quote['asOf'],'decisionAt':pending['created'],'signalCandle':pending['candle'],
               'entryCycle':cycle['id'],'entryAudit':None}
            state['cash']-=p['margin']+p['entryFee'];state.update(position=p,pending=None)
            executed={'status':'filled','action':final,'reason':'Świeża cena po decyzji i ponowna zgoda ryzyka.'};event(conn,'open',final+' · perpetual · '+str(cfg['leverage'])+'x')
    if not executed and not state.get('pending'):
        if final in ('LONG','SHORT') and state['active'] and not p:state['pending']={'side':final,'created':now,'candle':candle}
        elif final=='CLOSE' and p:state['pending']={'side':'CLOSE','created':now,'candle':candle,'reason':'Przeciwny pełny sygnał futures'}
    if valid:state['lastEquity']=model.value(state['cash'],p,quote['markPrice'],cfg)
    state['status']='Brak świeżego ticker/mark price; brak wykonań.' if not valid else 'Futures papierowe: '+('monitorowanie i analiza.' if state['active'] else 'nowe wejścia zatrzymane; ochrona pozycji pozostaje aktywna.')
    if analysis_error:state['status']+=' Pobranie analizy nie powiodło się.'
    reported_action='CLOSE' if executed and executed['action']=='CLOSE' else final
    cycle.update(action=reported_action,reason=executed['reason'] if reported_action=='CLOSE' else '; '.join(reasons) if reasons else reason,plan=plan,
                 execution=executed or ({'status':'queued','action':state['pending']['side'],'reason':'Oczekiwanie na cenę po decyzji.'} if state.get('pending') else {'status':'WAIT','reason':reason}),
                 account={'cash':state['cash'],'equity':state['lastEquity'] if valid or not p else None,'realized':state['realized'],'closedTrades':state['tradeCount']})
    if executed and executed['action']=='CLOSE':
        cycle['stages'].append({'id':'protection','name':'Ochrona / zamknięcie futures','status':'approved','reasons':[executed['reason']]})
        row=conn.execute('SELECT data FROM paper_trades WHERE id=?',(state['lastTradeId'],)).fetchone();trade=json.loads(row['data']);trade['exitAudit']=cycle
        conn.execute('UPDATE paper_trades SET data=? WHERE id=?',(json.dumps(trade),state['lastTradeId']))
    conn.execute('INSERT INTO agent_cycles VALUES(?,?,?)',(cycle['id'],stamp,json.dumps(cycle)))
    conn.execute('DELETE FROM agent_cycles WHERE id IN (SELECT id FROM agent_cycles ORDER BY created_at DESC LIMIT -1 OFFSET 5000)')
    if p and executed:p['entryAudit']=cycle
    state.update(lastCycle=cycle['id'],lastCandle=candle or state.get('lastCandle'),lastDecision={'action':reported_action,'reason':cycle['reason'],'candle':candle,'at':stamp})
