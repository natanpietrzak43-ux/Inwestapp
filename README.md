# Inwestapp

Prywatny warsztat analizy technicznej dla XRP, XLM, srebra, ropy WTI i złota. Pierwsza wersja: analiza zamkniętych świec dziennych, sygnały kup/sprzedaj/czekaj, plan ryzyka oraz test historyczny. Bez zleceń automatycznych i połączenia z brokerem.

## Uruchomienie

Windows: rozpakuj ZIP do nowego folderu, otwórz folder zawierający `server.py` i dwukrotnie kliknij **Uruchom.bat**. Skrypt uruchomi serwer i otworzy przeglądarkę. Zainstalowany Python 3.10+ jest wymagany. Pozostaw okno terminala otwarte; Ctrl+C zatrzymuje serwer. Aby zaktualizować istniejącą aplikację, najpierw zatrzymaj jej poprzedni serwer, następnie uruchom nową wersję z nowego rozpakowanego folderu. Odśwież stronę Ctrl+F5.

Wymagany Python 3.10 lub nowszy. Brak zewnętrznych zależności.

```sh
cd /workspace/Inwestapp
python server.py --host 127.0.0.1 --port 8000
```

Na swoim komputerze przejdź do adresu lokalnego serwera na porcie 8000. W środowisku onboarding serwer sprawdzamy lokalnymi żądaniami; interfejs onboardingu nie udostępnia podglądu strony. Nie wystawiaj serwera bez uwierzytelniania do Internetu. Ustawienia kapitału, ryzyka i kosztu są przechowywane w pamięci przeglądarki. Dane CSV pozostają tylko w bieżącej sesji. Brak kont, synchronizacji i trwałego portfela.

## Dane

### Bieżące ceny — wersja 1.1

Panel „Bieżące ceny” odczytuje wszystkie pięć instrumentów automatycznie co 15 sekund po zakończeniu poprzedniego odczytu. Można wybrać 30/60 sekund lub odświeżanie ręczne. Ceny są prezentowane w USD, z nazwą źródła, symbolem, czasem notowania i stanem świeżości. Pobrany czas notowania jest odrębny od czasu odbioru (szczegóły po najechaniu na kartę). Godziny w panelu są pokazane w strefie Europe/Warsaw.

- XRP i XLM: publiczny ticker Coinbase Exchange, `https://api.exchange.coinbase.com/products/{XRP-USD|XLM-USD}/ticker`, bez klucza API. Zwraca ostatnią transakcję oraz aktualny bid/ask. To odczyty bieżących danych giełdy, bez subskrypcji WebSocket i bez gwarancji dostarczenia każdego ticka. Źródło różni się od dziennych świec Yahoo Finance; ceny mogą się różnić.
- Złoto, srebro i WTI: metadane `regularMarketPrice` i `regularMarketTime` z publicznego endpointu Yahoo chart (`range=1d&interval=1m`). To ceny referencyjne futures, których opóźnienie może być niepodane. Nie oznaczamy ich jako gwarantowanych notowań w czasie rzeczywistym. Do takich notowań potrzebny jest odpowiedni feed brokera lub licencjonowanego dostawcy. Jeśli źródło podaje `exchangeDataDelayedBy`, interpretujemy je w minutach; częstotliwość odczytu nie zmniejsza opóźnienia dostawcy.
- Backend buforuje odczyty przez 10 sekund i pobiera instrumenty równolegle. Po błędzie zwraca osobny status dla instrumentu i opcjonalnie wyraźnie oznaczoną ostatnią znaną cenę. Brak zastępowania jej ceną syntetyczną. Cena transakcji starsza niż 120 sekund (krypto) lub 600 sekund (surowce) jest oznaczana jako starsza. Poza sesją jest to spodziewane i widoczne w panelu; progi nie gwarantują czasu rzeczywistego.
- Odczyty są wstrzymywane w ukrytej karcie przeglądarki, trybie demo i przy imporcie CSV. Nie zmieniają zamkniętych świec, planu D1, sygnałów ani historycznego testu. Wszystkie te obliczenia nadal używają wyłącznie ukończonych sesji.

Potrzebne domeny HTTPS: `api.exchange.coinbase.com` i `query1.finance.yahoo.com`. TLS pozostaje weryfikowany. Endpoint aplikacji: `GET /api/quotes` lub `GET /api/quotes?instrument=XRP`; status HTTP 200 może zawierać błędy poszczególnych źródeł — należy sprawdzić `quotes[].status`. Wersja aplikacji: `GET /api/health` → `version=1.1.0`.

