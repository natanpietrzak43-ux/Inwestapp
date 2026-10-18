"""Fixed rule sets, chronological split, no automatic parameter optimization."""
from analysis_engine import validate_bars,indicators,backtest,parameters
from technical_tools import PRESETS


def metrics(stats,capital):
    return {**{k:stats[k] for k in ('returnPct','benchmarkPct','maxDrawdown','winRate','profitFactor','startDate','endDate')},
            'trades':len(stats['trades']),'netPnl':capital*stats['returnPct']/100,
            'openPosition':stats['openPosition'] is not None,'coreRulesOnly':True}


def compare(rows,timeframe='1h',capital=10000,risk=1,costs=10,slippage=0):
    bars=validate_bars(rows,timeframe);capital,risk,costs=parameters(capital,risk,costs)
    if len(bars)<400:raise ValueError('Laboratorium wymaga co najmniej 400 świec: 200 rozgrzewki i co najmniej 60 końcowego testu.')
    inds=indicators(bars);split=200+int((len(bars)-200)*.7);results=[]
    for key,preset in PRESETS.items():
        train=backtest(bars[:split],inds[:split],capital,risk,costs,preset['tools'],preset['strategy'],slippage=slippage)
        test=backtest(bars,inds,capital,risk,costs,preset['tools'],preset['strategy'],start_index=split,slippage=slippage)
        reasons=[]
        if len(train['trades'])<30:reasons.append('Okres początkowy: mniej niż 30 zamkniętych transakcji.')
        if len(test['trades'])<10:reasons.append('Okres końcowy: mniej niż 10 zamkniętych transakcji.')
        if train['returnPct']<=0 or test['returnPct']<=0:reasons.append('Nie oba okresy mają dodatni wynik po kosztach.')
        if any(s['profitFactor'] is None or s['profitFactor']<=1 for s in (train,test)):reasons.append('Nie oba okresy mają określony profit factor > 1.')
        results.append({'id':key,'name':preset['name'],'tools':preset['tools'],'strategy':preset['strategy'],'initial':metrics(train,capital),'test':metrics(test,capital),
                        'researchFilterPassed':not reasons,'reasons':reasons})
    return {'rows':results,'timeframe':timeframe,'bars':len(bars),'splitDate':bars[split]['date'],'initialBars':split-200,'testBars':len(bars)-split,
            'capital':capital,'risk':risk,'costs':costs,'slippage':slippage,'sourceCodeParityVerified':False,
            'notice':'Testujemy pięć stałych lokalnych zestawów. Pierwsze 200 świec to rozgrzewka, kolejne 70% okres początkowy, końcowe 30% osobny portfel testowy bez przeniesienia pozycji. Odczyt przed pierwszym otwarciem testu może użyć ostatniej świecy okresu początkowego. Nie dobieramy parametrów. Powtórne wybieranie zestawu po obejrzeniu wyniku końcowego odbiera mu niezależność. Test nie stosuje historycznie blokady BUY, nie dowodzi zyskowności i nie potwierdza zgodności z pobranym kodem Pine/MCP. Wykonanie testu: kolejne otwarcie świecy; bot papierowy: pierwsza świeża cena zaobserwowana po decyzji.'}
