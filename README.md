# Inwestapp 1.2

Prywatny warsztat analizy technicznej XRP, XLM, srebra, ropy WTI i złota. Domyślne świece godzinowe H1, wybór narzędzi, cztery gotowe zestawy, plan ryzyka i test historyczny. Brak zleceń automatycznych, kont i połączenia z brokerem.

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

## Interwał i zakres widoku

Domyślnie **H1 (1 godzina)**, opcjonalnie D1 (1 dzień). Przycisk **1 dzień / 7 dni / 30 dni** wybiera zakres widocznej historii, a nie długość świecy. Wskaźniki, sygnał i test wykorzystują całą pobraną historię: do 6 miesięcy H1 lub 5 lat D1, z buforem historii przez 60 sekund. Pierwsze 200 świec służy rozgrzewce wszystkich zestawów.

EMA200 na H1 oznacza 200 świec godzinowych; nie 200 dni. Bieżąca nieukończona świeca nie jest używana. Godziny są prezentowane w Europe/Warsaw, a dane i granice zamknięcia są normalizowane do UTC. D1 pomija cały bieżący dzień UTC. Starsze dane blokują rekomendacje: H1 ponad 3h dla krypto i 6h dla surowców; D1 odpowiednio 2 i 4 dni. W weekend blokada starych H1 jest spodziewana. System nie zna harmonogramu konkretnego brokera.

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

Nakładki rysujemy na wykresie ceny; RSI, Stochastic, OBV, ADX, Momentum i MACD mają oddzielne wykresy. Własny wybór zapisuje się lokalnie w przeglądarce razem z ryzykiem, kosztem i interwałem.

## Gotowe zestawy i reguły

| Zestaw | Narzędzia | Tryb |
| --- | --- | --- |
| Podstawowy | EMA + RSI + ADX + OBV + Bollinger | Trend |
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

Bieżący panel cen pozostaje odrębny od świec i sygnałów. XRP/XLM: publiczny Coinbase Exchange ticker (ostatnia transakcja i bid/ask). Surowce: referencyjne metadane Yahoo chart, z możliwym niepodanym opóźnieniem; obserwowano ok. 10 minut. Odczyty co 15/30/60 sekund lub ręcznie nie gwarantują każdego ticka i nie usuwają opóźnienia źródła. Cache cen: 10 sekund. Błąd zachowuje wyłącznie oznaczoną ostatnią znaną cenę. Stare ceny transakcji: ponad 120 sekund krypto lub 600 sekund surowce. Panel zatrzymuje odczyty w ukrytej karcie, demo i CSV.

HTTPS, bez kluczy: `query1.finance.yahoo.com` i `api.exchange.coinbase.com`. TLS jest weryfikowany. Dostawcy mogą limitować żądania. Brak automatycznego podstawiania demo za błąd danych.

CSV: `date,open,high,low,close,volume`, przecinek, kropka dziesiętna, minimum 220 i maksimum 5000 zakończonych świec, do 2 MB. Wybrany instrument i interwał muszą odpowiadać plikowi. H1 wymaga daty z godziną i strefą, np. `2026-10-13T10:00:00Z`; D1 `2026-10-13`. Daty rosnąco, bez duplikatów; offsety H1 normalizujemy do UTC. Import nie jest trwale zapisywany. Zmiana interwału usuwa bieżący import i wczytuje historię wybranego źródła.

## Sprawdzenie i API

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

`GET /api/health` → `version=1.2.0`. `GET /api/catalog` → narzędzia, zestawy, źródła. `GET /api/analyze?instrument=XRP&timeframe=1h&strategy=trend&tools=ema,rsi,adx,obv,bollinger` (domyślne H1 i zestaw podstawowy). `tools=` oznacza pusty zestaw, bez podstawiania domyślnych. `mode=demo` generuje oznaczone dane syntetyczne i zawsze blokuje rekomendacje transakcyjne. `GET /api/quotes` lub `?instrument=XRP`; HTTP 200 może zawierać błędy poszczególnych źródeł w `quotes[].status`. `POST /api/import`: JSON z `instrument`, `csv`, `timeframe`, `tools`, `strategy`, `capital`, `risk`, `costs`. Błędne parametry zwracają 400, nieudane pobranie historii 502.

## Źródła reguł i ograniczeń

Materiały przeczytane 2026-10-14. Opisują wskaźniki i sens łączenia uzupełniających informacji, nie potwierdzają dochodowości naszego modelu na tych instrumentach. Nasze zestawy i progi to jawne uproszczenia, nie rekomendacje autorów źródeł.

- [StockCharts — Ichimoku](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud): konstrukcja i przesunięcia chmury, trend i momentum.
- [StockCharts — Bollinger](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/bollinger-bands): dotknięcie wstęgi samo nie jest sygnałem, w trendzie ceny mogą „iść po wstędze”.
- [StockCharts — OBV](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv): potwierdzanie trendu i innych sygnałów wolumenem.
- [StockCharts — Stochastic](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full): oscylator w kontekście trendu, konsolidacji, wsparcia i oporu.
- [StockCharts — SAR](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/parabolic-sar): częste błędne zwroty w konsolidacji, filtr ADX jako wsparcie oceny trendu.
- [StockCharts — Fibonacci](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements): strefy uwagi wymagają dodatkowego potwierdzenia, 50% nie wynika z ciągu.
- [MetaTrader — Alligator](https://www.metatrader5.com/en/terminal/help/indicators/bw_indicators/alligator): SMMA, mediana ceny i przesunięcia 13/8/5 oraz 8/5/3.
