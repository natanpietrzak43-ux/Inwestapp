# SPDX-License-Identifier: MPL-2.0
# B-Xtrender formulas: © QuantTherapy. Independent Python adaptation, Inwestapp 2026.
# See THIRD_PARTY_NOTICES.md for the pinned source and scope of this adaptation.
"""Independent implementations of published moving-average/oscillator formulas.

The legacy EMA20/50/200 and RSI14 keep their existing seed conventions.
New Pine-style EMA series start at the first non-missing source value.
"""


def ema_first(values,period):
    result=[];previous=None;alpha=2/(period+1)
    for value in values:
        if value is None:result.append(None);continue
        previous=value if previous is None else alpha*value+(1-alpha)*previous
        result.append(previous)
    return result


def mercado_indicators(close):
    m1,m2,m3=[ema_first(close,p) for p in (21,89,200)]
    return [{'emaM1':m1[i],'emaM2':m2[i],'emaM3':m3[i],'emaMercadoReady':i>=199} for i in range(len(close))]


def rsi_wilder(values,period):
    """Wilder RSI on the input series, SMA seed from `period` valid changes.

    Pine-compatible one-sided convention: no losses -> 100 (also flat),
    no gains with losses -> 0. No zero padding before the first valid RSI.
    """
    result=[];previous=None;gains=[];losses=[];up=down=None
    for value in values:
        if value is None:result.append(None);continue
        if previous is None:previous=value;result.append(None);continue
        change=value-previous;previous=value;gain=max(change,0);loss=max(-change,0)
        if up is None:
            gains.append(gain);losses.append(loss)
            if len(gains)<period:result.append(None);continue
            up=sum(gains)/period;down=sum(losses)/period
        else:up=(up*(period-1)+gain)/period;down=(down*(period-1)+loss)/period
        result.append(100.0 if down==0 else 100-100/(1+up/down))
    return result


def tillson_t3(values,period=5,factor=.7):
    layers=[];current=values
    for _ in range(6):current=ema_first(current,period);layers.append(current)
    b=factor;c1=-b**3;c2=3*b*b+3*b**3;c3=-6*b*b-3*b-3*b**3;c4=1+3*b+b**3+3*b*b
    return [c1*e6+c2*e5+c3*e4+c4*e3 if e3 is not None else None
            for e3,e4,e5,e6 in zip(*layers[2:])]


def histogram_color(value,previous):
    if value is None or previous is None:return None
    rising=value>previous
    return ('#00ff00' if rising else '#228b22') if value>0 else ('#ff0000' if rising else '#8b0000')


def bxtrender_indicators(close):
    fast,slow=[ema_first(close,p) for p in (5,20)]
    short=[r-50 if r is not None else None for r in rsi_wilder([f-s for f,s in zip(fast,slow)],15)]
    long=[r-50 if r is not None else None for r in rsi_wilder(slow,15)]
    smooth=tillson_t3(short)
    result=[]
    for i in range(len(close)):
        ready=i>=2 and all(v is not None for v in smooth[i-2:i+1])
        # Mark the confirmation candle. Never move a newly discovered pivot back in time.
        turn_up=bool(ready and smooth[i]>smooth[i-1] and smooth[i-1]<smooth[i-2])
        turn_down=bool(ready and smooth[i]<smooth[i-1] and smooth[i-1]>smooth[i-2])
        result.append({'bxShort':short[i],'bxLong':long[i],'bxT3':smooth[i],
                       'bxShortColor':histogram_color(short[i],short[i-1]) if i else None,
                       'bxLongColor':histogram_color(long[i],long[i-1]) if i else None,
                       'bxLongRising':long[i]>long[i-1] if i and long[i] is not None and long[i-1] is not None else None,
                       'bxTurnUp':turn_up,'bxTurnDown':turn_down})
    return result
