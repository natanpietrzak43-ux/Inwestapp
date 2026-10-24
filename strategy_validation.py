"""Fixed forward windows and explicit stress scenarios. No winner selection."""
import hashlib
import json
import bot_backtest
import decision_engine
from analysis_engine import validate_bars


def validate(rows,cfg,bundle=None):
    bars=validate_bars(rows,cfg['timeframe'])
    if len(bars)<1000:raise ValueError('Walidacja wymaga minimum 1000 świec i trzech późniejszych okien testowych.')
    first=max(400,len(bars)//2);width=(len(bars)-first)//3;reports=[]
    for fold in range(3):
        start=first+fold*width;end=first+(fold+1)*width if fold<2 else len(bars)
        # Keep the complete earlier history for causal gates, independent account
        # per fold. Date filtering alone cannot select sub-day fold boundaries.
        from shared_replay import run
        report=run(bars[:end],cfg,start_date=None,end_date=None,spread_bps=10,ledger=True,start_index=start,bundle=bundle)
        reports.append({'fold':fold+1,'start':bars[start]['date'],'end':bars[end-1]['date'],'metrics':report['metrics']})
    stressed={**cfg,'costs':min(200,cfg['costs']*1.5),'slippage':min(100,max(1,cfg['slippage']*2))}
    stress=bot_backtest.run(bars,stressed,spread_bps=20,ledger=False,market_bundle=bundle)
    reasons=[]
    if cfg['market']=='perpetual' and bundle is None:reasons.append('Dopuszczenie futures wymaga rzeczywistych danych kontraktowych, mark price i fundingu.')
    for r in reports:
        m=r['metrics']
        if m['closedTrades']<10:reasons.append(f"Okno {r['fold']}: mniej niż 10 zamkniętych transakcji.")
        if m['netPnl']<=0 or m['profitFactor'] is None or m['profitFactor']<=1:reasons.append(f"Okno {r['fold']}: brak dodatniego wyniku i PF>1.")
        if m['maxDrawdown']>cfg['max_drawdown'] or m['liquidations']:reasons.append(f"Okno {r['fold']}: naruszenie limitu obsunięcia lub likwidacja.")
    if stress['metrics']['netPnl']<=0 or stress['metrics']['liquidations']:reasons.append('Scenariusz zwiększonych kosztów nie przeszedł filtra.')
    return {'fingerprint':decision_engine.fingerprint(cfg),'config':cfg,'eligible':not reasons,'reasons':reasons,'reports':reports,'stress':stress['metrics'],
            'marketDataMode':'contract_data' if bundle else 'assumptions','dataHash':hashlib.sha256(json.dumps(bars,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'notice':'Trzy niezależne portfele w kolejnych oknach, wyłącznie wcześniejsze dane dla filtrów. Brak doboru zwycięzcy. Progi badawcze nie dowodzą przyszłej przewagi; wielokrotne wybieranie modeli po wynikach ogranicza niezależność testu.'}
