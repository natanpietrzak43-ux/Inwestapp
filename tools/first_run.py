"""Local menu groups existing tools; never sends secrets or starts trading."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import launch


def main():
    errors=launch.installation_errors()
    if errors:print('\n'.join(errors));return 2
    options={'1':ROOT/'launch.py','2':ROOT/'tools/configure_demo.py','3':ROOT/'tools/configure_coingecko.py',
             '4':ROOT/'tools/configure_alerts.py','5':ROOT/'tools/security_check.py'}
    while True:
        print('\nINWESTAPP - pierwszy start i konfiguracja\n1. Otworz aplikacje (bez uruchamiania handlu)\n2. Klucze OKX Demo\n3. Klucz CoinGecko (opcjonalnie)\n4. Powiadomienia e-mail (opcjonalnie)\n5. Sprawdz zgodnosc plikow\n0. Zakoncz')
        choice=input('Wybierz numer: ').strip()
        if choice=='0':return 0
        if choice not in options:print('Wybierz numer z listy.');continue
        try:result=subprocess.run([sys.executable,str(options[choice])],cwd=ROOT)
        except KeyboardInterrupt:print('\nMenu zamkniete.');return 0
        if result.returncode:print('Operacja nie zostala potwierdzona. Przeczytaj komunikat powyzej.')


if __name__=='__main__':raise SystemExit(main())
