# Inwestapp 1.4

Prywatny warsztat analizy technicznej XRP, XLM, BTC/USD, ETH/USD, srebra, ropy WTI i złota. Świece M15/M30/H1/H2/H4/D1, wybór narzędzi, pięć gotowych zestawów, plan ryzyka i test historyczny. Alerty cenowe, wiadomości RSS, dziennik transakcji i licznik wpisanych prognoz. Brak zleceń automatycznych, kont i połączenia z brokerem.

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
```

`GET /api/health` → `version=1.4.0`. `GET /api/catalog` → narzędzia, zestawy, źródła. `GET /api/analyze?instrument=XRP&timeframe=1h&strategy=trend&tools=ema,rsi,adx,obv,bollinger` (domyślne H1 i zestaw podstawowy). `tools=` oznacza pusty zestaw, bez podstawiania domyślnych. `mode=demo` generuje oznaczone dane syntetyczne i zawsze blokuje rekomendacje transakcyjne. `GET /api/quotes` lub `?instrument=XRP`; HTTP 200 może zawierać błędy poszczególnych źródeł w `quotes[].status`. `POST /api/import`: JSON z `instrument`, `csv`, `timeframe`, `tools`, `strategy`, `capital`, `risk`, `costs`. Błędne parametry zwracają 400, nieudane pobranie historii 502.

Nowe API: `GET/POST /api/alerts`, `POST /api/alerts/{id}/rearm`, `DELETE /api/alerts/{id}`; `GET /api/journal`, `POST /api/trades`, `PUT/DELETE /api/trades/{id}`; `GET /api/news?instrument=XRP`; `GET /api/forecasts?instrument=XRP&horizon=90`, `POST /api/forecasts`, `DELETE /api/forecasts/{id}`; `GET /api/export`. Zapis wymaga obiektu JSON, ceny i wyniki są w USD. `GET /api/quotes` ocenia aktywne alerty i zwraca nowe `alertEvents`.

Weryfikacja wersji 1.4 (2026-10-16): 82 testy jednostkowe i HTTP, w tym wzorce liczbowe obliczone niezależnie wzorami zamkniętymi EMA i wygładzania Wildera. Rzeczywiste pobrania BTC/ETH we wszystkich 6 interwałach oraz bieżące ceny wszystkich 7 instrumentów. Chromium: kolory M1/M2/M3, histogramy B-Xtrender, wybór zestawu i jego zachowanie po przeładowaniu, widok mobilny bez przewijania poziomego, alert ETH, zamknięta transakcja BTC z wynikiem po kosztach, wiadomości ETH i podstawa prognozy BTC-USD. Brak błędów JavaScript. Launcher Windows nie był wykonywany natywnie w chmurze.

Wcześniejsza weryfikacja wersji 1.3 (2026-10-15): 69 testów jednostkowych i HTTP, test Chromium dodawania/ponownego uzbrajania alertu, trwałości po przeładowaniu, dziennika (otwarcie → edycja → zamknięcie, wynik netto), eksportu JSON, wpisanych prognoz, wiadomości oraz widoku mobilnego. Rzeczywiste pobrania: wszystkie 6 interwałów XRP, M15/H4 dla pozostałych 4 instrumentów oraz cztery kanały RSS. Testy korzystają z osobnych tymczasowych baz. `Uruchom.bat` nie był wykonywany na Windows w środowisku chmurowym.

## Źródła reguł i ograniczeń

Materiały przeczytane 2026-10-14. Opisują wskaźniki i sens łączenia uzupełniających informacji, nie potwierdzają dochodowości naszego modelu na tych instrumentach. Nasze zestawy i progi to jawne uproszczenia, nie rekomendacje autorów źródeł.

- [StockCharts — Ichimoku](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud): konstrukcja i przesunięcia chmury, trend i momentum.
- [StockCharts — Bollinger](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands): dotknięcie wstęgi samo nie jest sygnałem, w trendzie ceny mogą „iść po wstędze”.
- [StockCharts — OBV](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv): potwierdzanie trendu i innych sygnałów wolumenem.
- [StockCharts — Stochastic](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full): oscylator w kontekście trendu, konsolidacji, wsparcia i oporu.
- [StockCharts — SAR](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/parabolic-sar): częste błędne zwroty w konsolidacji, filtr ADX jako wsparcie oceny trendu.
- [StockCharts — Fibonacci](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements): strefy uwagi wymagają dodatkowego potwierdzenia, 50% nie wynika z ciągu.
- [MetaTrader — Alligator](https://www.metatrader5.com/en/terminal/help/indicators/bw_indicators/alligator): SMMA, mediana ceny i przesunięcia 13/8/5 oraz 8/5/3.