- Yahoo Finance, publiczny endpoint HTTPS `query1.finance.yahoo.com`: `XRP-USD`, `XLM-USD`, `SI=F`, `CL=F`, `GC=F`. Potrzebny dostęp sieciowy; brak klucza API. Dostawca może ograniczać żądania. Cache w pamięci: 15 minut, do 5 lat danych.
- Tryb demonstracyjny: syntetyczne, deterministyczne dane. Rekomendacje transakcyjne są blokowane i oznaczone jako „Czekaj”. Wyniki testu w tym trybie demonstrują mechanikę i nie świadczą o skuteczności.
- CSV: `date,open,high,low,close,volume`, separator przecinek, daty YYYY-MM-DD rosnąco, kropki dziesiętne. Od 220 do 5000 zakończonych świec; maksymalnie 2 MB. Wszystkie ceny w USD. Należy wybrać właściwy instrument przed importem. Bieżący dzień UTC jest odrzucany. Dane nieaktualne blokują sygnały.

GC=F, SI=F i CL=F są cenami referencyjnymi szeregów futures, a nie ofertami brokera. Test traktuje cenę jako ekspozycję bez dźwigni, z ułamkowymi jednostkami i mnożnikiem 1. Nie symuluje rzeczywistych kontraktów futures ani CFD. Przed ich obsługą trzeba dodać mnożniki, finansowanie, depozyty i rolowanie oraz dane właściwego brokera.

## Strategia

EMA200: pierwsza wartość jest średnią pierwszych 200 zamknięć; kolejne używają współczynnika `2 / 201`. Na wykresie jest fioletową linią, obok EMA20, EMA50 i SMA200. Wersja 1.1 dodaje położenie ceny względem EMA200 do obowiązkowego warunku trendu. Backtest korzysta z identycznej zmienionej reguły, więc wcześniejsze wyniki wersji 1.0 nie są aktualnymi wynikami strategii 1.1.

Wejście wymaga ceny > EMA200 i SMA200, EMA20 > EMA50, ADX14 ≥ 20, RSI14 w zakresie 50–70, dodatniego histogramu MACD12/26/9 oraz ATR14 ≤ 8% ceny. Wolumen ≥ średniej poprzednich 20 sesji jest dodatkowym, opcjonalnym warunkiem; próg wynosi 5 z 6 z pięcioma pozostałymi obowiązkowymi. Wskaźniki są skorelowane, więc wynik 5/6 nie jest prawdopodobieństwem zysku.

Wyjście sygnałowe wymaga ceny < EMA50, RSI < 45 i ujemnego histogramu MACD. „Sprzedaj” oznacza zamknięcie istniejącej pozycji kupna, bez shortów. Dodatkowo stały stop 2 ATR i cel 3 ATR. Plan ceny odniesienia nie jest zleceniem; wykonanie w teście następuje na kolejnym otwarciu i wtedy ustalane są poziomy.

Backtest nie używa przyszłych danych do wskaźników ani sygnałów. Jeśli stop i cel są trafione na jednej świecy, realizuje stop jako pierwszy. Luka poniżej stopa realizuje wyjście po otwarciu. Koszty w pb są pobierane od wejścia i wyjścia. Pozycja nie może przekroczyć kapitału, a liczba jednostek wynika z budżetu ryzyka i kosztów. Otwarte pozycje są wycenione w krzywej kapitału z kosztem wyjścia, ale wykluczone ze statystyk zamkniętych transakcji. Punkt odniesienia „kup i trzymaj” stosuje ten sam okres i koszt obu stron.

Końcowe 30% okresu raportuje zamknięte transakcje, których wejście nastąpiło w tym fragmencie. To raport dodatkowy, nie niezależna walidacja strategii. Parametry są stałe, bez optymalizacji. Mała próba, dane syntetyczne i same wskaźniki nie potwierdzają przewagi. Wyniki historyczne nie gwarantują przyszłych; test pomija podatki, finansowanie, specyfikę brokera i płynność. Nie ma jeszcze dowodu, że strategia przynosi zysk.

## Sprawdzenie

Walidacja danych Yahoo Finance w bieżącym środowisku 2026-10-13 powiodła się dla wszystkich pięciu instrumentów (ostatnia świeca 2026-10-12). Symulacja poprzedniej wersji 1.0 (bez filtra EMA200) na pobranej historii, po 200 sesjach rozgrzewki, przy kapitale 10 000 USD, ryzyku 1% i koszcie 10 pb na stronę: XRP −5,66% (21 transakcji), XLM +4,12% (16), srebro +0,03% (33), ropa −1,44% (11), złoto +6,00% (35). Model nie wykazał zysku na wszystkich instrumentach ani trwałej przewagi; nie jest gotową strategią do bezpośredniego wdrożenia na prawdziwym kapitale. Wyniki surowców są wyłącznie symulacją ekspozycji na ceny referencyjne, bez specyfiki futures/CFD. Aktualne wyniki można odtworzyć w zakładce „Test strategii”; będą się zmieniać wraz z historią dostawcy.

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

Po uruchomieniu serwera: `GET /api/health`, `GET /api/analyze?instrument=XRP&mode=demo`, `GET /api/analyze?instrument=XRP&mode=live`. Błąd dostawcy zwraca 502, bez automatycznego zastępowania danych demonstracją. `POST /api/import` przyjmuje JSON z `instrument`, `csv`, `capital`, `risk`, `costs`. Walidacja wejścia zwraca 400.
