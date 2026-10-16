"""Public RSS headlines. Lexical headline tags are not analyst consensus or forecasts."""
import html
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS=[('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),
       ('Cointelegraph','https://cointelegraph.com/rss'),('EIA','https://www.eia.gov/rss/todayinenergy.xml')]
QUERIES={'BTC':'Bitcoin BTC cryptocurrency','ETH':'Ethereum ETH cryptocurrency','XRP':'XRP Ripple cryptocurrency','XLM':'XLM Stellar Lumens','GOLD':'gold price commodity','SILVER':'silver price commodity','OIL':'WTI crude oil price'}
CACHE={};LOCK=threading.Lock()


def plain(value):return html.unescape(re.sub(r'<[^>]*>',' ',value or '')).strip()[:1000]
def https(value):
    try:
        url=urllib.parse.urlparse(value)
        return url.scheme=='https' and bool(url.hostname) and not url.username and not url.password
    except ValueError:return False

def matches(key,text):
    text=text.casefold()
    if key=='XRP':return bool(re.search(r'\bxrp\b',text) or ('ripple' in text and re.search(r'crypto|token|blockchain|payment',text)))
    if key=='XLM':return bool(re.search(r'\bxlm\b|stellar lumens',text) or ('stellar' in text and re.search(r'blockchain|token|network|crypto',text)))
    if key=='BTC':return bool(re.search(r'\bbitcoin\b|\bbtc\b',text))
    if key=='ETH':return bool(re.search(r'\bethereum\b|\beth\b|\bether\b',text))
    if key=='GOLD':return bool(re.search(r'\bgold\b',text))
    if key=='SILVER':return bool(re.search(r'\bsilver\b',text) and 'silver lining' not in text)
    return bool(re.search(r'\boil\b|\bcrude\b|\bwti\b|\bopec\b|petroleum',text))


def headline_tags(title):
    text=title.casefold()
    positive=bool(re.search(r'\brall(?:y|ies)\b|\bsurg\w*|\bgains?\b|\brises?\b|\bbullish\b|\bsoars?\b|\bwzrost\w*',text))
    negative=bool(re.search(r'\bfall\w*|\bdrops?\b|\bslump\w*|\bbearish\b|\bplung\w*|\bloss\w*|\bspad\w*',text))
    tone='mixed' if positive and negative else 'positive' if positive else 'negative' if negative else 'neutral'
    themes=[]
    for label,pattern in [('Regulacje',r'\bsec\b|regulat|lawsuit|court|legal'),('Makro i stopy',r'\bfed\b|inflation|interest rate|dollar|central bank'),('Podaż i popyt',r'supply|demand|production|inventory|inventories|opec'),('Technologia i adopcja',r'blockchain|network|adoption|upgrade|partnership')]:
        if re.search(pattern,text):themes.append(label)
    opinion=bool(re.search(r'analyst|forecast|price target|predict|outlook',text))
    return {'tone':tone,'themes':themes,'analystCommentary':opinion}


def parse_feed(raw,provider):
    if len(raw)>2_000_000 or b'<!DOCTYPE' in raw.replace(b'\x00',b'').upper() or b'<!ENTITY' in raw.replace(b'\x00',b'').upper():raise ValueError('Nieprawidłowy RSS.')
    root=ET.fromstring(raw);entries=[]
    nodes=root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')
    for node in nodes[:150]:
        def value(name):
            child=node.find(name)
            if child is None:child=node.find('{http://www.w3.org/2005/Atom}'+name)
            return child.text if child is not None and child.text else ''
        title=plain(value('title'));link=value('link').strip()
        if not link:
            child=node.find('{http://www.w3.org/2005/Atom}link');link=child.get('href','') if child is not None else ''
        if not title or not https(link):continue
        published=None
        stamp=value('pubDate') or value('published') or value('updated')
        if stamp:
            try:
                date=parsedate_to_datetime(stamp)
                if date.tzinfo is not None:published=date.astimezone(timezone.utc).isoformat()
            except (ValueError,TypeError,OverflowError):
                try:
                    date=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                    if date.tzinfo is not None:published=date.astimezone(timezone.utc).isoformat()
                except (ValueError,TypeError):pass
        source=plain(value('source')) or provider
        title=re.sub(r'\s+-\s+'+re.escape(source)+r'$', '',title)
        entries.append({'title':title,'url':link,'source':source,'feed':provider,'publishedAt':published,
                        'snippet':plain(value('description') or value('summary'))[:350],**headline_tags(title)})
    return entries


def fetch_feed(spec):
    provider,url=spec
    with LOCK:cached=CACHE.get(url)
    if cached and time.time()-cached['attempt']<(60 if cached['error'] else 900):return cached
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Inwestapp RSS reader)','Accept':'application/rss+xml, application/xml, text/xml'})
        with urllib.request.urlopen(req,timeout=12) as response:raw=response.read(2_000_001)
        entries=parse_feed(raw,provider)
        result={'provider':provider,'url':url,'items':entries,'attempt':time.time(),'fetchedAt':datetime.now(timezone.utc).isoformat(),'error':None,'stale':False}
    except Exception:
        result={'provider':provider,'url':url,'items':cached['items'] if cached else [],'attempt':time.time(),
                'fetchedAt':cached['fetchedAt'] if cached else None,'error':'Nie udało się pobrać RSS. Źródło może blokować dostęp lub być chwilowo niedostępne.','stale':True}
    with LOCK:CACHE[url]=result
    return result


def get_news(key):
    if key not in QUERIES:raise ValueError('Nieprawidłowy instrument.')
    google='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':QUERIES[key],'hl':'en-US','gl':'US','ceid':'US:en'})
    specs=FEEDS+[('Google News — różni wydawcy',google)]
    with ThreadPoolExecutor(max_workers=4) as pool:feeds=list(pool.map(fetch_feed,specs))
    seen=set();items=[];now=datetime.now(timezone.utc)
    # Prefer original publisher feeds over aggregator duplicates.
    for feed in feeds:
        for item in feed['items']:
            if not matches(key,item['title']+' '+item['snippet']):continue
            identity=re.sub(r'\W+','',item['title'].casefold())
            if identity in seen:continue
            seen.add(identity);entry={**item,'staleSource':feed['stale']};items.append(entry)
    items.sort(key=lambda x:x['publishedAt'] or '',reverse=True);items=items[:60]
    fresh=[x for x in items if not x['staleSource'] and x['publishedAt'] and 0<=(now-datetime.fromisoformat(x['publishedAt'])).total_seconds()<=72*3600]
    return {'instrument':key,'items':items,'sources':[{k:f[k] for k in ('provider','url','fetchedAt','error','stale')} for f in feeds],
            'summary':{'recentCount':len(fresh),**{tone:sum(x['tone']==tone for x in fresh) for tone in ('positive','negative','mixed','neutral')}},
            'notice':'Automatyczne tagi rozpoznają słowa w tytule, nie weryfikują treści ani faktów. Podsumowanie obejmuje datowane wiadomości z ostatnich 72 h z działających źródeł. Wiadomości nie zmieniają sygnału technicznego i nie stanowią prognoz analityków.'}
