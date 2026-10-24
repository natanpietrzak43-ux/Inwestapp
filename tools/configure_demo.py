"""Run locally; keys use hidden input and never enter chat, Git or SQLite."""
from pathlib import Path
import getpass
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import secure_store
from user_data import data_dir


def main():
    print('Konfiguracja WYLACZNIE klucza OKX Demo. Uprawnienia: odczyt i handel, bez wyplat.')
    print('Wpisywane znaki sa niewidoczne. Kazde pole zatwierdz klawiszem Enter.')
    values={'environment':'demo'}
    for name,label in [('key','API key Demo'),('secret','Secret Demo'),('passphrase','Passphrase Demo')]:
        values[name]=getpass.getpass(label+': ').strip()
        if not values[name]:raise SystemExit('Puste pole. Konfiguracja nie zostala zapisana.')
    secure_store.write(data_dir()/'private'/'okx-demo.json',values)
    print('Zapisano prywatna konfiguracje poza plikami projektu/eksportem bazy. Uruchom aplikacje i sprawdz polaczenie Demo.')


if __name__=='__main__':main()
