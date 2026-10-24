"""Replay drives the exact persisted paper executor, in isolated task storage."""
from datetime import datetime,timezone
import json
import tempfile
import execution_context
from analysis_engine import validate_bars,indicators
from timeframes import candle_time,TIMEFRAMES
from user_data import numeric
import decision_engine


def run(rows,cfg,start_date=None,end_date=None,spread_bps=10,ledger=True,start_index=220,bundle=None):
    import paper_bot
    bars=validate_bars(rows,cfg['timeframe'])
    if len(bars)>5000:raise ValueError('Pełny replay: maksymalnie 5000 świec; wybierz krótszą historię.')
    inds=indicators(bars);spread=numeric(spread_bps,0,200)/10000;step=TIMEFRAMES[cfg['timeframe']]['seconds']
    def date(value):
        if not value:return None
        try:return datetime.strptime(value,'%Y-%m-%d').date()
        except (ValueError,TypeError):raise ValueError('Daty testu: RRRR-MM-DD (UTC).') from None
    start,end=date(start_date),date(end_date)
    if start and end and start>end:raise ValueError('Początek wypada po końcu testu.')
    stamps=[candle_time(b['date'],cfg['timeframe']) for b in bars]
    if not 220<=start_index<len(bars):raise ValueError('Początek testu wymaga co najmniej 220 wcześniejszych świec.')
    indices=[i for i in range(start_index,len(bars)) if (not start or stamps[i].date()>=start) and (not end or stamps[i].date()<=end)]
    if not indices:raise ValueError('Pełny bot wymaga 220 świec rozgrzewki i świec w wybranym okresie.')
    curve=[];blocked=[];guards={};events=0
    with tempfile.TemporaryDirectory(prefix='inwestapp-replay-') as temp,execution_context.replay(temp,bundle):
        paper_bot.start({**cfg,'mode':'paper'});run_id=paper_bot.current_state()['run_id']
        def tick(value,when,snapshot,mark=None):
            nonlocal events
            execution_context.clock.set(when)
            q={'status':'ok','instrument':cfg['instrument'],'currency':cfg['currency'],'provider':'OKX' if cfg['source']=='okx' else 'Replay',
               'sourceSymbol':cfg['instrument']+'-USDT'+('-SWAP' if cfg['market']=='perpetual' else ''),
               'price':value,'bid':value*(1-spread/2),'ask':value*(1+spread/2),'markPrice':value if mark is None else mark,'markTimestamp':when,
               'timestamp':when,'asOf':datetime.fromtimestamp(when,timezone.utc).isoformat()}
            paper_bot.advance(run_id,q,snapshot,now=when);events+=1
            return paper_bot.current_state()
        for i in indices:
            now=stamps[i].timestamp();prior=bars[max(0,i-LOOKBACK_PAD):i];prior_inds=inds[max(0,i-LOOKBACK_PAD):i]
            markrow=bundle['marks'][now] if bundle else bars[i]
            snapshot=decision_engine.analysis(prior,prior_inds,cfg,now)
            guards[snapshot['historyGuard'].get('evidenceEnd') or 'warmup']=snapshot['historyGuard']
            if not snapshot['historyGuard']['passed']:blocked.append({'date':bars[i]['date'],'reason':'Kroczący filtr wcześniejszych danych blokuje nowe wejście.'})
            # A later quote is required by the same forward executor. Its price
            # here is the next opening observation, with explicit synthetic spread.
            tick(bars[i]['open'],now,snapshot,markrow['open'])
            state=tick(bars[i]['open'],now+.001,snapshot,markrow['open']);p=state['position']
            if p:
                side=p.get('side',1);adverse=bars[i]['low'] if side==1 else bars[i]['high'];favorable=bars[i]['high'] if side==1 else bars[i]['low']
                liquidation=p.get('liquidationPrice')
                adverse_mark=markrow['low'] if side==1 else markrow['high']
                if liquidation is not None and side*(adverse_mark-liquidation)<=0:
                    state=tick(adverse,now+step*.25,snapshot,adverse_mark)
                elif side*(adverse-p['stop'])<=0:
                    state=tick(p['stop'],now+step*.25,snapshot,adverse_mark)
                elif side*(favorable-p['target'])>=0:
                    state=tick(p['target'],now+step*.5,snapshot,markrow['high'] if side==1 else markrow['low'])
            state=tick(bars[i]['close'],now+step-.01,snapshot,markrow['close'])
            if i==indices[-1] and state['position']:
                execution_context.clock.set(now+step-.009)
                # close_position uses wall clock for live calls; replace only
                # the persisted replay intent timestamp, within this private DB.
                with paper_bot.storage(True) as conn:
                    state=paper_bot._read(conn)
                    state['pending']={'side':'CLOSE' if cfg['market']=='perpetual' else 'SELL','created':now+step-.009,'reason':'Koniec testu'}
                    paper_bot._save(conn,state)
                state=tick(bars[i]['close'],now+step-.008,snapshot,markrow['close'])
            curve.append({'date':bars[i]['date'],'value':state['lastEquity']})
        with paper_bot.storage() as conn:
            trades=[json.loads(r['data']) for r in conn.execute('SELECT data FROM paper_trades ORDER BY created_at,id')]
        final=paper_bot.current_state()
    for trade in trades:
        trade['entryDate']=trade['entry_at'];trade['exitDate']=trade['exit_at'];trade.setdefault('funding',0);trade.setdefault('liquidated',False)
        trade.setdefault('entryFee',0);trade.setdefault('exitFee',0)
        for field in ('entryAudit','exitAudit'):trade.pop(field,None)
    capital=cfg['capital'];peak=capital;dd=0
    for row in curve:peak=max(peak,row['value']);dd=max(dd,(peak-row['value'])/peak*100)
    gains=sum(t['pnl'] for t in trades if t['pnl']>0);losses=-sum(t['pnl'] for t in trades if t['pnl']<0)
    stats={'returnPct':(final['cash']/capital-1)*100,'netPnl':final['cash']-capital,'finalEquity':final['cash'],'maxDrawdown':dd,
           'closedTrades':len(trades),'winRate':100*sum(t['pnl']>0 for t in trades)/len(trades) if trades else 0,'profitFactor':gains/losses if losses else None,
           'liquidations':sum(t['liquidated'] for t in trades),'fees':sum(t['entryFee']+t['exitFee'] for t in trades),'funding':sum(t['funding'] for t in trades)}
    return {'config':cfg,'metrics':stats,'historyGuard':{'passed':False,'reason':'O dopuszczeniu decyduje osobna walidacja i rejestr wersji.'},
            'engineVersion':decision_engine.VERSION,'strategyFingerprint':decision_engine.fingerprint(cfg),
            'startDate':bars[indices[0]]['date'],'endDate':bars[indices[-1]]['date'],'bars':len(indices),'warmupBars':220,
            'equity':curve if ledger else [],'trades':trades if ledger else [],'blockedEntries':blocked[-200:] if ledger else [],'blockedCount':len(blocked),
            'spreadBps':spread*10000,'historicalGuardReplayed':True,'decisionEvents':events,'evidenceEpochs':list(guards.values()),
            'liquidationModel':'isolated_constant_mmr_ohlc_proxy',
            'marketDataMode':'contract_data' if bundle else 'assumptions','marketDataNotice':bundle['notice'] if bundle else 'Modelowe funding i maintenance margin; brak historycznego mark price.',
            'notice':'Pełny replay wywołuje ten sam wykonawca co bot papierowy, z kroczącą oceną wyłącznie wcześniejszych świec. Wypełnienia po kolejnej obserwacji otwarcia są założeniem OHLC; spread, kolejność ruchów, funding i likwidacja nadal mogą być modelowe. Nie odtwarza opóźnień sieci ani rzeczywistych wykonań giełdy. Konto użytkownika nie jest zmieniane.'}


LOOKBACK_PAD=decision_engine.LOOKBACK+decision_engine.REFRESH_BARS+1
