"""Configure notifications to the owner's chosen email, locally and privately."""
from pathlib import Path
import getpass
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import notification_channel
import secure_store
from user_data import data_dir


def main():
    print('Konfiguracja automatycznych alarmow na Twoj adres e-mail. Nie podawaj danych w czacie.')
    cfg={'host':input('Serwer SMTP Twojej poczty: ').strip(),'port':int(input('Port 465 TLS albo 587 STARTTLS: ').strip()),
         'username':input('Login SMTP: ').strip(),'password':getpass.getpass('Haslo aplikacji SMTP (ukryte): ').strip(),
         'sender':input('Adres nadawcy: ').strip(),'recipient':input('Twoj adres odbiorcy alarmow: ').strip()}
    notification_channel.validate(cfg);secure_store.write(data_dir()/'private'/'alerts.json',cfg)
    print('Zapisano prywatna konfiguracje. W Centrum automatyzacji uruchom test kanalu i sprawdz odebrana wiadomosc.')


if __name__=='__main__':main()
