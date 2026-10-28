"""Fixed, read-only source imports; external strategy code is inert research."""
import hashlib
import re
import urllib.request
import network_guard
from datetime import datetime,timezone
from market_data import INSTRUMENTS
from timeframes import TIMEFRAMES

REVISION='f3340ce11f5bdf62f598522e64d1f5638eaa13f5'
FILES={'strategy001':'user_data/strategies/Strategy001.py','strategy002':'user_data/strategies/Strategy002.py',
       'adx_momentum':'user_data/strategies/berlinguyinca/ADXMomentum.py'}


def context(body):
    key=body.get('instrument','XRP');tf=body.get('timeframe','1h');market=body.get('market','spot')
    if key not in INSTRUMENTS or tf not in TIMEFRAMES or market not in ('spot','perpetual'):raise ValueError('Nieprawidłowy kontekst instrumentu / świecy / rynku.')
    if market=='perpetual' and INSTRUMENTS[key]['kind']!='crypto':raise ValueError('Kontekst perpetual dotyczy obecnie tylko krypto.')
    return {'instrument':key,'timeframe':tf,'market':market,'suitabilityVerified':False}


def catalog():
    return {'checkedAt':'2026-10-23','templates':[{'id':key,'name':path.rsplit('/',1)[1][:-3]} for key,path in FILES.items()],
            'providers':[
                {'name':'Freqtrade strategies','access':'publiczny import plików źródłowych HTTPS / API aplikacji','status':'Potwierdzono odczyt 3 plików i licencji, bez konta.',
                 'url':'https://github.com/freqtrade/freqtrade-strategies','capability':'Materiały do przepisania i testów; brak potwierdzonej przewagi dla konkretnej pary.'},
                {'name':'QuantConnect API / MCP','access':'konto i token QuantConnect, integracja MCP w VS Code',
                 'status':'Oficjalne repo potwierdza API/testy. Starszy samodzielny MCP jest oznaczony jako deprecated; logowania i testu chmurowego nie wykonano.',
                 'url':'https://github.com/QuantConnect/mcp-server','capability':'Tworzenie i odczyt backtestów własnych projektów; nie katalog sprawdzonych dochodowych strategii.'},
                {'name':'trader.dev MCP','access':'istniejąca konfiguracja MCP','status':'Poprzednio potwierdzona blokada Cloudflare 1010 w tej chmurze; bez ponawiania połączeń.',
                 'url':'https://mcp.trader.dev','capability':'Badawcze narzędzia strategii po dopuszczeniu dostępu przez usługę.'}]
            }


def fetch(body):
    key=body.get('template');ctx=context(body)
    if key not in FILES:raise ValueError('Wybierz strategię z publicznego katalogu.')
    path=FILES[key];url=f'https://raw.githubusercontent.com/freqtrade/freqtrade-strategies/{REVISION}/{path}'
    request=urllib.request.Request(url,headers={'User-Agent':'Inwestapp/1.8','Accept':'text/plain'})
    try:
        raw=network_guard.read(request,limit=128_000,timeout=15)
    except OSError:raise ValueError('Nie udało się pobrać publicznego źródła Freqtrade. Nie podstawiono lokalnej kopii.') from None
    if len(raw)>128_000:raise ValueError('Źródło przekracza limit 128 KB.')
    try:code=raw.decode('utf-8')
    except UnicodeError:raise ValueError('Źródło nie jest tekstem UTF-8.') from None
    return {'provider':'Freqtrade public sources','tool':key,'fetchedAt':datetime.now(timezone.utc).isoformat(),
            'context':ctx,'verified':False,'sourceUrl':url,'revision':REVISION,'sha256':hashlib.sha256(raw).hexdigest(),
            'license':'GPL-3.0','licenseUrl':f'https://github.com/freqtrade/freqtrade-strategies/blob/{REVISION}/LICENSE',
            'content':{'code':code,'indicatorsMentioned':sorted(set(re.findall(r'ta\.([A-Za-z0-9_]+)\(',code))),
                       'notice':'Kod źródłowy do analizy. Nie został uruchomiony, zainstalowany jako strategia bota ani zweryfikowany dla wybranego instrumentu. Testy Inwestapp dotyczą lokalnych reguł.'}}
