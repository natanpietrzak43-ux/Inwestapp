"""Canonical UTC candle boundaries, independent of browser display range."""
from datetime import datetime, timedelta, timezone

TIMEFRAMES = {'1h': {'label':'H1 · 1 godzina','seconds':3600,'providerInterval':'60m','range':'6mo'},
              '1d': {'label':'D1 · 1 dzień','seconds':86400,'providerInterval':'1d','range':'5y'}}


def candle_time(value, timeframe='1d'):
    if timeframe not in TIMEFRAMES:
        raise ValueError('Nieprawidłowy interwał; wybierz 1h lub 1d.')
    text=str(value)
    if timeframe=='1d':
        return datetime.strptime(text,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    if 'T' not in text:
        raise ValueError('H1 wymaga daty z godziną i strefą, np. 2026-10-13T10:00:00Z.')
    date=datetime.fromisoformat(text.replace('Z','+00:00'))
    if date.tzinfo is None:
        raise ValueError('Data H1 wymaga strefy czasowej (Z lub +00:00).')
    return date.astimezone(timezone.utc)


def candle_closed(value, timeframe='1d', now=None):
    now=now or datetime.now(timezone.utc)
    return candle_time(value,timeframe)+timedelta(seconds=TIMEFRAMES[timeframe]['seconds'])<=now
