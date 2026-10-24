"""Actual mark OHLC/funding plus current validated contract specifications."""
from datetime import datetime,timezone
import time
import contract_specs
import okx_data
from timeframes import TIMEFRAMES,candle_time


def mark_history(key,tf,begin,end,open_only=False):
    cursor=None;result={};step=TIMEFRAMES[tf]['seconds']
    for _ in range(80):
        params={'instId':okx_data.symbol(key,'perpetual'),'bar':okx_data.BARS[tf],'limit':'100'}
        if cursor is not None:params['after']=str(cursor)
        rows=okx_data.request('/api/v5/market/history-mark-price-candles',params)
        if not rows:break
        oldest=min(int(r[0]) for r in rows)
        if cursor is not None and oldest>=cursor:raise ValueError('Paginacja mark price nie przesuwa się.')
        for r in rows:
            if not isinstance(r,list) or len(r)<6:raise ValueError('Nieprawidłowa historia mark price.')
            if r[5]=='0' and open_only and float(r[0])/1000<=time.time():
                # Funding valuation only: the opening observation is already
                # known. Never turn an open candle into fabricated closed OHLC.
                stamp=okx_data.number(r[0])/1000
                if stamp%step:raise ValueError('Otwarcie mark price poza granicą godziny.')
                row={'date':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),'open':okx_data.number(r[1]),'openOnly':True}
            else:row=okx_data._decode([*r[:5],'0','0','0',r[5]],tf,time.time())
            if row:
                stamp=candle_time(row['date'],tf).timestamp()
                if begin<=stamp<=end:result[stamp]=row
        if oldest/1000<=begin:break
        cursor=oldest;time.sleep(.22)
    if not result or any(t not in result for t in range(int(begin),int(end)+1,step)):
        raise ValueError('Brak pełnej historii mark price w wybranym okresie. Nie podstawiono cen transakcyjnych.')
    return result


def fetch(rows,cfg,start_date=None,end_date=None):
    if cfg['market']!='perpetual' or cfg['source']!='okx':raise ValueError('Dane kontraktowe wymagają OKX perpetual.')
    if len(rows)<221:raise ValueError('Za krótka historia kontraktu.')
    tf=cfg['timeframe']
    selected=[r for r in rows[220:] if (not start_date or r['date'][:10]>=start_date) and (not end_date or r['date'][:10]<=end_date)]
    if not selected:raise ValueError('Brak historii kontraktu w wybranym okresie.')
    begin=candle_time(selected[0]['date'],tf).timestamp();end=candle_time(selected[-1]['date'],tf).timestamp()
    spec=contract_specs.fetch(cfg['instrument'])
    marks=mark_history(cfg['instrument'],tf,begin,end)
    funding=contract_specs.funding_history(cfg['instrument'],int(begin*1000),int((end+TIMEFRAMES[tf]['seconds'])*1000)-1)
    hourly=marks if tf=='1h' else mark_history(cfg['instrument'],'1h',int(begin//3600)*3600,int((end+TIMEFRAMES[tf]['seconds']-1)//3600)*3600,open_only=True)
    for item in funding:
        hour=int(item['timestamp']//3600)*3600
        if hour not in hourly:raise ValueError('Brak mark price dla rozliczenia fundingu.')
        item['markPrice']=hourly[hour]['open']
    return {'spec':spec,'marks':marks,'funding':funding,'mode':'contract_data',
            'notice':'Rzeczywiste OHLC mark price i stawki rozliczonego fundingu. Nominał fundingu wyceniany otwarciem godzinowej świecy mark. Bieżące specyfikacje/progi użyte dla historii; brak historycznych zmian progów i cen wykonania wewnątrz świecy.'}
