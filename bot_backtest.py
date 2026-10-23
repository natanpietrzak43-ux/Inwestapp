"""Causal OHLC replay of one selected spot/perpetual rule set and risk limits.

Entry decisions use i-1 only and fill at i open. No external code is executed.
This research replay does not replay the live expanding historical entry gate.
"""
from datetime import datetime
from analysis_engine import validate_bars,indicators
from market_data import INSTRUMENTS
from timeframes import TIMEFRAMES,candle_time
from user_data import numeric
import leveraged_trading as model


NOTICE=('Sygnał z poprzedniej zamkniętej świecy, wejście na kolejnym otwarciu. '
        'Uwzględniamy koszty, poślizg, założony spread, limity dnia i obsunięcia oraz wielkość pozycji. '
        'To badawczy replay reguł i ryzyka; nie odtwarza kroczącej blokady historycznej bota ani opóźnień sieciowych. '
        'Futures: ilość w jednostkach bazowych, liniowy depozyt izolowany; stały funding / 8h i maintenance margin są założeniami. '
        'Historyczne OHLC kontraktu zastępują mark price wyłącznie do modelu likwidacji; nie pobieramy historycznych mark price ani funding. '
        'Przy nieznanej kolejności wewnątrz świecy wybieramy likwidację przed stopem, stop przed celem. '
        'Funding rozliczamy za przekroczone granice UTC 00/08/16 po cenie najbliższego przetwarzanego otwarcia. '
        'Ostatnią pozycję zamykamy na końcu testu. Wynik nie jest prognozą ani odtworzeniem rozliczeń OKX.')


