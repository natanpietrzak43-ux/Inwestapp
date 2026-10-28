# Weryfikacja automatyzacji 2.1

Aktualizacja 28.10.2026: wydanie 2.1.0 dodaje ochronę lokalnego API, CSP, limity i kontrolę zgodności paczki oraz 12 kryptowalut (łącznie 16). Przeszło 236 testów Python/HTTP, 14 testów modelu wykresu i 5 zestawów Chromium: start, wykres, bot, automatyzacja i próby ataków. Przeglądarka potwierdziła zablokowanie obcej strony oraz skryptu inline; złośliwe nagłówki wiadomości pozostały tekstem. Formularz specyfikacji w teście automatyzacji używał kontrolowanej odpowiedzi, nie bieżącego API OKX. Import publicznego źródła Freqtrade w teście bota zakończył się zapisem materiału bez wykonania kodu.

Dzisiejsze publiczne sprawdzenie dostępności nowych par na OKX/Coinbase zatrzymała blokada proxy HTTP403. Katalog nie jest dowodem aktualnego notowania. Brak aktywnych danych/specyfikacji blokuje analizę/wykonanie. Nadal nie wykonano uwierzytelnionych operacji na koncie OKX Demo ani testu Windows/DPAPI/skanowania Defender na komputerze użytkownika. Szczegóły granic ochrony: [SECURITY.md](../SECURITY.md).

Poniżej zachowano dowody i warunki z wdrożenia 2.0; nie oznaczają ponownego sprawdzenia dostawcy na dzień wydania 2.1.

Stan: 24.10.2026. Implementacja w projekcie nie jest potwierdzeniem uruchomienia na Windows użytkownika ani dostępu do jego giełdy.

| Obszar | Zaimplementowano | Sprawdzenie i pozostałe warunki |
| --- | --- | --- |
| Wspólny silnik | Przyczynowe epoki dowodu, wspólne bramki/limity, pełny replay tego samego wykonawcy papierowego, osobna baza/zegar zadania, późniejsze okna i stres kosztów | Testy przyczynowości, zgodności i izolacji; rzeczywista walidacja XLM zakończona blokadą, nie zaliczeniem strategii |
| Zlecenia Demo | Podpis HMAC, nagłówek Demo bez trybu live, trwały zamiar, uzgodnienie po timeout/restart, limity ceny, częściowe wykonania i deduplikacja | Testy protokołu i kontrolowany serwer giełdy. Brak kluczy OKX Demo w chmurze: uwierzytelnione operacje NIEZWERYFIKOWANE |
| Ochrona | SL/TP/OCO po stronie giełdy, potwierdzenie ilości, reduce-only przy braku ochrony, blokada obcych pozycji/zleceń | Testy odmowy ochrony i awarii. Faktyczna akceptacja/nadanie ochrony przez OKX Demo wymaga kluczy i testu integracyjnego |
| Kontrakty | Decimal, ctVal/ctMult, min/lot/tick, MMR tiers, prowizje, historyczne mark i funding | Rzeczywiste publiczne API XLM: 93 progi, 260 mark OHLC i 33 rozliczenia; dodatkowa walidacja 1200 świec, 980 mark i 123 rozliczenia. Aktualne specyfikacje w historii nadal są uproszczeniem |
| Nadzór Windows | Jedna blokada na bazę, restart runner, osobny watchdog, zadania po zalogowaniu, SMTP/HTTPS, kopia i odtwarzanie | Blokady, backup/restore i kanały na kontrolowanych fixture sprawdzone Linux. DPAPI, BAT/PowerShell i zadania Windows wymagają uruchomienia na Windows. Żadnego zadania nie zainstalowano zdalnie |
| Strategie | Wersje, hash kodu z kontrolą zmiany w trakcie pracy, walidacje, ręczne dopuszczenie Demo/odwołanie/30 dni, audyt | Testy odrzucenia złego wyniku, zmiany kodu i cofnięcia. Nie znaleziono i nie zatwierdzono rentownej strategii w tych sprawdzeniach |

## Rzeczywiste dane a testy kontrolowane

