# Zabezpieczenia Inwestapp 2.2

Wersja 2.2 dodaje wyłącznie odczyt kontekstu CoinGecko przez stały host `api.coingecko.com` i trzy ustalone endpointy Demo API. Klucz jest przesyłany tylko w nagłówku serwera, przechowywany jak pozostałe prywatne ustawienia; nie jest dostępny przez HTTP ani w eksporcie. Przekierowania są odrzucane. Nazwy z list popularności renderujemy jako tekst. Wbudowane limity, bufory i trwały licznik ograniczają zużycie API, ale nie potwierdzają limitów i kosztów planu dostawcy. CoinGecko nie trafia do cen zleceń, sygnałów, alertów ani wykresów OHLC. Wtyczka czatu i połączenie lokalnej aplikacji to oddzielne integracje.

To lokalna aplikacja dla jednego użytkownika Windows, z botem papierowym i oddzielnym OKX Demo. Poniższe mechanizmy ograniczają konkretne ataki na aplikację; nie stanowią antywirusa, niezależnego audytu ani gwarancji bezpieczeństwa komputera.

| Zagrożenie | Zastosowana ochrona | Granica ochrony |
|---|---|---|
| Obca strona uruchamia bota lub zmienia dane | Token operacji, kontrola Origin/Referer/Fetch Metadata, dokładny Host z portem, brak CORS | Token to ochrona przed obcą stroną, nie logowanie; lokalny program może go pobrać |
| DNS rebinding i dostęp z sieci lokalnej | Nasłuch tylko 127.0.0.1/localhost, kontrola adresu klienta i Host | Nie wystawiaj panelu przez publiczny proxy ani przekierowanie portu |
| Skrypt w RSS, strategii lub dzienniku | Renderowanie tekstu jako tekstu, brak wykonywania importów, CSP bez skryptów inline/eval i zewnętrznych skryptów | Style inline są potrzebne wykresom; CSP nie naprawia zainfekowanej przeglądarki |
| Przechwycenie kliknięć przez ramkę | frame-ancestors none, X-Frame-Options DENY | Nie chroni przed programem z dostępem do pulpitu |
| SSRF i przekierowanie źródła danych | Stała lista hostów HTTPS, brak userinfo/innych portów/schematów/przekierowań, weryfikacja TLS | To reguły aplikacji, nie zapora systemowa; własny SMTP/webhook to zaufana konfiguracja właściciela |
| Zbyt wiele lub zbyt duże żądania | 32 połączenia, 15 s na odczyt z gniazda, 2 kosztowne analizy naraz, limity żądań i danych | Długie backtesty mogą opóźnić następne analizy; worker giełdowy jest osobny |
| Niejednoznaczne żądania | Odrzucenie Transfer-Encoding, wielokrotnych krytycznych nagłówków, powtórzonych pól JSON, NaN/Infinity | Serwer pozostaje przeznaczony wyłącznie do użytku lokalnego |
| Ujawnienie kluczy | Windows DPAPI, prywatne pliki, atomowy zapis do losowego pliku tymczasowego, brak sekretów w eksporcie i logach HTTP | Złośliwy proces tego samego użytkownika może wywołać DPAPI |
| Zmieniona lub zmieszana paczka | Manifest SHA256 sprawdzany przez launcher i bezpośredni start serwera | Manifest nie jest podpisany; atakujący mogący wymienić kod i manifest może zmienić oba |
| Niepożądana transakcja | Osobny start Demo, walidacja zgodnej wersji, limity ryzyka i uzgodnienie zleceń | Nie potwierdzono autentycznych zleceń Demo bez kluczy konta; brak trybu realnych środków |

Publiczne dane pochodzą wyłącznie z hostów w `network_guard.HOSTS`. Przekierowanie nawet do innego zatwierdzonego hosta jest odrzucane; źródło pokazuje błąd zamiast pobrać inną treść. Konto Demo ma osobne stałe adresy REST/WebSocket i obowiązkowy nagłówek symulacji. MCP ma osobny stały endpoint i filtr narzędzi badawczych; wcześniejsza blokada dostawcy nie jest obchodzona. Własny webhook odrzuca jawne lokalne/prywatne IP i nazwy localhost/internal, ale nie jest zaporą DNS dla dowolnej domeny ustawionej świadomie przez właściciela.

Token ma losowość 32 bajtów, jest wspólny dla procesu serwera, przechowywany w pamięci i zmienia się po restarcie. Przeglądarka nie zapisuje go w cookie/localStorage/URL. Klienty lokalne API muszą pobrać go samodzielnie. Panel nie ma autoryzacji wielu użytkowników: nie udostępniaj go niezaufanym osobom. Ochrona aplikacji nie zatrzyma programu działającego już na Twoim koncie Windows.

## Aktualizacja na Windows

1. Zatrzymaj serwer, nadzór i stare zadania Harmonogramu. Zachowaj prywatną kopię folderu danych.
2. Pobierz pełny ZIP konkretnego wydania z właściwego repozytorium GitHub. Rozpakuj do nowego folderu. Nie mieszaj źródeł z poprzednią wersją.
3. Skanuj folder aktualnym Microsoft Defender lub własnym antywirusem. `Skanuj-Defender.bat` wywołuje istniejący skaner: nie instaluje ochrony, nie dodaje wyjątków i nie obchodzi PowerShell Execution Policy. Gdy polityka blokuje skrypt, skanuj przez menu folderu w Eksploratorze. Wynik sprawdź w Historii ochrony; wywołanie nie dowodzi zakończenia skanu bez zagrożeń.
4. Uruchom `Sprawdz-bezpieczenstwo.bat`, następnie `Uruchom.bat` lub wariant z nadzorem. Brak manifestu/zmienione pliki zatrzymują start. Nie regeneruj manifestu, żeby ominąć ostrzeżenie.
5. Sprawdź wersję 2.2.0 i kartę zabezpieczeń w Centrum automatyzacji. Po zmianie kodu strategie wymagają nowej wersji i walidacji. Kluczy nie wklejaj do czatu ani źródeł.
6. Utrzymuj wspierany i aktualizowany system. Na Windows 10 potrzebne są aktywne poprawki ESU lub przejście na wspierany system. Nie wyłączaj Defendera, SmartScreen ani zapory w celu uruchomienia aplikacji.

Manifest sprawdza zgodność i kompletność plików, nie podpis wydawcy ani brak wirusów. Nie zmieniamy ustawień ochrony Windows z chmury. Nie uruchomiliśmy skanera Windows ani DPAPI na komputerze użytkownika.

## Weryfikacja

Testy HTTP obejmują CSRF, fałszywy Host/port, obce Origin/Referer/Fetch Metadata, powielone nagłówki, ramkowanie ciała, limity, błędy i nagłówki bezpieczeństwa. Testy lokalne sprawdzają transport bez przekierowań, limity odpowiedzi, zapis sekretów i wykrywanie zmiany/usunięcia plików. Chromium testuje obcą stronę na innym porcie, odrzucenie odczytu i zapisu, renderowanie złośliwych wiadomości jako tekstu i rzeczywiste zablokowanie skryptu przez CSP. Dostawcy i Windows wymagają odrębnej weryfikacji na komputerze docelowym.

Rozwój: po przeglądzie zmian utrzymujący projekt generuje `python tools/build_release_manifest.py` i wykonuje testy. W CI manifest jest sprawdzany, nigdy automatycznie naprawiany. LF w `.gitattributes` zachowuje sumy na Windows/Linux. Dla znalezionej luki przygotuj opis i zanonimizowany sposób odtworzenia, bez kluczy i całej bazy.