def run(rows,cfg,start_date=None,end_date=None,spread_bps=10,ledger=True):
    tf=cfg['timeframe'];bars=validate_bars(rows,tf);inds=indicators(bars)
    spread=numeric(spread_bps,0,200)/10000;slip=cfg['slippage']/10000
    def bound(value):
        if not value:return None
        try:return datetime.strptime(value,'%Y-%m-%d').date()
        except (ValueError,TypeError):raise ValueError('Daty testu: RRRR-MM-DD (UTC).') from None
    start,end=bound(start_date),bound(end_date)
    if start and end and start>end:raise ValueError('Początek testu nie może wypadać po końcu.')
    stamps=[candle_time(b['date'],tf) for b in bars]
    indices=[i for i in range(200,len(bars)) if (start is None or stamps[i].date()>=start) and (end is None or stamps[i].date()<=end)]
    if not indices:raise ValueError('Brak świec w wybranym okresie po 200 świecach rozgrzewki.')
    cash=cfg['capital'];p=None;trades=[];curve=[];blocked=[];peak=cash;day=None;day_equity=cash;daily_halted=False;drawdown_halted=False;max_dd=0
    def exit_fill(value,side):return value*(1-side*spread/2)*(1-side*slip)
    def close(value,bar,reason,liquidation=False):
        nonlocal cash,p
        fill=exit_fill(value,p['side']);result=model.settlement(p,fill,cfg,liquidation)
        cash+=result['credit']
        trades.append({**p,**result,'entryDate':p['entry_at'],'exitDate':bar['date'],'exit':fill,'reason':reason})
        p=None
    def mark_value(value):
        return cash+model.settlement(p,exit_fill(value,p['side']),cfg)['credit'] if p else cash
    def limits(value,bar,current_day):
        nonlocal day,day_equity,daily_halted,drawdown_halted,peak,max_dd
        equity=mark_value(value)
        if day!=current_day:day=current_day;day_equity=equity;daily_halted=False
        peak=max(peak,equity);dd=(peak-equity)/peak*100;max_dd=max(max_dd,dd)
        if dd>=cfg['max_drawdown']:drawdown_halted=True
        if equity<=day_equity*(1-cfg['daily_loss']/100):daily_halted=True
        if p and (daily_halted or drawdown_halted):close(value,bar,'Limit obsunięcia' if drawdown_halted else 'Limit straty dnia UTC')
    for i in indices:
        bar=bars[i];stamp=stamps[i].timestamp();current_day=stamps[i].date().isoformat();exited=False
        if p:
            model.funding(p,bar['open'],stamp,cfg)
            if model.liquidated(p,bar['open'],cfg):close(bar['open'],bar,'Likwidacja — luka',True);exited=True
            elif p['side']*(bar['open']-p['stop'])<=0:close(bar['open'],bar,'Stop — luka');exited=True
            elif p['side']*(bar['open']-p['target'])>=0:close(p['target'],bar,'Take profit na otwarciu');exited=True
        had_position=p is not None;limits(bar['open'],bar,current_day);exited=exited or (had_position and p is None)
        d=model.signal(bars[i-1],inds[i-1],cfg);action=d['action']
        if p and ((action=='SHORT' and p['side']==1) or (action=='LONG' and p['side']==-1) or action=='CLOSE'):
            close(bar['open'],bar,'Przeciwny sygnał / wyjście');exited=True
        if not p and not exited and action in ('LONG','SHORT'):
            side=1 if action=='LONG' else -1;reason=None
            if daily_halted or drawdown_halted:reason='Limit straty dnia lub obsunięcia.'
            elif cfg['direction'] not in ('both','long' if side==1 else 'short'):reason='Wyłączony kierunek.'
            elif spread*10000>cfg['max_spread']:reason='Założony spread przekracza limit.'
            elif INSTRUMENTS[cfg['instrument']]['kind']=='crypto' and (stamps[i]-stamps[i-1]).total_seconds()!=TIMEFRAMES[tf]['seconds']:reason='Luka w historii krypto.'
            elif abs(bar['open']/bars[i-1]['close']-1)*100>cfg['max_deviation']:reason='Otwarcie za daleko od świecy sygnału.'
            if reason is None:
                entry=bar['open']*(1+side*spread/2)*(1+side*slip)
                p=model.plan(cfg,cash,cash,entry,inds[i-1]['atr'],side,stamp)
                if p:
                    p.update(entry_at=bar['date'],signalCandle=bars[i-1]['date']);cash-=p['margin']+p['entryFee']
                else:reason='Niewystarczający depozyt lub stop za likwidacją.'
            if reason:blocked.append({'date':bar['date'],'reason':reason})
        if p:
            adverse=bar['low'] if p['side']==1 else bar['high'];favorable=bar['high'] if p['side']==1 else bar['low']
            if model.liquidated(p,adverse,cfg):close(p['liquidationPrice'],bar,'Likwidacja modelowa wewnątrz świecy',True)
            elif p['side']*(adverse-p['stop'])<=0:close(p['stop'],bar,'Stop loss')
            elif p['side']*(favorable-p['target'])>=0:close(p['target'],bar,'Take profit')
        limits(bar['close'],bar,current_day)
        if i==indices[-1] and p:close(bar['close'],bar,'Koniec testu')
        equity=mark_value(bar['close']);peak=max(peak,equity);max_dd=max(max_dd,(peak-equity)/peak*100)
        curve.append({'date':bar['date'],'value':equity})
    gains=sum(t['pnl'] for t in trades if t['pnl']>0);losses=-sum(t['pnl'] for t in trades if t['pnl']<0)
    cutoff=bars[indices[int(len(indices)*.7)]]['date'];holdout=[t for t in trades if t['entryDate']>=cutoff]
    stats={'returnPct':(cash/cfg['capital']-1)*100,'netPnl':cash-cfg['capital'],'finalEquity':cash,'maxDrawdown':max_dd,
           'closedTrades':len(trades),'winRate':sum(t['pnl']>0 for t in trades)/len(trades)*100 if trades else 0,
           'profitFactor':gains/losses if losses else None,'liquidations':sum(t['liquidated'] for t in trades),
           'fees':sum(t['entryFee']+t['exitFee'] for t in trades),'funding':sum(t['funding'] for t in trades),
           'holdoutTrades':len(holdout),'holdoutPnl':sum(t['pnl'] for t in holdout)}
    guard=stats['closedTrades']>=30 and stats['netPnl']>0 and stats['profitFactor'] is not None and stats['profitFactor']>1 and stats['holdoutTrades']>=5 and stats['holdoutPnl']>0
    return {'config':cfg,'metrics':stats,'historyGuard':{'passed':guard},'startDate':bars[indices[0]]['date'],'endDate':bars[indices[-1]]['date'],
            'bars':len(indices),'warmupBars':200,'equity':curve if ledger else [],'trades':trades if ledger else [],
            'blockedEntries':blocked[-200:] if ledger else [],'blockedCount':len(blocked),'spreadBps':spread*10000,
            'historicalGuardReplayed':False,'liquidationModel':'isolated_constant_mmr_ohlc_proxy','notice':NOTICE}
