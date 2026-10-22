# Inwestapp 1.7.2

Prywatny warsztat analizy technicznej XRP, XLM, BTC/USD, ETH/USD, srebra, ropy WTI i złota. Świece M15/M30/H1/H2/H4/D1, wybór narzędzi, pięć gotowych zestawów, plan ryzyka i test historyczny. Alerty cenowe, wiadomości RSS, dziennik transakcji, licznik wpisanych prognoz oraz bot papierowy i laboratorium strategii. Brak rzeczywistych zleceń i połączenia z brokerem.

## Poprawka 1.7.2 — prawidłowe rozpoznawanie błędów portu w Windows

Poprzedni launcher uznawał każdy błąd próbnego połączenia (również timeout) za zajęty port. W Windows mogło to blokować start mimo pustego wyniku `netstat`. Teraz sprawdzamy możliwość przypisania lokalnego portu przez `bind`, zamiast próbować połączenia. Zajęty adres, odmowa dostępu/rezerwacja systemowa i inne błędy mają osobne komunikaty wraz z oryginalnym błędem systemowym. Windows korzysta z wyłącznego dostępu do portu, aby uniknąć współdzielenia adresu przez dwa serwery.

Rozpakuj **cały ZIP 1.7.2 do nowego folderu** i uruchom znajdujący się w nim `Uruchom.bat`. Nie kopiuj pojedynczych plików między wydaniami. Launcher nadal nie zatrzymuje cudzych procesów ani samoczynnie nie wybiera innego portu. Jeśli błąd się powtórzy, skopiuj cały komunikat, zwłaszcza `Szczegoly systemowe`. `WinError 10013` oznacza odmowę dostępu; sam nie dowodzi, że działa starszy serwer. Polecenie `netsh interface ipv4 show excludedportrange protocol=tcp` jedynie wyświetla rezerwacje Windows. Nie usuwaj ich w ciemno.

Opcjonalny wybrany port: w folderze aplikacji otwórz CMD i wpisz `py -3 launch.py --port 8001` lub `Uruchom.bat --port 8001`. Nie uruchamiaj równolegle dwóch wersji na tej samej bazie bota. Zmiana portu zmienia adres aplikacji: oznaczenia wykresu i ustawienia zapisane w przeglądarce pozostają przypisane do poprzedniego adresu. Dane SQLite pozostają we wspólnym katalogu użytkownika.

Weryfikacja 1.7.2: 162 testy Python/HTTP i 14 testów modelu wykresu zakończone powodzeniem; rzeczywisty start przez launcher, kontrolowane zamknięcie Ctrl+C ze zwolnieniem portu, odmowa startu drugiego serwera i test przeglądarki potwierdzający wersję oraz wczytanie funkcji. Testy regresyjne obejmują błędnie odrzucony wolny port przy timeout połączenia, rzeczywisty zajęty port, odmowę dostępu, rozpoznanie działającej aplikacji przy wyłącznym dostępie oraz konfigurację wyłączności Windows. Natywne uruchomienie na Windows wymaga potwierdzenia na komputerze użytkownika; testy chmurowe wykonano na Linux.

## Widoczność aktualizacji i wykrywanie starego serwera

Jeśli w prawym górnym rogu widzisz **1.6**, oglądasz starszy interfejs. Funkcje interaktywnego wykresu i „?” są od wersji 1.7. Samo pobranie ZIP-a nie przełącza działającego serwera na nowy folder.

1. W terminalu starej aplikacji naciśnij **Ctrl+C**.
2. Rozpakuj **cały ZIP 1.7.2** do nowego folderu. Wejdź do folderu, w którym jest `Uruchom.bat` i `server.py`.
3. Uruchom **Uruchom.bat z nowego folderu** i pozostaw jego okno otwarte.
4. W przeglądarce naciśnij **Ctrl+F5**. U góry ma być **Interfejs 1.7.2 · serwer 1.7.2** i komunikat o wczytaniu wykresu oraz wyjaśnień.
5. Kliknij **Otwórz nowy wykres** albo **Obejrzyj funkcje na danych demonstracyjnych**. Podgląd demonstracyjny jest wyraźnie oznaczony i pozwala sprawdzić funkcje, gdy dostawca notowań jest niedostępny. „?” znajdziesz przy narzędziach w sekcji **Twój zestaw analityczny**; pasek nawigacji i rysowania jest przy wykresie.

Launcher `launch.py` sprawdza kompletność plików i zgodność wersji HTML. Jeśli na porcie działa starsza aplikacja, pokazuje jej wersję i instrukcję zatrzymania, kończy się kodem 3 i nie uruchamia drugiego bota ani nie otwiera starej strony. Nie zabija żadnych procesów i nie wybiera po cichu innego portu. Jeśli potwierdzi już działającą wersję 1.7.2 z wymaganymi funkcjami, otwiera istniejącą aplikację bez tworzenia drugiego serwera. `python launch.py --check-installation` sprawdza same pliki, bez uruchamiania bota.

Strona sprawdza wersję serwera i wczytanie modułów. Przy niezgodności lub błędzie ładowania pokazuje widoczny komunikat. Pliki interfejsu mają adresy z numerem wersji, a odpowiedzi lokalnego serwera nagłówek `Cache-Control: no-store`. Wersja jest wspólna w `app_release.py`; dostęp do danych, wskaźniki, oznaczenia wykresu i osobiste rekordy nie są resetowane. Bezpośrednie uruchomienie `python server.py` pozostaje obsługiwane; przy zajętym porcie również kończy się czytelnym komunikatem.

Wcześniejsza weryfikacja 1.7.1: 154 testy Python/HTTP, w tym rzeczywisty test launchera przy zajętym porcie ze starszym serwerem; 14 testów modelu wykresu; testy przeglądarkowe dla nowego wykresu, wersji 1.7.1, podglądu bez dostępu do notowań, niezgodności wersji i brakującego modułu. Składnia i działanie skryptów Python sprawdzone w chmurze Linux; samego pliku BAT nie uruchamiano na Windowsie.

## Aktualizacja 1.7 — interaktywny wykres i wyjaśnienia wskaźników

W **Przeglądzie rynku** wykres ma krzyżyk kursora z ceną na osi pionowej i datą/czasem wskazanej świecy. Podgląd pokazuje osobno cenę w miejscu kursora oraz OHLC (otwarcie, maksimum, minimum, zamknięcie), wolumen i wybrane odczyty wskaźników tej świecy. Wyższa precyzja prezentacji nie zwiększa dokładności dostawcy: cena kursora to pozycja na skali, nie potwierdzona transakcja po tej cenie. Czas świec śróddziennych wyświetlamy w **Europe/Warsaw**, z oznaczeniem GMT+1/+2 rozróżniającym zmianę czasu. D1 ma tylko datę źródła; nie dopisujemy mu pozornej godziny otwarcia giełdy.

