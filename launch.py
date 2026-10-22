"""Validate the unpacked app and avoid silently opening an older server.

Never kills another process or starts another paper worker on a different port.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import webbrowser

from app_release import APP_VERSION, FEATURES, STATIC_PATHS
from local_server import port_busy, report_bind_error

ROOT = Path(__file__).resolve().parent
REQUIRED = ('server.py','app_release.py','local_server.py','analysis_engine.py','market_data.py','paper_bot.py',
            'agent_pipeline.py','okx_data.py','technical_tools.py','custom_indicators.py',
            'timeframes.py','user_data.py','news_data.py','strategy_lab.py','trader_mcp.py')


def installation_errors(root=ROOT):
    errors=[]
    for name in (*REQUIRED, *('web/'+name for name in STATIC_PATHS.values())):
        if not (root/name).is_file():errors.append('Brak pliku: '+name)
    if (root/'web/index.html').is_file():
        try:
            html=(root/'web/index.html').read_text(encoding='utf-8')
            match=re.search(r'data-ui-version="([^"]+)"',html)
            if not match or match.group(1)!=APP_VERSION:errors.append('Pliki interfejsu i serwera pochodza z roznych wersji.')
        except OSError:errors.append('Nie mozna odczytac plikow interfejsu.')
    return errors


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_):return None


def running_release(port):
    # Local process inspection must not use an external proxy or follow redirects.
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:
            raw=response.read(16385)
        if len(raw)>16384:return None
        result=json.loads(raw)
        if not isinstance(result,dict) or result.get('status')!='ok':return None
        if not isinstance(result.get('instruments'),list) or not {'XRP','XLM'}.issubset(result['instruments']):return None
        return result
    except (OSError,ValueError,TypeError):return None


def run_server(port):
    child=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(port),'--open-browser'],cwd=ROOT)
    try:
        return child.wait()
    except KeyboardInterrupt:
        # Ctrl+C reaches both processes in the same console. Let the server
        # finish its own shutdown instead of printing a launcher traceback.
        print('\nZatrzymywanie aplikacji...',flush=True)
        try:
            return child.wait(timeout=10)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            child.terminate()
            try:return child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                return child.wait()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Uruchom zweryfikowana wersje Inwestapp.')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--check-installation',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('Port: 1-65535.')
    print('Inwestapp '+APP_VERSION+' | folder: '+str(ROOT),flush=True)
    errors=installation_errors()
    if errors:
        print('\n'.join(errors));print('Rozpakuj CALY ZIP do nowego folderu i uruchom z niego Uruchom.bat.');return 2
    if args.check_installation:print('Pliki nowego wykresu i wyjasnien sa kompletne.');return 0
    running=None
    try:
        busy=port_busy(args.port)
    except OSError as error:
        # An exclusive Windows listener can reject bind with WSAEACCES too.
        running=running_release(args.port)
        if not running:
            report_bind_error(error,args.port)
            return 4
        busy=True
    if busy:
        if running is None:running=running_release(args.port)
        if running and running.get('version')==APP_VERSION and isinstance(running.get('features'),list) and set(FEATURES).issubset(running['features']):
            print('Ta wersja juz dziala. Otwieram istniejaca aplikacje, bez drugiego serwera.',flush=True)
            webbrowser.open(f'http://127.0.0.1:{args.port}/?v={APP_VERSION}');return 0
        version=running.get('version') if running else None
        print(f'\nPort {args.port} jest zajety'+(f' przez Inwestapp {version}.' if isinstance(version,str) and re.fullmatch(r'[0-9.]{1,20}',version) else '.'))
        print('Nowa wersja NIE zostala uruchomiona. Nie otwieram starszej aplikacji.')
        if running:
            print('W oknie terminala STAREJ aplikacji nacisnij Ctrl+C.')
            print('Uruchom ponownie Uruchom.bat z TEGO nowego folderu.')
        else:
            print('Nie potwierdzono, ze ten proces to Inwestapp. Sprawdz w CMD:')
            print(f'netstat -ano | findstr :{args.port}')
            print('Skopiuj wynik do diagnostyki, aby ustalic program zajmujacy port.')
        return 3
    return run_server(args.port)


if __name__=='__main__':sys.exit(main())
