"""Causal indicator calculations; displaced lines use only already known prices."""
import math

TOOLS = {
    'ema': {'name': 'EMA 20 / 50 / 200', 'group': 'trend', 'overlay': True, 'lookback': 200, 'description': 'Kierunek trendu; okresy liczone w świecach wybranego interwału.'},
    'ichimoku': {'name': 'Chmura Ichimoku', 'group': 'trend', 'overlay': True, 'lookback': 78, 'description': '9 / 26 / 52, chmura przesunięta o 26 świec; cena i Tenkan/Kijun.'},
    'alligator': {'name': 'Aligator', 'group': 'trend', 'overlay': True, 'lookback': 21, 'description': 'SMMA mediany ceny: 13/8/5, przesunięcia 8/5/3.'},
    'sar': {'name': 'Parabolic SAR', 'group': 'trend', 'overlay': True, 'lookback': 3, 'description': 'Kierunek trendu; przyspieszenie 0,02 do 0,20. Nie zastępuje stopa ATR.'},
    'rsi': {'name': 'RSI 14', 'group': 'momentum', 'overlay': False, 'lookback': 15, 'description': 'Momentum i strefy 30/70; obliczenie Wildera z poprzedniej wersji.'},
    'stochastic': {'name': 'Stochastic 14 / 3 / 3', 'group': 'momentum', 'overlay': False, 'lookback': 18, 'description': 'Wygładzony %K i %D; relacja ceny do zakresu 14 świec.'},
    'momentum': {'name': 'Momentum 10', 'group': 'momentum', 'overlay': False, 'lookback': 11, 'description': '100 × cena / cena sprzed 10 świec; poziom równowagi 100.'},
    'macd': {'name': 'MACD 12 / 26 / 9', 'group': 'momentum', 'overlay': False, 'lookback': 34, 'description': 'EMA i histogram; należy do tej samej grupy co inne oscylatory.'},
    'obv': {'name': 'OBV — równowaga wolumenu', 'group': 'volume', 'overlay': False, 'lookback': 25, 'description': 'Skumulowany wolumen; porównanie z EMA20 i poziomem sprzed 5 świec.'},
    'adx': {'name': 'ADX 14', 'group': 'regime', 'overlay': False, 'lookback': 28, 'description': 'ADX ≥ 20: filtr trendu; ADX < 20: filtr konsolidacji. Nie określa kierunku.'},
    'bollinger': {'name': 'Wstęgi Bollingera 20 / 2', 'group': 'context', 'overlay': True, 'lookback': 20, 'description': 'SMA20 ± 2 odchylenia standardowe; dotknięcie wstęgi samo nie jest sygnałem.'},
    'fibonacci': {'name': 'Korekty Fibonacciego', 'group': 'context', 'overlay': True, 'lookback': 55, 'description': '23,6 / 38,2 / 50 / 61,8 / 78,6% z kierunkowego zakresu ostatnich 55 świec; kontekst, bez głosu.'},
}
PRESETS = {
    'balanced': {'name': 'Trend — zestaw podstawowy', 'strategy': 'trend', 'tools': ['ema','rsi','adx','obv','bollinger']},
    'cloud': {'name': 'Trend — Ichimoku', 'strategy': 'trend', 'tools': ['ichimoku','stochastic','adx','obv','sar']},
    'alligator': {'name': 'Trend — Aligator', 'strategy': 'trend', 'tools': ['alligator','momentum','adx','obv','fibonacci']},
    'range': {'name': 'Konsolidacja — Bollinger', 'strategy': 'range', 'tools': ['bollinger','stochastic','adx','obv']},
}
SOURCES = [
    {'name': 'StockCharts: Ichimoku', 'url': 'https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud'},
    {'name': 'StockCharts: Bollinger', 'url': 'https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands'},
    {'name': 'StockCharts: OBV', 'url': 'https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv'},
    {'name': 'StockCharts: Stochastic', 'url': 'https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full'},
    {'name': 'StockCharts: Parabolic SAR', 'url': 'https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/parabolic-sar'},
    {'name': 'StockCharts: Fibonacci', 'url': 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements'},
    {'name': 'MetaTrader: Aligator', 'url': 'https://www.metatrader5.com/en/terminal/help/indicators/bw_indicators/alligator'},
]


def selection(tools=None, strategy='trend'):
    if strategy not in ('trend', 'range'):
        raise ValueError('Nieprawidłowy tryb strategii.')
    if tools is None:
        tools = PRESETS['balanced' if strategy == 'trend' else 'range']['tools']
    if not isinstance(tools, list) or len(tools) > len(TOOLS) or any(not isinstance(t,str) or t not in TOOLS for t in tools):
        raise ValueError('Nieprawidłowy wybór wskaźników.')
    return list(dict.fromkeys(tools))


def sma(values, period):
    result = [None] * len(values)
    for i in range(period-1,len(values)):
        window = values[i-period+1:i+1]
        if all(v is not None for v in window):
            result[i] = sum(window)/period
    return result


def extra_indicators(bars, ema, wilder):
    close = [b['close'] for b in bars]
    median = [(b['high']+b['low'])/2 for b in bars]
    bb = sma(close,20)
    jaws, teeth, lips = [wilder(median,p,0) for p in (13,8,5)]
    tenkan, kijun, span_a_raw, span_b_raw, stochastic_raw = [[None]*len(bars) for _ in range(5)]
    obv = [0.0]*len(bars)
    sar = [None]*len(bars)
    def midpoint(i,period):
        if i+1<period:return None
        win=bars[i-period+1:i+1]
        return (max(b['high'] for b in win)+min(b['low'] for b in win))/2
    for i,b in enumerate(bars):
        tenkan[i],kijun[i],span_b_raw[i]=[midpoint(i,p) for p in (9,26,52)]
        if kijun[i] is not None:span_a_raw[i]=(tenkan[i]+kijun[i])/2
        if i>=13:
            win=bars[i-13:i+1];high=max(x['high'] for x in win);low=min(x['low'] for x in win)
            stochastic_raw[i]=100*(b['close']-low)/(high-low) if high>low else 50.0
        if i:
            obv[i]=obv[i-1]+(b['volume'] if close[i]>close[i-1] else -b['volume'] if close[i]<close[i-1] else 0)
    k=sma(stochastic_raw,3);d=sma(k,3);obv_ema=ema(obv,20)
    if len(bars)>1:
        up=close[1]>=close[0];acc=.02
        sar[1]=min(b['low'] for b in bars[:2]) if up else max(b['high'] for b in bars[:2])
        extreme=max(b['high'] for b in bars[:2]) if up else min(b['low'] for b in bars[:2])
        for i in range(2,len(bars)):
            value=sar[i-1]+acc*(extreme-sar[i-1])
            if up:
                value=min(value,bars[i-1]['low'],bars[i-2]['low'])
                if bars[i]['low']<value:
                    up=False;value=extreme;extreme=bars[i]['low'];acc=.02
                elif bars[i]['high']>extreme:
                    extreme=bars[i]['high'];acc=min(.2,acc+.02)
            else:
                value=max(value,bars[i-1]['high'],bars[i-2]['high'])
                if bars[i]['high']>value:
                    up=True;value=extreme;extreme=bars[i]['high'];acc=.02
                elif bars[i]['low']<extreme:
                    extreme=bars[i]['low'];acc=min(.2,acc+.02)
            sar[i]=value
    out=[]
    for i,b in enumerate(bars):
        std=math.sqrt(sum((v-bb[i])**2 for v in close[i-19:i+1])/20) if bb[i] is not None else None
        fib=None
        if i>=54:
            win=bars[i-54:i+1];lo=min(range(55),key=lambda j:win[j]['low']);hi=max(range(55),key=lambda j:win[j]['high'])
            low,high=win[lo]['low'],win[hi]['high'];direction='unknown' if lo==hi else 'up' if lo<hi else 'down'
            fib={'low':low,'high':high,'direction':direction,'startDate':win[lo if direction=='up' else hi]['date'],
                 'endDate':win[hi if direction=='up' else lo]['date'],
                 'levels':{str(p):high-(high-low)*p if direction=='up' else low+(high-low)*p for p in (.236,.382,.5,.618,.786)}}
        out.append({'tenkan':tenkan[i],'kijun':kijun[i], 'cloudA':span_a_raw[i-26] if i>=26 else None,
                    'cloudB':span_b_raw[i-26] if i>=26 else None, 'lagReference':close[i-26] if i>=26 else None,
                    'alligatorJaw':jaws[i-8] if i>=8 else None,'alligatorTeeth':teeth[i-5] if i>=5 else None,
                    'alligatorLips':lips[i-3] if i>=3 else None,'sar':sar[i],
                    'bbMid':bb[i],'bbUpper':bb[i]+2*std if std is not None else None,'bbLower':bb[i]-2*std if std is not None else None,
                    'stochK':k[i],'stochD':d[i],'previousStochK':k[i-1] if i else None,
                    'obv':obv[i],'obvEma':obv_ema[i], 'obvPrevious':obv[i-5] if i>=5 else None,
                    'hasVolume':i>=19 and sum(x['volume'] for x in bars[i-19:i+1])>0,
                    'momentum':100*close[i]/close[i-10] if i>=10 else None,'fibonacci':fib})
    return out


def tool_reading(tool, bar, ind, strategy):
    c=bar['close'];value=None;bull=bear=False;available=True
    def ready(*keys):return all(ind.get(key) is not None for key in keys)
    if tool=='ema':
        available=ready('ema20','ema50','ema200');value=ind.get('ema200')
        if available:bull=c>ind['ema200'] and ind['ema20']>ind['ema50'];bear=c<ind['ema200'] and ind['ema20']<ind['ema50']
    elif tool=='ichimoku':
        available=ready('cloudA','cloudB','tenkan','kijun','lagReference');value=ind.get('kijun')
        if available:
            bull=c>max(ind['cloudA'],ind['cloudB']) and ind['tenkan']>ind['kijun'] and c>ind['lagReference']
            bear=c<min(ind['cloudA'],ind['cloudB']) and ind['tenkan']<ind['kijun'] and c<ind['lagReference']
    elif tool=='alligator':
        available=ready('alligatorLips','alligatorTeeth','alligatorJaw');value=ind.get('alligatorJaw')
        if available:bull=ind['alligatorLips']>ind['alligatorTeeth']>ind['alligatorJaw'];bear=ind['alligatorLips']<ind['alligatorTeeth']<ind['alligatorJaw']
    elif tool=='sar':
        available=ready('sar');value=ind.get('sar')
        if available:bull=c>value;bear=c<value
    elif tool=='rsi':
        available=ready('rsi');value=ind.get('rsi')
        if available:bull=(30<=value<=50) if strategy=='range' else 50<=value<=70;bear=value>=60 if strategy=='range' else value<45
    elif tool=='stochastic':
        available=ready('stochK','stochD');value=ind.get('stochK')
        if available:bull=ind['stochK']>ind['stochD'] and (ind['stochK']<=35 if strategy=='range' else 50<=ind['stochK']<=80);bear=ind['stochK']<ind['stochD'] and (ind['stochK']>=65 if strategy=='range' else ind['stochK']<50)
    elif tool=='momentum':
        available=ready('momentum');value=ind.get('momentum')
        if available:bull=value>100;bear=value<100
    elif tool=='macd':
        available=ready('macdHist');value=ind.get('macdHist')
        if available:bull=value>0;bear=value<0
    elif tool=='obv':
        available=ready('obv','obvEma','obvPrevious') and bool(ind.get('hasVolume'));value=ind.get('obv')
        if available:bull=value>ind['obvEma'] and value>ind['obvPrevious'];bear=value<ind['obvEma'] and value<ind['obvPrevious']
    elif tool=='adx':
        available=ready('adx');value=ind.get('adx')
        if available:bull=value<20 if strategy=='range' else value>=20
    elif tool=='bollinger':
        available=ready('bbMid','bbLower','bbUpper');value=ind.get('bbMid')
        if available:bull=bar['low']<=ind['bbLower'] and c>ind['bbLower'] if strategy=='range' else ind['bbMid']<=c<=ind['bbUpper'];bear=c>=ind['bbMid'] if strategy=='range' else c<ind['bbMid']
    elif tool=='fibonacci':
        available=ind.get('fibonacci') is not None
        value=ind['fibonacci']['levels']['0.618'] if available else None
    state='missing' if not available else 'bull' if bull else 'bear' if bear else 'neutral'
    return {'id':tool,'name':TOOLS[tool]['name'],'group':TOOLS[tool]['group'],'state':state,'value':value,'ok':bool(bull),'detail':TOOLS[tool]['description']}


def combined_decision(bar, ind, tools=None, strategy='trend'):
    tools=selection(tools,strategy)
    checks=[tool_reading(t,bar,ind,strategy) for t in tools]
    groups={g:[c for c in checks if c['group']==g] for g in ('trend','momentum','volume','regime','context')}
    missing=[]
    for group,label in (('momentum','momentum'),('volume','wolumen OBV'),('regime','reżim ADX')):
        if not groups[group]:missing.append(label)
    if strategy=='trend' and not groups['trend']:missing.append('trend (EMA, Ichimoku, Aligator lub SAR)')
    if strategy=='range' and 'bollinger' not in tools:missing.append('układ Wstęg Bollingera')
    def aligned(group,state):return bool(groups[group]) and all(c['state']==state for c in groups[group])
    risk_ok=ind.get('atr') is not None and 0<ind['atr']/bar['close']<=.08
    setup_ok=aligned('trend','bull') if strategy=='trend' else next((c['state']=='bull' for c in checks if c['id']=='bollinger'),False)
    context=[c for c in groups['context'] if c['id']!='fibonacci' and not (strategy=='range' and c['id']=='bollinger')]
    context_ok=all(c['state']=='bull' for c in context)
    conditions=[{'name':'Trend / układ ceny','ok':setup_ok,'detail':'Zgodność wybranych narzędzi trendu' if strategy=='trend' else 'Powrót ceny ponad dolną wstęgę'},
                {'name':'Momentum','ok':aligned('momentum','bull'),'detail':'Zgodność wybranych oscylatorów; jedna grupa, jeden warunek'},
                {'name':'Wolumen','ok':aligned('volume','bull'),'detail':'OBV ponad EMA20 oraz ponad poziomem sprzed 5 świec'},
                {'name':'Reżim rynku','ok':aligned('regime','bull'),'detail':'ADX ≥ 20: trend' if strategy=='trend' else 'ADX < 20: konsolidacja'},
                {'name':'Kontekst i ryzyko','ok':risk_ok and context_ok,'detail':'ATR ≤ 8% ceny, dodatni; potwierdzenie wybranej wstęgi. Fibonacci bez głosu'}]
    unavailable=[c['name'] for c in checks if c['state']=='missing']
    action='WAIT'
    if not missing and not unavailable:
        if all(c['ok'] for c in conditions):action='BUY'
        elif strategy=='trend' and aligned('trend','bear') and aligned('momentum','bear'):action='SELL'
        elif strategy=='range' and next((c['state']=='bear' for c in checks if c['id']=='bollinger'),False) and aligned('momentum','bear'):action='SELL'
    reason=('Zestaw niekompletny: dodaj '+', '.join(missing)+'.' if missing else
            'Brak danych dla: '+', '.join(unavailable)+'.' if unavailable else
            {'BUY':'Wybrane grupy są zgodne. Zweryfikuj cenę wykonania i plan ryzyka przed wejściem.',
             'SELL':'Warunki wyjścia z istniejącej pozycji kupna są spełnione. Bez otwierania shorta.',
             'WAIT':'Brak zgodności wszystkich wymaganych grup. Poczekaj na pełny układ.'}[action])
    return {'action':action,'score':sum(c['ok'] for c in conditions),'total':len(conditions),'checks':checks,
            'groups':conditions,'reason':reason,'missingGroups':missing,'unavailableTools':unavailable,'strategy':strategy}