Publiczne odczyty specyfikacji/mark/funding zostały wykonane; to nie jest uwierzytelnienie konta. W chmurze nie ma OKX_DEMO_API_KEY, OKX_DEMO_API_SECRET ani OKX_DEMO_PASSPHRASE. Nie wysłano rzeczywistego zlecenia do OKX (nawet Demo) i nie sprawdzono prywatnego WebSocket na koncie. Dotychczasowy blok trader.dev 1010 pozostaje niezależny i nie był obchodzony.

Kontrolowany transport testuje m.in. przyjęte zlecenie z utraconą odpowiedzią, nieprzyjęte zlecenie z timeout, częściowe wykonanie, odrzucenie ochrony, obcą pozycję i obce zlecenie bez client ID. Testy nie dowodzą zachowania zewnętrznej usługi. Nagłówek `x-simulated-trading: 1` jest obowiązkowy w kodzie, prywatny WS ma stały adres wspap OKX. Nie ma ścieżki realnego handlu.

Walidacja rzeczywistego XLM-SWAP H1 na 1200 świecach z 980 świecami mark i 123 rozliczeniami fundingu nie dopuściła modelu: w każdym z trzech okien zero transakcji, ponieważ kroczący filtr wcześniejszych danych blokował wejścia. Wynik zerowy nie jest dowodem skuteczności; niewystarczająca aktywność blokuje zatwierdzenie.

## Uruchomienie i testy

- `python launch.py --check-installation`
- `python -m unittest discover -s tests -q`
- `node --test tests/test_chart.cjs`
- `node --check web/automation.js`
- Opcjonalne Chromium/Playwright: startup_browser.cjs, chart_browser.cjs, bot_browser.cjs, automation_browser.cjs. Każdy uruchamiaj przy osobnym serwerze i tymczasowym INWESTAPP_DATA_DIR, nigdy na osobistej bazie. Bot browser startuje/zatrzymuje własny bot papierowy, automation browser nie wysyła zleceń Demo.
- Dodano workflow GitHub Actions dla Linux/Windows, Python 3.12/3.15; jego dodanie nie oznacza jeszcze zaliczenia zdalnych uruchomień.

Do uruchomienia na komputerze właściciela potrzebne są: cały nowy ZIP, zatrzymanie starej wersji, konfiguracja lokalnych kluczy Demo, oddzielny test konta bez zleceń, walidacja i świadome dopuszczenie strategii, osobny start Demo oraz test kanału alarmowego. Windows musi pozostać włączony i bez uśpienia. Osobny watchdog na tym samym PC nie alarmuje o utracie zasilania całego PC; taki nadzór wymaga zewnętrznego monitora.

Nie deklarujemy gotowości do prawdziwych środków, gwarantowanej ochrony ani zyskowności.

## Wynik sprawdzeń w tej chmurze

- 218 testów Python/HTTP zakończonych powodzeniem na Linux; bez pominiętych testów w tym uruchomieniu.
- 14 testów modelu wykresu zakończonych powodzeniem.
- Wszystkie cztery zestawy Chromium/Playwright zaliczone: startup, wykres, bot/replay, centrum automatyzacji. Zweryfikowano widok mobilny, blokadę startu bez kluczy i dopuszczenia, pobranie specyfikacji oraz rzeczywisty zapis/odczyt raportu i kopii.
- Rzeczywisty drugi serwer na innym porcie przy tej samej bazie zakończył się kodem4 przed uruchomieniem wykonawców. Osobny proces watchdog potwierdził aktualne heartbeat.
- Backup/restore i SMTP są testowane na kontrolowanych danych/transportach. Nie wysyłano rzeczywistego e-maila, nie skonfigurowano SMTP użytkownika i nie wpisywano jego sekretów.
- Pakiet websockets16.0 jest dostępny w tej chmurze; prywatne połączenie z kontem OKX Demo nie zostało uwierzytelnione.
- Serwery walidacyjne używały osobnych katalogów /tmp/inwestapp-v200-ui, /tmp/inwestapp-v200-final i /tmp/inwestapp-v200-release. Bot papierowy walidacyjny pozostawiono zatrzymany i bez pozycji; Demo nie było uruchamiane.

Pliki Windows są przygotowane do lokalnej instalacji, nie zostały natywnie uruchomione w tej chmurze. Zdalny workflow GitHub Actions wymaga osobnego potwierdzenia wyniku; nie zastępujemy go samym faktem zapisania pliku workflow.