- **Kółko myszy** przybliża i oddala wokół wskazanego miejsca. Przyciski **＋/−** robią to samo wokół środka. Skala ceny dopasowuje się do widocznych świec i wybranych linii.
- **Przesuń**: przeciągnij w poziomie, aby oglądać starszą historię. **Najnowsze** wraca do końca danych, **Reset widoku** i dwuklik w trybie przesuwania przywracają wybrany zakres dni. Na ekranie dotykowym można przesuwać jednym palcem i przybliżać/oddalać dwoma.
- **Punkt**, **Poziom ceny**, **Linia**: wybierz narzędzie i kliknij wykres; linia wymaga dwóch końców. Dwa ostatnie punkty pokazują zmianę ceny, procent oraz odstęp czasu. **Escape** anuluje rozpoczętą linię i włącza przesuwanie. **Cofnij oznaczenie** działa również po usunięciu wszystkich oznaczeń.
- Lista **Punkty i linie odniesienia** pozwala pokazać lub usunąć pojedyncze oznaczenie. Maksymalnie 50. Zapis w pamięci tej przeglądarki, osobno według instrumentu, dostawcy, waluty, trybu i interwału; CSV ma dodatkowe rozróżnienie zestawu danych. Odświeżenie strony lub aktualizacja ZIP-em zachowuje oznaczenia przy tej samej przeglądarce i adresie/porcie. Nie są kopiowane do SQLite/eksportu dziennika ani między komputerami. Wyczyszczenie pamięci przeglądarki je usuwa.
- Po ustawieniu fokusu na wykresie: **←/→** przechodzi po świecach, **↑/↓** zmienia poziom ceny kursora, **＋/−** zmienia zoom, **Home** przechodzi do najnowszych danych. W trybie oznaczeń **Enter/spacja** dodaje punkt w miejscu kursora. Narzędzia i wyjaśnienia są dostępne z klawiatury.

Widoczne oscylatory korzystają z tego samego wycinka historii co wykres ceny. Zoom, przesuwanie i oznaczenia nie wysyłają zleceń ani nie zmieniają obliczeń wskaźników, sygnału, backtestu lub bota: te nadal wykorzystują pełną pobraną historię. Nie dodajemy syntetycznych świec ani notowań pomiędzy odczytami dostawcy. To lokalny wykres SVG z funkcjami nawigacji i adnotacji, bez zależności od konta/serwisu TradingView.

Przycisk **?** przy każdym z 14 narzędzi, przy legendzie, wykresach oscylatorów i odczytach oraz przy ATR otwiera wyjaśnienie: **za co odpowiada**, **jak czytać**, **jak działa w Inwestapp**, **na co uważać**. Wyjaśnienia opisują faktyczne okresy i progi aplikacji. Kliknięcie nie zmienia zaznaczenia wskaźnika ani nie pobiera nowej analizy. Okno można zamknąć przyciskiem, klawiszem Escape lub kliknięciem poza nim.

Weryfikacja: 145 testów Python/HTTP; `node --test tests/test_chart.cjs` — 14 testów modelu widoku i poprawności oznaczeń. Opcjonalny `tests/chart_browser.cjs` (Playwright/Chromium, osobny serwer z tymczasowym INWESTAPP_DATA_DIR) sprawdza odczyt kursora, skalowanie współrzędnych, zoom/pan, zapis i odseparowanie oznaczeń, cofanie, wszystkie 14 wyjaśnień, D1, klawiaturę, widok mobilny i gest dwoma palcami. Aplikacja nadal nie wymaga dodatkowych pakietów do uruchomienia.

## Aktualizacja 1.6 — OKX i zespół agentów

W **Źródło danych** wybierz **OKX spot · krypto / USDT** dla XRP, XLM, BTC lub ETH. Publiczne REST API nie wymaga klucza: `/api/v5/market/ticker` oraz `/api/v5/market/history-candles`. Ceny i świece są z tej samej giełdy. Bieżące ceny to odczyty z buforem 10 s, odświeżane przez interfejs zwykle co 15 s; to nie strumień tickowy ani gwarancja ciągłości. Dla złota, srebra i ropy wybierz dotychczasowe źródło Yahoo/zarządzanie w USD. Nie stosujemy automatycznego zastępowania awarii OKX inną giełdą lub demonstracją.

**USDT pozostaje USDT, bez założenia kursu 1:1 do USD.** Analiza, plan, konto bota i wyniki testu pokazują walutę źródła. Ręczny dziennik, alerty i wpisane prognozy nadal są w USD i używają osobno Coinbase/Yahoo, także podczas przeglądania wykresu OKX. Przy uruchomieniu bota wybierz ten sam dostawca cen i świec. Istniejące konto z transakcjami nie zmienia waluty. Po zamknięciu pozycji i zatrzymaniu bota przycisk **Nowe konto symulacyjne** archiwizuje poprzedni stan i uruchamia nowe konto z formularza; historia pozostaje w SQLite i eksporcie JSON. UI pokazuje podsumowania poprzednich kont, a szczegóły są w eksporcie. To nowe konto testowe, nie kontynuacja jego wyników.

Świece OKX: natywne `15m`, `30m`, `1H`, `2H`, `4H`, `1Dutc`. Używamy tylko `confirm=1` i zakończonych przedziałów UTC; `vol` oznacza wolumen bazowego aktywa spot. Odpowiedzi odwracamy do rosnących dat, sprawdzamy OHLC, walidujemy paginację i odrzucamy sprzeczne duplikaty. Bufor w ignorowanym `.cache/okx` uzupełnia historię przy kolejnych odczytach. Pierwsze pobranie wymaga wielu stron i może potrwać dłużej; brak połączenia nie zmienia starego bufora w świeże dane. Limit 5000 świec: około 52 dni M15, 104 dni M30, 180 dni H1/H2/H4, 400 dni D1 (minimum dla laboratorium). Rzeczywiste pokrycie jest pokazane przy wykresie; brakujących okresów nie dopisujemy.

W **Bot i strategie** wybierz **Zespół agentów regułowych**, źródło i instrument, zestaw wskaźników oraz limity, następnie **Uruchom bota papierowego**. Dotychczasowe zapisane konta pozostają przy starym silniku do świadomej zmiany konfiguracji. Agenci są lokalnymi modułami deterministycznych reguł, nie modelami LLM; nie wymagają subskrypcji AI, MCP ani kluczy OKX.

Przebieg zgodny z diagramem:

1. **Dane**: odczyt wybranego rynku, pary i waluty.
2. **Kontrola jakości**: poprawne zamknięte OHLCV, instrument/interwał/źródło/waluta, świeża cena i potwierdzenie pobrania świec do 120 s. Dla ciągłego rynku krypto sprawdzamy luki i ostatnią oczekiwaną świecę z 120 s na jej publikację. Kontrola odchylenia ceny od ostatniego zamknięcia domyślnie 3%. Błąd zatrzymuje analityków i zapisuje WAIT.
3. **Agenci trendu, momentum, wolumenu, reżimu i kontekstu**: odczyty wskaźników wybranego zestawu, z uzasadnieniami. Powiązane wskaźniki pozostają jedną grupą.
4. **Agent nadrzędny**: zgodność wymaganych grup wg dotychczasowych jawnych reguł; konflikt oznacza WAIT. Sprzedaż oznacza zamknięcie long, bez shortów.
5. **Agent ryzyka z wetem**: blokada historyczna BUY, świeżość/spójność danych, brak innej pozycji, spread domyślnie do 30 pb, ekspozycja do 25% kapitału, ryzyko na transakcję, strata dzienna domyślnie 3% i obsunięcie konta od szczytu 10%. Wejście po ask + poślizg, wyjście po bid − poślizg w OKX; obie prowizje oraz poślizg stopa są uwzględnione w wielkości pozycji. Są to założenia symulacji, nie pomiar rzeczywistego wykonania giełdowego.
6. **Wykonanie albo WAIT**: zlecenie papierowe czeka na świeżą cenę z czasem późniejszym od decyzji. Przed BUY ponawiamy ocenę danych, grup i limitów; pogorszenie anuluje zlecenie. Wygasa ono po 20 minutach. Stop 2 ATR, cel 3 ATR. Po wyjściu brak ponownego wejścia na tej samej świecy. Ochronne wyjście lub ręczne zamknięcie wymagają świeżej zgodnej ceny, ale nie wymagają nowej analizy wskaźników.
7. **Dziennik i ocena**: każdy cykl ma identyfikator, odczyty, propozycję, decyzję ryzyka, przyczynę WAIT oraz status wykonania i wycenę konta. UI pokazuje ostatnie 30, baza zachowuje 5000 cykli łącznie; transakcje zachowują osobno audyt wejścia i wyjścia nawet po rotacji cykli. Wyniki kont różnych walut nie są sumowane.

