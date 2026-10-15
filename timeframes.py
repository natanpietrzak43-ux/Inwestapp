"""Canonical UTC candle boundaries, independent of browser display range."""
from datetime import datetime, timedelta, timezone

TIMEFRAMES = {
    '15m': {'label':'15 minut','short':'M15','seconds':900,'providerInterval':'15m','range':'60d','limitDays':60},
    '30m': {'label':'30 minut','short':'M30','seconds':1800,'providerInterval':'30m','range':'60d','limitDays':60},
    '1h': {'label':'1 godzina','short':'H1','seconds':3600,'providerInterval':'60m','range':'6mo','limitDays':183},
    '2h': {'label':'2 godziny','short':'H2','seconds':7200,'providerInterval':'60m','range':'6mo','aggregate':True,'limitDays':183},
    '4h': {'label':'4 godziny','short':'H4','seconds':14400,'providerInterval':'60m','range':'6mo','aggregate':True,'limitDays':183},
    '1d': {'label':'24 godziny','short':'D1','seconds':86400,'providerInterval':'1d','range':'5y','limitDays':1826}}


def candle_time(value, timeframe='1d'):
    if timeframe not in TIMEFRAMES:
        raise ValueError('Wybierz interwał 15m, 30m, 1h, 2h, 4h lub 1d.')
    text=str(value)
    if timeframe=='1d':
        return datetime.strptime(text,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    if 'T' not in text:
        raise ValueError('Interwał śróddzienny wymaga daty z godziną i strefą, np. 2026-10-13T10:00:00Z.')
    date=datetime.fromisoformat(text.replace('Z','+00:00'))
    if date.tzinfo is None:
        raise ValueError('Data wymaga strefy czasowej (Z lub +00:00).')
    return date.astimezone(timezone.utc)


def candle_closed(value, timeframe='1d', now=None):
    now=now or datetime.now(timezone.utc)
    return candle_time(value,timeframe)+timedelta(seconds=TIMEFRAMES[timeframe]['seconds'])<=now


def aggregate_hours(rows,timeframe,now=None):
    """Closed UTC buckets from available H1 bars; never invent missing session hours."""
    seconds=TIMEFRAMES[timeframe]['seconds'];buckets={}
    now=now or datetime.now(timezone.utc)
    for row in rows:
        ts=int(candle_time(row['date'],'1h').timestamp());start=ts-ts%seconds
        if datetime.fromtimestamp(start,timezone.utc)+timedelta(seconds=seconds)>now:continue
        group=buckets.setdefault(start,[]);group.append(row)
    result=[]
    for start,group in sorted(buckets.items()):
        group.sort(key=lambda r:r['date'])
        if not result and candle_time(rows[0]['date'],'1h').timestamp()>start:continue
        result.append({'date':datetime.fromtimestamp(start,timezone.utc).isoformat(),'open':group[0]['open'],
                       'high':max(r['high'] for r in group),'low':min(r['low'] for r in group),
                       'close':group[-1]['close'],'volume':sum(r['volume'] for r in group)})
    return result
