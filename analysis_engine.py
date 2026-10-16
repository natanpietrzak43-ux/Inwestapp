"""Closed OHLCV analysis and conservative, next-open long-only simulation."""
import math
from custom_indicators import mercado_indicators, bxtrender_indicators
from datetime import datetime, timezone
from timeframes import candle_time, candle_closed
from technical_tools import extra_indicators, combined_decision, selection


def validate_bars(rows, timeframe='1d'):
    if not isinstance(rows, list) or not 220 <= len(rows) <= 25000:
        raise ValueError('Potrzeba od 220 do 25000 zakończonych świec.')
    result = []
    previous = None
    for row in rows:
        date = str(row['date'])
        when=candle_time(date,timeframe)
        if (previous is not None and when<=previous) or not candle_closed(date,timeframe):
            raise ValueError('Daty muszą być rosnące, bez duplikatów i otwartych lub przyszłych świec.')
        bar = {'date': when.isoformat() if timeframe!='1d' else when.strftime('%Y-%m-%d')}
        for key in ('open', 'high', 'low', 'close', 'volume'):
            bar[key] = float(row.get(key, 0))
            if not math.isfinite(bar[key]) or bar[key] < 0 or (key=='volume' and bar[key]>1e18):
                raise ValueError('Dane OHLCV muszą być skończonymi, nieujemnymi liczbami.')
        if any(not 1e-9<=bar[k]<=1e12 for k in ('open','high','low','close')):
            raise ValueError('Ceny muszą być dodatnie i w zakresie 0,000000001–1 bilion, aby zapewnić stabilne obliczenia.')
        if bar['low'] > min(bar['open'], bar['close']) or bar['high'] < max(bar['open'], bar['close']) or bar['low'] > bar['high']:
            raise ValueError('Nieprawidłowy zakres high/low świecy.')
        result.append(bar)
        previous = when
    return result