Pobieranie/analiza historii działa w osobnym wątku, aby wolna paginacja nie zatrzymywała ochrony pozycji. Brak świeżej ceny nadal uniemożliwia wyjście. Cykle cenowe zwykle co 15 s plus opóźnienie dostawcy; luki i ruchy między odczytami mogą zwiększyć stratę. Limit dzienny zatrzymuje nowe wejścia i zamyka pozycję po świeżej cenie; Start nie kasuje go w tym samym dniu UTC. Wymaga świadomego wznowienia kolejnego dnia. Limit obsunięcia nie jest zerowany Startem; wyniki należy ocenić przed ewentualnym nowym kontem.

**Laboratorium** obsługuje historię OKX i Yahoo, demonstrację oraz CSV. W dalszym ciągu porównuje pięć stałych rdzeni wskaźnikowych z rozdzieleniem chronologicznym, kosztami i poślizgiem. Nie odtwarza historycznie pełnego zespołu agentów, spreadu, limitów konta ani bieżącej bramki BUY. Cały nowy przebieg należy oceniać w handlu papierowym na kolejnych napływających danych. Nie oznaczamy wyników laboratorium jako walidacji całego bota.

**Weryfikacja w tej chmurze (2026-10-19):** po początkowym błędzie proxy potwierdzono działające publiczne tickery wszystkich czterech kryptowalut oraz analizę XLM we wszystkich sześciu interwałach: 5000 M15, 5000 M30, 4320 H1, 2160 H2, 1080 H4 i 400 D1. Pełny cykl na prawdziwych danych XLM H1 przeszedł kontrolę jakości: agenci wskazali wyjście, a ryzyko prawidłowo zwróciło WAIT przy braku pozycji long. Nie otwarto shorta ani rzeczywistego zlecenia. 145 testów jednostkowych/HTTP sprawdza m.in. parser, waluty, błędy i paginację OKX, wetowanie, ponowną kontrolę wejść, prowizje, bid/ask, limity, współbieżność, archiwizację i migrację starego konta. Chromium: start/stop, zapis audytu, archiwum, pięć kart laboratorium, widok mobilny bez przepełnienia; brak błędów JavaScript. Domenę `www.okx.com` dodano do projektu konfiguracji sieci; ustawienia wymagają przeglądu/zapisania/publikacji dla utrwalenia konfiguracji. Dostęp do strony dokumentacji nadal zwracał HTTP403; kontrakty REST porównano z [oficjalnym SDK OKX](https://github.com/okxapi/python-okx/blob/master/okx/MarketData.py) i zweryfikowano powyższymi odpowiedziami publicznego API. Dodatnie wyniki demonstracji nie są wynikami prawdziwego handlu.

## Uruchomienie i aktualizacja na Windows

1. Zatrzymaj poprzednią wersję przez Ctrl+C w jej terminalu.
2. Rozpakuj ZIP nowej wersji do nowego folderu.
3. W folderze z `server.py` dwukrotnie kliknij **Uruchom.bat** (Windows może pokazywać nazwę „Uruchom”). Python 3.10+ musi być zainstalowany.
4. Przeglądarka otworzy aplikację. Pozostaw terminal otwarty. Ctrl+F5 odświeża stare pliki strony.

Alternatywnie, z folderu aplikacji:

```sh
python server.py --host 127.0.0.1 --port 8000
```

macOS/Linux: użyj `python3`. Brak zewnętrznych zależności. Opcja `--open-browser` otwiera przeglądarkę. Nie wystawiaj tego serwera bez uwierzytelniania do Internetu. W onboardingu chmurowym podgląd localhost nie jest udostępniany; używamy lokalnych żądań do weryfikacji.

## Aktualizacja 1.5 — bot papierowy i laboratorium

Otwórz **Bot i strategie**. Aplikacja nie ma połączenia do wysyłania zleceń na giełdę/brokera. Bot działa wyłącznie na papierowym koncie USD i nie korzysta z kluczy transakcyjnych.

1. Wybierz instrument, interwał, jeden z pięciu lokalnych zestawów, kapitał początkowy, ryzyko, prowizję i poślizg w pb na stronę oraz limit straty dnia UTC.
2. Kliknij **Uruchom bota papierowego**. Cykl wykonuje się około co 15 sekund w procesie serwera. Przeglądarka może być zamknięta; komputer i serwer muszą pracować. Po ponownym uruchomieniu serwera aktywny bot wznawia się z zapisanego stanu.
3. Sygnały pochodzą z zamkniętych świec. Wejście wymaga zgodności wszystkich wybranych grup oraz istniejącej blokady historycznej BUY. Ta blokada ocenia rdzeń reguł na historii, z kosztami i ustawionym poślizgiem; nie jest dowodem zyskowności. Częste „czekaj” oznacza brak spełnienia reguł, a nie błąd instalacji.
4. Po decyzji bot oczekuje na pierwszy zaobserwowany świeży odczyt **z czasem notowania nie wcześniejszym niż decyzja**. Nie wpisuje fikcyjnego wejścia po historycznej cenie. Oczekujące zlecenie wygasa po 20 minutach. Krypto dopuszcza wiek ceny 120 s, surowce 1200 s; opóźnione notowania referencyjne mogą opóźniać papierowe wykonanie.
5. Maksymalnie jedna pozycja long, bez dźwigni. Wielkość wyznacza ryzyko i dostępna gotówka. Stop = 2 ATR, cel = 3 ATR. Zakup obejmuje dodatni poślizg i prowizję; sprzedaż ujemny poślizg i prowizję. To szacunki, bez symulacji arkusza zleceń, płynności i realnego wykonania.
6. Stop/cel są oceniane na dostępnych odczytach cen. Nie wykryjemy każdego ruchu pomiędzy odczytami ani podczas awarii/uśpienia. Po luce realizacja jest symulowana po pierwszej zaobserwowanej cenie, a strata może przekroczyć plan.
7. Limit straty dnia porównuje kapitał po kosztach likwidacji z pierwszą dostępną wyceną dnia UTC. Przekroczenie wyłącza nowe wejścia i zamyka papierową pozycję po dostępnej świeżej cenie. Bot nie uruchamia się automatycznie następnego dnia — użytkownik musi ponownie kliknąć Start. Restart/Start tego samego dnia nie zeruje punktu odniesienia limitu.
8. **Zatrzymaj nowe wejścia** anuluje oczekujące kupno. Stop/cel otwartej pozycji nadal działają podczas pracy serwera. **Zamknij papierową pozycję** kolejkuje wyjście po kolejnym świeżym odczycie. Samo zamknięcie przeglądarki nie zatrzymuje bota.

Kapitał początkowy po pierwszej zamkniętej transakcji jest stały. Konfiguracji otwartej pozycji nie można zmienić bez jej zamknięcia. Konto i wszystkie transakcje/zdarzenia są trwałe w tej samej lokalnej bazie SQLite, ale oddzielone od ręcznego dziennika. UI pokazuje ostatnie 200 transakcji i 100 zdarzeń; pełne tabele obejmuje eksport JSON i kopia bazy. Surowce oznaczają ułamkową referencyjną ekspozycję z mnożnikiem 1, nie kontrakt futures/CFD. Brak podatków, finansowania i przeliczeń walut.

### Porównanie strategii

W tym samym panelu wybierz źródło **Yahoo / demonstracja / wcześniej importowany CSV** i kliknij **Porównaj strategie**. Minimalnie 400 świec. Wszystkie pięć lokalnych zestawów dostaje ten sam okres, kapitał, ryzyko, prowizje i poślizg. Pokazujemy wynik, liczbę transakcji, profit factor i maksymalne obsunięcie.

Pierwsze 200 świec to rozgrzewka. Kolejne 70% dostępnego okresu to część początkowa; końcowe 30% jest testowane od osobnego portfela z takim samym kapitałem, bez pozycji przeniesionej z początku. Wskaźniki w końcowym teście mogą korzystać z wcześniejszej historii; pierwsze otwarcie testu może wykonać sygnał z ostatniej świecy części początkowej. Obliczenia wskaźników nie używają przyszłych cen. Nie optymalizujemy parametrów i nie wybieramy automatycznie zwycięzcy.

Minimalny **filtr badawczy** wymaga 30 zamkniętych transakcji początkowych i 10 końcowych, dodatniego wyniku oraz określonego profit factor > 1 w obu częściach. Przejście nie dowodzi przewagi. Ponowne wybieranie zestawu po obejrzeniu końcowego wyniku odbiera temu fragmentowi niezależność. To porównanie stałych modeli, nie automatyczna optymalizacja/walidacja krocząca. Dodatni wynik nie aktywuje bota.

Test historyczny symuluje wejście na kolejnym otwarciu i poślizg/prowizję po obu stronach; bot papierowy używa pierwszej świeżej obserwacji po decyzji. Wyniki nie muszą być identyczne. Dotychczasowy Test strategii w Przeglądzie zachowuje domyślny dodatkowy poślizg 0 pb; laboratorium i bot domyślnie mają 5 pb. Raporty jawnie oceniają rdzeń reguł bez historycznego stosowania blokady BUY.

### Globalny MCP trader.dev w chmurze

Na żądanie użytkownika dodano globalny wpis Codex CLI **trader-dev** w tej chmurze. Korzysta z mostka Node i przypiętego `mcp-remote@0.15.1`. Mostek obsługuje sieciowe proxy (`--enable-proxy`), ma prywatne katalogi cache/auth i usuwa klucz z wyjścia stdout/stderr. Klucz jest poza repozytorium, w prywatnym `~/.codex/trader-dev/api-key` (0600); wpis Codexa wskazuje plik mostka i nie zawiera wartości klucza. Narzędzie `mcp-remote` otrzymuje klucz w parametrze URL swojego procesu potomnego. Konfiguracja nie jest instalowana na komputerze Windows ani w innych aplikacjach; nowe sesje Codexa odczytają globalny wpis. Lista narzędzi bieżącego czatu nie jest automatycznie przeładowywana.

**Potwierdzony blokujący problem dostawcy (2026-10-18):** żądanie inicjalizacji klienta aplikacji otrzymało HTTP 403 z Cloudflare **1010 / browser_signature_banned**, `owner_action_required=true`. Usługa odrzuca połączenie klienta aplikacji z tej chmury. Zalecany klient Node mcp-remote, z domyślną tożsamością i obsługą proxy, również nie zakończył inicjalizacji w limicie 35 sekund; nie potwierdzono jego dostępu. Nie potwierdzono ważności klucza i nie pobrano katalogu ani strategii. Zapisany wpis MCP nie oznacza działającego dostępu. Znany błąd zapisano w `~/.codex/trader-dev/access-status.json`; aplikacja i mostek nie ponawiają automatycznie połączeń. Dostęp musi dopuścić właściciel trader.dev; nie obchodzimy blokady przez zmianę tożsamości klienta.

Po uzyskaniu potwierdzenia od właściciela usługi, że dostęp odblokowano, usuń **wyłącznie** `access-status.json`, uruchom ponownie lokalny serwer/Codexa i kliknij **Sprawdź połączenie MCP**. Zachowaj `api-key`. Błąd 1010 nie ustala, czy klucz API jest poprawny. Skrypt odtworzenia globalnego wpisu to `python tools/configure_mcp.py` (wymaga Codex CLI, Node, npx i uprawnień do jego aktywnej konfiguracji). Pyta o klucz w ukrytym polu, ewentualnie czyta `TRADER_DEV_API_KEY`; nie wpisuj sekretu do plików projektu. W zarządzanej chmurze aktywna konfiguracja może wymagać wykonania `codex mcp add` z przyznanym uprawnieniem zapisu. Nie zmieniaj zmiennej platformowej CODEX_HOME.

Aplikacyjny klient MCP czyta `TRADER_DEV_API_KEY` lub prywatny plik powyżej. Brak klucza na innym komputerze jest pokazywany jako brak konfiguracji; sekretu nie przenosimy ZIP-em. API `/api/mcp/status` ujawnia tylko status/bezpieczne metadane, nigdy klucz. Po udanym połączeniu wyświetla tylko narzędzia badawcze dotyczące strategii, bez narzędzi zleceń, usuwania, wdrożeń lub danych uwierzytelniających. Można wywołać wybrane narzędzie z argumentami JSON i zapisać odpowiedź jako **niezweryfikowany materiał źródłowy**. Zewnętrzny tekst jest wyświetlany jako tekst, nie instrukcje/kod.

**Laboratorium wykonuje wyłącznie lokalnie zaimplementowane zestawy Inwestapp. Nie uruchamia pobranych skryptów Pine/Pythona i nie potwierdza zgodności ich reguł ani deklarowanych zysków.** Inna strategia z rynku wymaga osobnego przepisania i walidacji. MCP jest opcjonalne: jego blokada nie zatrzymuje bota papierowego i testów lokalnych. Do aplikacji Python nie dodano zależności; Node/npx są potrzebne tylko do globalnego mostka Codexa.

## Aktualizacja 1.4 — nowe narzędzia i instrumenty

**BTC/USD (Bitcoin)** i **ETH/USD (Ethereum)** działają w analizie, wszystkich 6 interwałach, bieżących cenach Coinbase Exchange, alertach, wiadomościach, dzienniku i wpisanych prognozach. Razem aplikacja obsługuje 7 instrumentów. Serie historyczne z Yahoo to `BTC-USD` i `ETH-USD`; mogą różnić się od cen giełdy Coinbase i wykresu TradingView. Wiek dopuszczalny cen do alertów krypto pozostaje 120 s, również dla nowych par.

W **Gotowym zestawie** wybierz **Trend — EMA 21/89/200 + B-Xtrender**. Zaznaczy to nowe narzędzia oraz ADX, OBV i Bollinger. Możesz też osobno zaznaczyć je w **Własnym doborze**. Dotychczasowe ustawienia przeglądarki zostają zachowane; nowy zestaw nie włącza się automatycznie. Dotychczasowe EMA20/50/200, RSI14 i pozostałe narzędzia zachowują obliczenia.

**EMA 21 / 89 / 200 — M1 / M2 / M3:** konfiguracja wskazana przez użytkownika według EMA en 1 Indicador (Jesús Mercado). M1 = EMA21 zielona; M2 = EMA89 biała z ciemnym obrysem dla jasnego wykresu; M3 = EMA200 czerwona. Źródło to `close`, okresy oznaczają liczbę świec wybranego interwału. Nowe średnie mają inicjalizację pierwszą ceną i α = 2/(okres+1), a nie nasiono SMA stosowane w starym zestawie. Pierwsze wartości mogą różnić się od TradingView, jeśli zaczynamy od innego miejsca historii. Wymagamy 200 świec rozgrzewki. W grupie trendu: wzrost `cena > M1 > M2 > M3`; spadek `cena < M1 < M2 < M3`; pozostałe układy są neutralne. Odtwarzamy wskazane okresy i kolory standardowych EMA; oryginalny kod Mercado nie był dostępny do porównania.

**B-Xtrender — QuantTherapy:** lokalna adaptacja formuł z publicznej kopii Pine **Backtest Edition**, zgodnej nazwą z [linkiem użytkownika](https://wild.pynesys.io/scripts/b-xtrender-backtest-edition-quanttherapy-uCWPAPT2). Zweryfikowana [kopia kodu z przypisaniem autorstwa i MPL 2.0](https://github.com/hasnocool/tradingview-pine-scripts/blob/69969aeaf271b2f7b5a7632a1bde43069a0cbe26/B-Xtrender%20%5BBacktest%20Edition%5D%20%40QuantTherapy.pine). Bez połączenia z kontem TradingView lub instalowania Pine.

- Krótkie momentum: `RSI15(EMA5(close) − EMA20(close)) − 50`.
- Długi trend: `RSI15(EMA20(close)) − 50`.
- RSI ma nasiono ze średniej pierwszych 15 zmian i wygładzanie Wildera; przy braku strat przyjmuje 100, także dla płaskiej serii. Brakujące wartości przed rozgrzewką nie są zastępowane zerami.
- Na wykresie: wąskie słupki krótkie, szerokie jasne długie. Powyżej 0 zielone, poniżej 0 czerwone; jaśniejszy kolor oznacza wzrost wartości względem poprzedniej świecy. Zero i rozbieżne składowe są neutralne.
- Dodatkowe wygładzenie Tillson T3(5; 0,7) i punkty zwrotne są kontekstem Inwestapp, poza wskazaną Backtest Edition. Niebieska linia jest obliczana z 6 kolejnych EMA i standardowych współczynników T3. Punkty pojawiają się na świecy potwierdzenia zwrotu, nie są cofane w historii i nie uczestniczą w głosowaniu.

B-Xtrender należy do jednej grupy **momentum**. Potwierdza wzrost, gdy obie składowe są dodatnie, i spadek, gdy obie są ujemne. Dołożenie RSI/MACD nie zwiększa liczby grup — wszystkie wybrane narzędzia momentum muszą się zgadzać. Zestaw EMA + B-Xtrender nadal wymaga ADX ≥ 20, potwierdzenia OBV, kontekstu Bollingera i dodatniego ATR ≤ 8% ceny. Nowe wejście kupna nadal podlega blokadzie historycznej. Brak danych albo niekompletny zestaw oznacza czekanie.

**Test strategii ocenia nasze połączenie narzędzi**, z dotychczasowym stopem 2 ATR, celem 3 ATR, kosztami i kolejnym otwarciem. Nie odtwarza strategii Backtest Edition ze stopem procentowym, jej wyjściem przy zmianie jednej składowej ani shortami. Sprzedaj w analizie nadal oznacza wyjście z istniejącej pozycji kupna. Zgodność narzędzi ani dodanie BTC/ETH nie dowodzą zyskowności. Szczegóły autorstwa, źródeł i licencji: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Interwał i zakres widoku

Domyślnie **H1 (1 godzina)**; do wyboru **15 min, 30 min, 1h, 2h, 4h i 24h**. Przycisk **1 dzień / 7 dni / 30 dni / 90 dni / 180 dni** wybiera zakres widocznej historii, a nie długość świecy. Wskaźniki, sygnał i test wykorzystują całą pobraną historię: zwykle do 60 dni M15/M30, 6 miesięcy H1/H2/H4 lub 5 lat D1, z buforem historii przez 60 sekund. Pierwsze 200 świec służy rozgrzewce wszystkich zestawów.

EMA200 na H1 oznacza 200 świec godzinowych; nie 200 dni. Bieżąca nieukończona świeca nie jest używana. Godziny są prezentowane w Europe/Warsaw, a dane i granice zamknięcia są normalizowane do UTC. D1 pomija cały bieżący dzień UTC. H2/H4 są agregowane z zamkniętych H1 w przedziałach UTC (00:00–02:00 itd.). Godziny bez notowań nie są sztucznie uzupełniane; początkowy niepełny przedział jest odrzucany. Starsze dane blokują rekomendacje: dla interwałów śróddziennych większa z wartości: trzy długości świecy lub 3h krypto / 6h surowce; D1 odpowiednio 2 i 4 dni. Przy braku 90/180 dni M15/M30 aplikacja pokazuje dostępny zakres i ostrzeżenie, nie dopisuje świec. Dłuższą historię można zaimportować z CSV. W weekend blokada starych H1 jest spodziewana. System nie zna harmonogramu konkretnego brokera.

## Narzędzia

- EMA20/50/200: dotychczasowa metoda, nasiona SMA i współczynnik 2/(n+1).
- RSI14 i ADX14: dotychczasowe obliczenia Wildera. ADX mierzy siłę, nie kierunek.
- Ichimoku9/26/52: Tenkan, Kijun i chmura przesunięta o 26 świec; Chikou na wykresie to znane zamknięcia przesunięte wstecz. Decyzja porównuje wyłącznie aktualne zamknięcie z zamknięciem sprzed 26 świec. Brak przyszłych wartości w historycznych obliczeniach i brak projekcji chmury poza zakres wykresu.
- Bollinger20/2: SMA20 ± 2 populacyjne odchylenia standardowe.
- Alligator: SMMA mediany (high+low)/2, okresy 13/8/5 i przesunięcia 8/5/3.
- OBV: od 0; wolumen dodawany przy wzroście zamknięcia, odejmowany przy spadku. Przy zerowym/brakującym wolumenie model czeka.
- Stochastic pełny 14/3/3: raw %K14, SMA3 %K, SMA3 %D; zerowy zakres ceny daje 50.
- Fibonacci: automatyczny zakres ekstremów ostatnich 55 świec i ich kolejność. 23,6 / 38,2 / 50 / 61,8 / 78,6%. Przy obu ekstremach w tej samej świecy kierunek jest oznaczony jako nieustalony i poziomy pozostają tylko poglądowym zakresem. Poziom 50% jest tradycyjną korektą, nie ilorazem ciągu Fibonacciego. Uproszczone kotwice mogą zmieniać się wraz z nowymi ekstremami; to kontekst, bez głosu w modelu.
- Parabolic SAR: AF 0,02, krok 0,02, maksimum 0,20, inicjalizacja kierunku i ekstremów z pierwszych 2 świec. Kierunek na wykresie nie zmienia stopa ATR.
- Momentum10: 100 × zamknięcie / zamknięcie sprzed 10 świec; równowaga 100.
- MACD12/26/9: istniejący wskaźnik, dodatkowa opcja.

Nakładki rysujemy na wykresie ceny; B-Xtrender, RSI, Stochastic, OBV, ADX, Momentum i MACD mają oddzielne wykresy. Własny wybór zapisuje się lokalnie w przeglądarce razem z ryzykiem, kosztem i interwałem.

## Gotowe zestawy i reguły

| Zestaw | Narzędzia | Tryb |
| --- | --- | --- |
| Podstawowy | EMA + RSI + ADX + OBV + Bollinger | Trend |
| EMA21/89/200 + B-Xtrender | EMA M1/M2/M3 + B-Xtrender + ADX + OBV + Bollinger | Trend |
| Ichimoku | Ichimoku + Stochastic + ADX + OBV + SAR | Trend |
| Aligator | Alligator + Momentum + ADX + OBV + Fibonacci | Trend |
| Konsolidacja | Bollinger + Stochastic + ADX + OBV | Konsolidacja |

Wskaźniki z tej samej grupy nie dają oddzielnych głosów. Ocena ma **5 grup**, niezależnie od liczby wybranych narzędzi. Wszystkie narzędzia danej grupy muszą potwierdzać warunek; neutralny lub przeciwny odczyt blokuje wejście.

**Kup — rdzeń reguł:**

1. Trend: zgodne wybrane narzędzia trendu. EMA wymaga ceny > EMA200 i EMA20 > EMA50; Ichimoku ceny nad chmurą, Tenkan > Kijun i ceny > zamknięcia sprzed 26 świec; Aligator lips > teeth > jaw; SAR poniżej ceny. W konsolidacji zamiast tego wymagamy low na/pod dolną wstęgą i zamknięcia powyżej niej.
2. Momentum: w trendzie RSI 50–70, Stochastic %K > %D i 50–80, Momentum > 100 lub dodatni histogram MACD — zależnie od wyboru. W konsolidacji RSI 30–50 lub Stochastic %K > %D i %K ≤ 35.
3. Wolumen: OBV > EMA20 OBV i > OBV sprzed 5 świec.
4. Reżim: ADX ≥ 20 w trendzie, ADX < 20 w konsolidacji.
5. Kontekst/ryzyko: dodatni ATR14 ≤ 8% ceny, a wybrany Bollinger w trendzie wymaga ceny od SMA20 do górnej wstęgi. Fibonacci nie dokłada głosu.

**Sprzedaj:** wyjście z istniejącej pozycji kupna. W trendzie wybrane narzędzia trendu i momentum muszą wskazywać spadek. EMA: cena < EMA200 oraz EMA20 < EMA50; Ichimoku: cena pod chmurą, Tenkan < Kijun i cena < zamknięcia sprzed 26 świec; Aligator: lips < teeth < jaw; SAR ponad ceną. RSI < 45; Stochastic %K < %D i %K < 50; Momentum < 100; MACD ujemny. W konsolidacji cena na/powyżej środkowej wstęgi i słabnące momentum: Stochastic %K < %D i ≥ 65 albo RSI ≥ 60. Bez shortów i dokładania do otwartej pozycji.

**Czekaj:** niekompletny zestaw, brak danych/wolumenu, konflikty lub neutralne odczyty, stara historia, demonstracja albo niespełniona blokada historyczna. Tryb własny trendu wymaga narzędzia trendu + momentum + OBV + ADX. Konsolidacja wymaga Bollingera + momentum + OBV + ADX. Usunięcie wymaganej grupy jest dozwolone do oglądania wykresu, ale blokuje rekomendacje.

### Blokada nowych wejść

Dodatkowa heurystyczna blokada bieżącego „kup” wymaga co najmniej 30 zamkniętych transakcji, dodatniego wyniku netto całego testu, profit factor > 1 oraz co najmniej 5 zamkniętych transakcji otwartych w końcowych 30% okresu i dodatniego ich wyniku. „Sprzedaj” nadal może działać. Brak określonego profit factor także blokuje nowe wejście.

To filtr ostrożności, nie dowód przewagi. Końcowe 30% nie jest niezależnym zbiorem walidacyjnym. **Backtest pokazuje rdzeń reguł i nie stosuje tej bramki historycznie** (`backtest.coreRulesOnly=true`). Nie mamy walidacji kroczącej całego mechanizmu. Decyzja zawiera osobno `technicalAction` i końcowe `action`, a `historyGuard` wyjaśnia ograniczenia. Nie należy przedstawiać wyniku testu jako wyniku pełnej strategii z bramką.

## Ryzyko i test

Zlecenie po sygnale na zamknięciu jest realizowane na otwarciu następnej świecy. Stały stop = 2 ATR i cel = 3 ATR, R:R = 1,5 przed kosztami. Budżet ryzyka i dostępny kapitał ograniczają jednostki, bez dźwigni. Koszt w pb jest po obu stronach: 10 pb = 0,1% na stronę. Luka poniżej stopa realizuje wyjście po otwarciu; jeśli stop i cel trafiono w jednej świecy, zakładamy stop pierwszy. Otwarte pozycje są wycenione w kapitale z kosztem wyjścia, ale nie są zamkniętymi transakcjami. „Kup i trzymaj” używa tego samego okresu i kosztów.

Surowce to referencyjne szeregi GC=F, SI=F, CL=F. Test zakłada ułamkową ekspozycję bez dźwigni z mnożnikiem 1 — nie rzeczywiste kontrakty futures ani CFD. Nie obejmuje finansowania, podatków, depozytu, rolowania, harmonogramów brokerów ani płynności. Brak potwierdzonej zyskowności; wyniki historyczne i duża zgodność narzędzi nie gwarantują zysku. Progi są jawne i stałe, bez dopasowania do wyniku aktualnego instrumentu.

## Dane i CSV

Bieżący panel cen pozostaje odrębny od świec i sygnałów. XRP/XLM/BTC/ETH: publiczny Coinbase Exchange ticker (ostatnia transakcja i bid/ask). Surowce: referencyjne metadane Yahoo chart, z możliwym niepodanym opóźnieniem; obserwowano ok. 10 minut. Odczyty co 15/30/60 sekund lub ręcznie nie gwarantują każdego ticka i nie usuwają opóźnienia źródła. Cache cen: 10 sekund. Błąd zachowuje wyłącznie oznaczoną ostatnią znaną cenę. Stare ceny transakcji: ponad 120 sekund krypto lub 600 sekund surowce. Panel zatrzymuje odczyty w demo i CSV. W ukrytej karcie zatrzymuje się, gdy nie ma aktywnych alertów. Aktywne alerty utrzymują odczyty; przeglądarka nadal może ograniczać timery kart w tle.

HTTPS, bez kluczy: `query1.finance.yahoo.com` i `api.exchange.coinbase.com`. TLS jest weryfikowany. Dostawcy mogą limitować żądania. Brak automatycznego podstawiania demo za błąd danych.

CSV: `date,open,high,low,close,volume`, przecinek, kropka dziesiętna, minimum 220 i maksimum 25000 zakończonych świec, do 8 MB. Wybrany instrument i interwał muszą odpowiadać plikowi. Każdy interwał śróddzienny wymaga daty z godziną i strefą, np. `2026-10-13T10:00:00Z`; D1 `2026-10-13`. Daty rosnąco, bez duplikatów; offsety dat śróddziennych normalizujemy do UTC. Import nie jest trwale zapisywany. Zmiana interwału usuwa bieżący import i wczytuje historię wybranego źródła.

## Alerty cenowe

Zakładka **Alerty cenowe**: wybierz instrument, cenę w USD i warunek **≥** albo **≤**. Alert jest jednorazowy: pierwszy poprawny odczyt spełniający warunek wyłącza go i zapisuje zdarzenie. Można go uzbroić ponownie lub usunąć. Warunek to osiągnięcie progu przy odczycie; nie wymaga wcześniejszego przejścia przez próg. Kilka równoczesnych odczytów nie tworzy powtórzeń.

Alerty działają przy otwartej aplikacji, uruchomionym serwerze i trybie live. Ręczne odświeżanie przy aktywnych alertach wymusza odczyt co 15 s. Demo/CSV wstrzymują monitorowanie. Brak alertów po zamknięciu przeglądarki, podczas uśpienia lub awarii źródła. Krótkie przekroczenie między odczytami może zostać pominięte. Karty w tle mogą mieć opóźnione timery. Dla krypto dopuszczalny wiek ceny wynosi 120 s; dla opóźnionych cen referencyjnych surowców 1200 s (nie są ceną wykonania zlecenia). Zdarzenie zawiera dostawcę i czas notowania.

Komunikat pojawia się w aplikacji. Przycisk **Włącz powiadomienia i dźwięk** uruchamia dźwięk i prosi o pozwolenie systemu; odmowa nie blokuje komunikatów w aplikacji. Zgoda/dźwięk wymagają ponownego kliknięcia po przeładowaniu.

## Wiadomości

Kanały publiczne: [CoinDesk](https://www.coindesk.com/arc/outboundfeeds/rss/), [Cointelegraph](https://cointelegraph.com/rss), [EIA](https://www.eia.gov/rss/todayinenergy.xml) i [Google News](https://news.google.com/) z wynikami różnych wydawców. Wybierz instrument, aby pobrać pasujące tytuły, krótkie fragmenty RSS, daty i linki. Nie pobieramy pełnych artykułów ani materiałów za paywallem. Lista jest deduplikowana według tytułu. Cache 15 min; nieudane źródło ponawiane najwcześniej po minucie. Otwarta zakładka odświeża się co 15 min, można też kliknąć odświeżanie. RSS może blokować dostęp, zmienić adres lub zwrócić pustą listę; aplikacja pokazuje status każdego źródła. Po awarii zachowuje wyraźnie oznaczony starszy odczyt, bez wymyślania publikacji.

Analiza to **słownikowe tagi tytułów**: słowa o wzroście/spadku, regulacje, makro, podaż/popyt, technologia/adopcja oraz oznaczenia komentarzy analitycznych. Nie jest to analiza całych artykułów ani weryfikacja faktów. Nagłówek o rosnącej podaży nie musi oznaczać wzrostu ceny. Podsumowanie liczy wyłącznie datowane publikacje z ostatnich 72 h z działających źródeł. Nie zmienia sygnału technicznego i nie dostarcza liczbowych prognoz analityków.

## Dziennik transakcji i pomiar pozycji

Wpisz instrument, long/short, ilość, mnożnik kontraktu, cenę i datę wejścia oraz **łączne koszty w USD** (prowizje, finansowanie i inne). Stop i cel są opcjonalne: formularz oblicza planowaną stratę, zysk i stosunek zysku do ryzyka po wpisanych kosztach. Luka i poślizg mogą zwiększyć rzeczywistą stratę. Dla XRP/XLM/BTC/ETH mnożnik zwykle 1; futures/CFD wymagają sprawdzenia specyfikacji brokera. Nie ma obliczania depozytu ani automatycznego przeliczania walut.

Aby zamknąć wpis: **Edytuj / zamknij → Stan: Zamknięta → cena i data wyjścia → Zapisz**. Częściowe wyjścia rozdziel na osobne wpisy z odpowiednio podzielonymi kosztami. Wynik netto long = (wyjście − wejście) × ilość × mnożnik − koszty; short odwraca różnicę cen. Procentowy wynik odnosi się do wartości wejściowej ekspozycji plus kosztów, nie do depozytu przy dźwigni. Otwarte pozycje wyceniamy ceną referencyjną; starsze wyceny są oznaczone, brak jakiejkolwiek ceny blokuje pełną sumę otwartych pozycji. Przeglądaj ponownie zakładkę, aby odświeżyć wycenę. Dziennik nie zawiera podatków ani automatycznej synchronizacji z brokerem. Jest oddzielony od symulowanych transakcji w Teście strategii.

## Prognozy analityków — jawna dostępność danych

Dostawcy notowań używani w tej wersji **nie zapewniają spójnego automatycznego konsensusu cen docelowych** dla XRP/XLM/BTC/ETH i surowców. Licznik jest narzędziem dla **ręcznie dodanych, zweryfikowanych przez użytkownika prognoz**. Nie jest automatycznym konsensusem rynku. Nie generujemy prognoz z RSI, tonu wiadomości ani oceny zgodności grup.

Wybierz instrument i horyzont **30/90/180/365 dni od publikacji**, podaj autora, cenę docelową, datę oraz publiczny link https. Sprawdź zgodność jednostki USD, konkretnego instrumentu (dla surowców GC=F, SI=F, CL=F), terminu kontraktu i horyzontu. Formularz wymaga potwierdzenia weryfikacji. Model nie sprawdza automatycznie treści linku. Komentarz dotyczący spółki wydobywczej, ceny spot lub innego kontraktu może nie być porównywalny.

Aktywne są prognozy opublikowane w ostatnich 30 dniach, niewygasłe, dla jednego instrumentu i horyzontu. Najnowszy wpis jednego autora to jeden głos; wcześniejsze i stare wpisy nadal widać w liście. Licznik = (mediana celów / aktualna cena odniesienia − 1) × 100%. Bez celów lub przy starej/brakującej cenie nie wyświetlamy oczekiwanej zmiany. Skala paska to −100% do +100%, dokładna liczba obok nie jest przycinana. To prognozowana zmiana ceny według wybranych źródeł, bez kosztów i bez prawdopodobieństwa realizacji. Ten panel nie wpływa na „kup/sprzedaj/czekaj”.

## Trwałość i kopia danych

SQLite w standardowej bibliotece Pythona; brak instalowania pakietów. **Windows: `%LOCALAPPDATA%\Inwestapp\inwestapp.sqlite3`**. Wklej `%LOCALAPPDATA%\Inwestapp` w pasek Eksploratora plików. Baza jest poza ZIP-em: aktualizacja do nowego folderu zachowa alerty, zdarzenia, transakcje i prognozy. Linux/macOS: `.data/inwestapp.sqlite3` obok serwera. Opcjonalnie ustaw `INWESTAPP_DATA_DIR` na własny folder. Nie uruchamiaj równocześnie kilku wersji.

**Eksport danych JSON** w dzienniku zapisuje czytelną kopię wszystkich tabel. Automatyczny import JSON nie jest dostępny. Aby uzyskać kopię gotową do odtworzenia, zatrzymaj serwer Ctrl+C i skopiuj plik `inwestapp.sqlite3` w bezpieczne miejsce. Odtworzenie: przy zatrzymanym serwerze zachowaj obecną bazę i wstaw kopię pod tę samą ścieżkę. ZIP/Git nie zawierają osobistych wpisów. Ustawienia zestawów pozostają w localStorage przeglądarki.

Serwer domyślnie nasłuchuje tylko na 127.0.0.1. Sprawdza lokalny nagłówek Host i zgodność Origin przy zapisie, wymaga JSON. Nie jest przeznaczony do publicznego hostingu bez logowania i zabezpieczeń.

## Sprawdzenie i API

```sh
python -m unittest discover -s tests -v
node --check web/app.js
node --check web/workspace.js
node --check web/bot.js
node --check tools/trader_mcp_bridge.cjs
```

`GET /api/health` → `version=1.7.2` i `features`. `GET /api/catalog` → narzędzia, zestawy, źródła. `GET /api/analyze?instrument=XRP&timeframe=1h&strategy=trend&tools=ema,rsi,adx,obv,bollinger` (domyślne H1 i zestaw podstawowy). `tools=` oznacza pusty zestaw, bez podstawiania domyślnych. `mode=demo` generuje oznaczone dane syntetyczne i zawsze blokuje rekomendacje transakcyjne. `GET /api/quotes` lub `?instrument=XRP`; HTTP 200 może zawierać błędy poszczególnych źródeł w `quotes[].status`. `POST /api/import`: JSON z `instrument`, `csv`, `timeframe`, `tools`, `strategy`, `capital`, `risk`, `costs`. Błędne parametry zwracają 400, nieudane pobranie historii 502.

Nowe API: `GET/POST /api/alerts`, `POST /api/alerts/{id}/rearm`, `DELETE /api/alerts/{id}`; `GET /api/journal`, `POST /api/trades`, `PUT/DELETE /api/trades/{id}`; `GET /api/news?instrument=XRP`; `GET /api/forecasts?instrument=XRP&horizon=90`, `POST /api/forecasts`, `DELETE /api/forecasts/{id}`; `GET /api/export`. Zapis wymaga obiektu JSON, ceny i wyniki są w USD. `GET /api/quotes` ocenia aktywne alerty i zwraca nowe `alertEvents`.

Weryfikacja wersji 1.5 (2026-10-18): 115 testów jednostkowych/HTTP, w tym następstwo decyzji/ceny, koszty i poślizg obu stron, brak podwójnych transakcji, limit dzienny, stop, zachowanie ochrony po zatrzymaniu, wygaśnięcie zleceń, oddzielenie portfeli testowych, brak wpływu przyszłych cen na początkowy okres, protokół MCP JSON/SSE i usuwanie sekretów z wyjścia mostka. Rzeczywiste porównanie na 4391 świecach H1 BTC z kosztami 10 pb i poślizgiem 5 pb na stronę (1258 świec końcowego testu); żaden z pięciu zestawów nie przeszedł minimalnego filtra badawczego w tym sprawdzeniu. Przeglądarka Chromium: uruchomienie/zatrzymanie i trwałość konfiguracji bota na rzeczywistych danych BTC, porównanie pięciu zestawów na demonstracji, jawny komunikat blokady MCP 1010, brak błędów JS i przewijania poziomego na telefonie. Globalny wpis MCP potwierdzono poleceniem Codex CLI; połączenie z dostawcą pozostaje zablokowane.

Wcześniejsza weryfikacja wersji 1.4 (2026-10-16): 82 testy jednostkowe i HTTP, w tym wzorce liczbowe obliczone niezależnie wzorami zamkniętymi EMA i wygładzania Wildera. Rzeczywiste pobrania BTC/ETH we wszystkich 6 interwałach oraz bieżące ceny wszystkich 7 instrumentów. Chromium: kolory M1/M2/M3, histogramy B-Xtrender, wybór zestawu i jego zachowanie po przeładowaniu, widok mobilny bez przewijania poziomego, alert ETH, zamknięta transakcja BTC z wynikiem po kosztach, wiadomości ETH i podstawa prognozy BTC-USD. Brak błędów JavaScript. Launcher Windows nie był wykonywany natywnie w chmurze.

Wcześniejsza weryfikacja wersji 1.3 (2026-10-15): 69 testów jednostkowych i HTTP, test Chromium dodawania/ponownego uzbrajania alertu, trwałości po przeładowaniu, dziennika (otwarcie → edycja → zamknięcie, wynik netto), eksportu JSON, wpisanych prognoz, wiadomości oraz widoku mobilnego. Rzeczywiste pobrania: wszystkie 6 interwałów XRP, M15/H4 dla pozostałych 4 instrumentów oraz cztery kanały RSS. Testy korzystają z osobnych tymczasowych baz. `Uruchom.bat` nie był wykonywany na Windows w środowisku chmurowym.

API 1.5: `GET /api/bot`, `POST /api/bot/start`, `/api/bot/stop`, `/api/bot/close`; `POST /api/strategies/test` (instrument/timeframe/mode/capital/risk/costs/slippage, opcjonalnie csv); `GET /api/mcp/status`, `POST /api/mcp/research` (tool, arguments), `GET /api/strategies/research`. Bot odrzuca tryb inny niż paper i nie ma endpointu rzeczywistych zleceń. Eksport JSON obejmuje także tabele bota i materiały źródłowe.

## Źródła reguł i ograniczeń

Materiały przeczytane 2026-10-14. Opisują wskaźniki i sens łączenia uzupełniających informacji, nie potwierdzają dochodowości naszego modelu na tych instrumentach. Nasze zestawy i progi to jawne uproszczenia, nie rekomendacje autorów źródeł.

- [StockCharts — Ichimoku](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud): konstrukcja i przesunięcia chmury, trend i momentum.
- [StockCharts — Bollinger](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands): dotknięcie wstęgi samo nie jest sygnałem, w trendzie ceny mogą „iść po wstędze”.
- [StockCharts — OBV](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv): potwierdzanie trendu i innych sygnałów wolumenem.
- [StockCharts — Stochastic](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full): oscylator w kontekście trendu, konsolidacji, wsparcia i oporu.
- [StockCharts — SAR](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/parabolic-sar): częste błędne zwroty w konsolidacji, filtr ADX jako wsparcie oceny trendu.
- [StockCharts — Fibonacci](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements): strefy uwagi wymagają dodatkowego potwierdzenia, 50% nie wynika z ciągu.
- [MetaTrader — Alligator](https://www.metatrader5.com/en/terminal/help/indicators/bw_indicators/alligator): SMMA, mediana ceny i przesunięcia 13/8/5 oraz 8/5/3.
