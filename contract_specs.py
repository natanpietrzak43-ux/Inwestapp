"""Validated linear OKX contracts and decimal order rounding."""
from decimal import Decimal,InvalidOperation,ROUND_FLOOR,ROUND_CEILING
import hashlib
import json
import time
import okx_data


def decimal(value,positive=True):
    try:
        if isinstance(value,bool):raise ValueError()
        result=Decimal(str(value))
        if not result.is_finite() or (result<=0 if positive else result<0):raise ValueError()
        return result
    except (InvalidOperation,ValueError,TypeError):raise ValueError('Nieprawidłowa specyfikacja kontraktu.') from None


def text(value):return format(value,'f')


def parse(row,key,tiers):
    inst=okx_data.symbol(key,'perpetual')
    if row.get('instId')!=inst or row.get('ctType')!='linear' or row.get('ctValCcy')!=key or row.get('settleCcy')!='USDT' or row.get('state')!='live':
        raise ValueError('Kontrakt nie jest aktywnym liniowym swapem USDT wybranego instrumentu.')
    result={'instId':inst,'unitsPerContract':text(decimal(row['ctVal'])*decimal(row.get('ctMult') or 1)),
            'lotSz':text(decimal(row['lotSz'])),'minSz':text(decimal(row['minSz'])),'tickSz':text(decimal(row['tickSz'])),
            'maxMktSz':text(decimal(row['maxMktSz'])),'maxLeverage':text(decimal(row['lever'])),'tiers':[],
            'fetchedAt':time.time()}
    for t in tiers:
        if t.get('instFamily') not in (None,'',key+'-USDT'):raise ValueError('Nieprawidłowa rodzina progów depozytu.')
        result['tiers'].append({'minSz':text(decimal(t['minSz'],False)),'maxSz':text(decimal(t['maxSz'])),
                                'mmr':text(decimal(t['mmr'])),'maxLever':text(decimal(t['maxLever']))})
    if not result['tiers']:raise ValueError('Brak progów depozytu kontraktu; wejścia wstrzymane.')
    result['hash']=hashlib.sha256(json.dumps({k:v for k,v in result.items() if k!='fetchedAt'},sort_keys=True).encode()).hexdigest()
    return result


def fetch(key,request=okx_data.request):
    rows=request('/api/v5/public/instruments',{'instType':'SWAP','instId':okx_data.symbol(key,'perpetual')})
    tiers=request('/api/v5/public/position-tiers',{'instType':'SWAP','tdMode':'isolated','instFamily':key+'-USDT'})
    if len(rows)!=1:raise ValueError('Brak jednoznacznej specyfikacji kontraktu.')
    return parse(rows[0],key,tiers)


def round_plan(plan,cfg,spec):
    if spec['instId']!=okx_data.symbol(cfg['instrument'],'perpetual'):raise ValueError('Specyfikacja innego kontraktu.')
    if not 0<=time.time()-spec['fetchedAt']<=3600:raise ValueError('Specyfikacja kontraktu wygasła.')
    unit=decimal(spec['unitsPerContract']);lot=decimal(spec['lotSz']);tick=decimal(spec['tickSz'])
    entry=decimal(plan['entry']);side=plan['side'];fee=decimal(cfg['costs'] or '0',False)/10000;slip=decimal(cfg['slippage'] or '0',False)/10000
    stop=(decimal(plan['stop'])/tick).to_integral_value(rounding=ROUND_FLOOR if side==1 else ROUND_CEILING)*tick
    target=(decimal(plan['target'])/tick).to_integral_value(rounding=ROUND_FLOOR if side==1 else ROUND_CEILING)*tick
    risk_per_unit=Decimal(side)*(entry-stop*(1-Decimal(side)*slip))+(entry+stop*(1-Decimal(side)*slip))*fee
    if risk_per_unit<=0:raise ValueError('Nieprawidłowe ryzyko po zaokrągleniu ceny.')
    max_units=min(decimal(plan['units']),decimal(plan['riskBudget'])/risk_per_unit)
    contracts=(min(max_units/unit,decimal(spec['maxMktSz']))/lot).to_integral_value(rounding=ROUND_FLOOR)*lot
    if contracts<decimal(spec['minSz']):raise ValueError('Pozycja poniżej minimalnej liczby kontraktów.')
    tier=next((t for t in spec['tiers'] if decimal(t['minSz'],False)<=contracts<=decimal(t['maxSz'])),None)
    if not tier or decimal(cfg['leverage'])>min(decimal(tier['maxLever']),decimal(spec['maxLeverage'])):raise ValueError('Brak zgodnego progu depozytu lub za duża dźwignia.')
    units=contracts*unit;reserve=decimal(tier['mmr'])+fee
    liq=(entry-Decimal(side)*entry/decimal(cfg['leverage']))/(1-Decimal(side)*reserve)
    if Decimal(side)*(stop*(1-Decimal(side)*slip)-liq)<=0:raise ValueError('Stop za poziomem likwidacji dla rzeczywistego progu depozytu.')
    return {**plan,'units':float(units),'contracts':text(contracts),'stop':float(stop),'target':float(target),
            'slTriggerPx':text(stop),'tpTriggerPx':text(target),'notional':float(units*entry),
            'margin':float(units*entry/decimal(cfg['leverage'])),'entryFee':float(units*entry*fee),
            'estimatedStopLoss':float(units*risk_per_unit),'maintenanceMargin':float(decimal(tier['mmr'])),
            'liquidationPrice':float(liq),'specHash':spec['hash']}


def funding_history(key,begin_ms,end_ms):
    """Return actual known settlements only; fail on incomplete interval coverage."""
    result=[];cursor=None;oldest=None;latest=None
    for _ in range(100):
        params={'instId':okx_data.symbol(key,'perpetual'),'limit':'100'}
        if cursor is not None:params['after']=str(cursor)
        rows=okx_data.request('/api/v5/public/funding-rate-history',params)
        if not rows:break
        if latest is None:latest=max(int(r['fundingTime']) for r in rows)
        oldest=min(int(r['fundingTime']) for r in rows)
        if cursor is not None and oldest>=cursor:raise ValueError('Paginacja fundingu nie przesuwa się.')
        for r in rows:
            stamp=int(r['fundingTime'])
            if begin_ms<=stamp<=end_ms:
                rate=Decimal(str(r.get('realizedRate') or r['fundingRate']))
                if not rate.is_finite() or abs(rate)>1:raise ValueError('Nieprawidłowa stawka fundingu.')
                result.append({'timestamp':stamp/1000,'rate':float(rate)})
        if oldest<=begin_ms:break
        cursor=oldest;time.sleep(.22)
    if oldest is None or oldest>begin_ms or latest<end_ms-8*3600*1000:raise ValueError('Brak pełnego pokrycia fundingu w wybranym okresie; nie podstawiono stałej stawki.')
    return sorted({r['timestamp']:r for r in result}.values(),key=lambda r:r['timestamp'])