def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    out[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        out[i] = values[i] * (2 / (period + 1)) + out[i - 1] * (1 - 2 / (period + 1))
    return out


def wilder(values, period, start):
    out = [None] * len(values)
    if len(values) < start + period:
        return out
    end = start + period - 1
    out[end] = sum(values[start:end + 1]) / period
    for i in range(end + 1, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def indicators(bars):
    close = [b['close'] for b in bars]
    e20, e50, e200, e12, e26 = [ema(close, p) for p in (20, 50, 200, 12, 26)]
    macd = [e12[i] - e26[i] if e26[i] is not None else None for i in range(len(bars))]
    signal = [None] * 25 + ema(macd[25:], 9)
    gain, loss, tr, plus, minus = [[0.0] * len(bars) for _ in range(5)]
    tr[0] = bars[0]['high'] - bars[0]['low']
    for i in range(1, len(bars)):
        change = close[i] - close[i - 1]
        gain[i], loss[i] = max(change, 0), max(-change, 0)
        tr[i] = max(bars[i]['high'] - bars[i]['low'], abs(bars[i]['high'] - close[i-1]), abs(bars[i]['low'] - close[i-1]))
        up, down = bars[i]['high'] - bars[i-1]['high'], bars[i-1]['low'] - bars[i]['low']
        plus[i] = up if up > down and up > 0 else 0
        minus[i] = down if down > up and down > 0 else 0
    avg_gain, avg_loss, atr, pdm, mdm = [wilder(v, 14, 1) for v in (gain, loss, tr, plus, minus)]
    dx = [0.0] * len(bars)
    for i in range(14, len(bars)):
        total = pdm[i] + mdm[i]
        dx[i] = 100 * abs(pdm[i] - mdm[i]) / total if total else 0
    adx = wilder(dx, 14, 14)
    result = []
    for i, bar in enumerate(bars):
        rsi = None
        if avg_loss[i] is not None:
            rsi = 100 - 100 / (1 + avg_gain[i] / avg_loss[i]) if avg_loss[i] else (100 if avg_gain[i] else 50)
        hist = macd[i] - signal[i] if signal[i] is not None else None
        volume_avg = sum(b['volume'] for b in bars[i-20:i]) / 20 if i >= 20 else 0
        result.append({'ema20': e20[i], 'ema50': e50[i], 'ema200': e200[i], 'sma200': sum(close[i-199:i+1]) / 200 if i >= 199 else None,
                       'rsi': rsi, 'macd': macd[i], 'macdSignal': signal[i], 'macdHist': hist, 'atr': atr[i], 'adx': adx[i],
                       'volumeRatio': bar['volume'] / volume_avg if volume_avg > 0 else None,
                       'support': min(b['low'] for b in bars[max(0,i-20):i]) if i else None,
                       'resistance': max(b['high'] for b in bars[max(0,i-20):i]) if i else None})
    extra=extra_indicators(bars,ema,wilder)
    mercado=mercado_indicators(close)
    bx=bxtrender_indicators(close)
    return [{**ind,**additional,**new,**osc} for ind,additional,new,osc in zip(result,extra,mercado,bx)]


def decision(bar, ind, tools=None, strategy='trend'):
    return combined_decision(bar,ind,tools,strategy)


def parameters(capital=10000, risk=1, costs=10):
    capital, risk, costs = float(capital), float(risk), float(costs)
    if not all(math.isfinite(v) for v in (capital, risk, costs)) or not 100 <= capital <= 1e9 or not .1 <= risk <= 3 or not 0 <= costs <= 200:
        raise ValueError('Kapitał: 100–1 mld USD, ryzyko: 0,1–3%, koszt: 0–200 pb na stronę.')
    return capital, risk, costs


def risk_plan(bar, ind, capital, risk, costs):
    distance = 2 * ind['atr']
    entry = bar['close']
    stop = entry - distance
    units = min(capital / (entry * (1 + costs / 10000)), capital * risk / 100 / (distance + entry * 2 * costs / 10000)) if distance > 0 and stop > 0 else 0
    return {'entry': entry, 'stop': stop, 'target': entry + 1.5 * distance, 'units': units,
            'notional': units * entry, 'riskBudget': capital * risk / 100, 'rewardRisk': 1.5}


def backtest(bars, inds, capital=10000, risk=1, costs=10, tools=None, strategy='trend'):
    cash, fee, position = capital, costs / 10000, None
    trades, equity = [], []
    first = 200
    benchmark_units = capital / (bars[first]['open'] * (1 + fee))
    for i in range(first, len(bars)):
        bar = bars[i]
        prior = decision(bars[i-1], inds[i-1], tools, strategy)
        exit_price, reason = None, None
        if position:
            if bar['open'] <= position['stop']:
                exit_price, reason = bar['open'], 'Luka poniżej stop'
            elif bar['open'] >= position['target']:
                exit_price, reason = position['target'], 'Take profit'
            elif prior['action'] == 'SELL':
                exit_price, reason = bar['open'], 'Sygnał wyjścia'
        elif prior['action'] == 'BUY':
            plan = risk_plan({'close': bar['open']}, inds[i-1], cash, risk, costs)
            if plan['units'] > 0:
                position = {**plan, 'date': bar['date'], 'entryFee': plan['notional'] * fee}
                cash -= plan['notional'] * (1 + fee)
        # Daily OHLC cannot establish intrabar order: stop first if both are hit.
        if position and exit_price is None:
            if bar['low'] <= position['stop']:
                exit_price, reason = position['stop'], 'Stop loss'
            elif bar['high'] >= position['target']:
                exit_price, reason = position['target'], 'Take profit'
        if position and exit_price is not None:
            proceeds = position['units'] * exit_price * (1 - fee)
            pnl = proceeds - position['notional'] - position['entryFee']
            cash += proceeds
            trades.append({'entryDate': position['date'], 'exitDate': bar['date'], 'entry': position['entry'], 'exit': exit_price,
                           'units': position['units'], 'pnl': pnl, 'reason': reason})
            position = None
        value = cash + (position['units'] * bar['close'] * (1 - fee) if position else 0)
        equity.append({'date': bar['date'], 'value': value, 'benchmark': benchmark_units * bar['close'] * (1 - fee)})
    peak, drawdown = capital, 0
    for row in equity:
        peak = max(peak, row['value'])
        drawdown = max(drawdown, (peak-row['value']) / peak * 100)
    gains = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    losses = -sum(t['pnl'] for t in trades if t['pnl'] < 0)
    split_date = equity[int(len(equity) * .7)]['date']
    holdout = [t for t in trades if t['entryDate'] >= split_date]
    return {'equity': equity, 'trades': trades, 'returnPct': (equity[-1]['value']/capital-1)*100,
            'benchmarkPct': (equity[-1]['benchmark']/capital-1)*100, 'maxDrawdown': drawdown,
            'winRate': sum(t['pnl'] > 0 for t in trades)/len(trades)*100 if trades else None,
            'profitFactor': gains/losses if losses else None, 'openPosition': position,
            'holdoutDate': split_date, 'holdoutTrades': len(holdout), 'holdoutPnl': sum(t['pnl'] for t in holdout),
            'sampleWarning': len(trades) < 30, 'startDate': bars[first]['date'], 'endDate': bars[-1]['date'], 'coreRulesOnly':True}


def history_guard(stats):
    reasons=[]
    if len(stats['trades'])<30:reasons.append('mniej niż 30 zamkniętych transakcji')
    if stats['returnPct']<=0:reasons.append('wynik całego testu po kosztach nie jest dodatni')
    if stats['profitFactor'] is None or stats['profitFactor']<=1:reasons.append('profit factor nie przekracza 1')
    if stats['holdoutTrades']<5 or stats['holdoutPnl']<=0:reasons.append('końcowe 30% ma mniej niż 5 transakcji lub niedodatni wynik')
    return {'passed':not reasons,'reasons':reasons,'description':'Heurystyczna blokada nowych wejść, bez gwarancji skuteczności. Test przedstawia rdzeń reguł; nie symuluje tej bramki w przeszłości.'}


def analyze(bars, capital=10000, risk=1, costs=10, timeframe='1d', tools=None, strategy='trend'):
    bars = validate_bars(bars,timeframe)
    tools=selection(tools,strategy)
    capital, risk, costs = parameters(capital, risk, costs)
    inds = indicators(bars)
    stats=backtest(bars,inds,capital,risk,costs,tools,strategy)
    current=decision(bars[-1],inds[-1],tools,strategy)
    guard=history_guard(stats)
    current['technicalAction']=current['action']
    if current['action']=='BUY' and not guard['passed']:
        current={**current,'action':'WAIT','reason':'Układ techniczny kupna jest spełniony, ale test blokuje nowe wejście: '+ '; '.join(guard['reasons'])+'.'}
    return {'bars': bars, 'indicators': inds, 'decision': current,'historyGuard':guard,
            'selectedTools':tools,'strategy':strategy,'timeframe':timeframe,
            'plan': risk_plan(bars[-1], inds[-1], capital, risk, costs), 'backtest': stats}
