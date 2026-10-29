"""Local, hidden CoinGecko Demo key configuration; no network request."""
import getpass
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import secure_store
from user_data import data_dir


def main():
    print('CoinGecko Demo API - tylko dane rynkowe, bez handlu i bez uprawnien gieldy.')
    print('Utworz klucz Demo w swoim koncie: https://www.coingecko.com/en/api')
    print('Klucz wpisujesz lokalnie. Znaki sa niewidoczne; zatwierdz Enter. Nie wklejaj do czatu.')
    key = getpass.getpass('CoinGecko Demo API key: ').strip()
    if not key or len(key)>256 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise SystemExit('Nieprawidlowe pole; konfiguracja nie zostala zapisana.')
    secure_store.write(data_dir()/'private'/'coingecko.json', {'environment':'demo','key':key})
    print('Zapisano prywatnie. W aplikacji otworz CoinGecko i kliknij Pobierz dane.')
    print('Lokalny budzet domyslny: 9000 zadan/miesiac; nie jest limitem ani potwierdzeniem planu dostawcy.')
    print('Narzędzie nie wyslalo zadania API. Zuzycie i ewentualne koszty sprawdz w panelu CoinGecko.')


if __name__=='__main__':main()
