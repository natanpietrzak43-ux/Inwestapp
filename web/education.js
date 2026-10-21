/* Plain-language explanations of the exact local indicators. */
(()=>{
 const lessons={
  ema:['EMA 20 / 50 / 200','Wykładnicze średnie ceny zamknięcia pokazują trend, nadając większą wagę nowszym świecom. Krótsza EMA reaguje szybciej, dłuższa wygładza większą część szumu.',
   'Cena ponad rosnącą EMA200 wskazuje przewagę trendu wzrostowego. EMA20 ponad EMA50 potwierdza szybszy ruch w górę. Przecięcia są opóźnioną informacją o zmianie, a nie pewnym punktem zwrotu.',
   'Okresy oznaczają świece: EMA200 na H1 to 200 godzinowych świec, na D1 — 200 dziennych. W tym zestawie aplikacja wymaga ceny ponad EMA200 i EMA20 ponad EMA50; układ odwrotny wspiera wyjście.',
   'W ruchu bocznym średnie często przecinają się bez trwałego trendu. Łącz je z ADX i potwierdzeniem momentum; EMA i MACD częściowo powielają informację.'],
  ema_mercado:['EMA M1 / M2 / M3 — 21 / 89 / 200','Trzy wykładnicze średnie z ceny zamknięcia opisują szybki, pośredni i długi trend. M1 jest zielona, M2 biała z obrysem, a M3 czerwona.',
   'Uporządkowanie cena > M1 > M2 > M3 oznacza zgodny układ wzrostowy. Cena < M1 < M2 < M3 to układ spadkowy. Splątane średnie wskazują brak zgodnego kierunku.',
   'M1=21, M2=89, M3=200 świec. EMA zaczynają od pierwszej dostępnej ceny, a model czeka na 200 świec rozgrzewki. To wskazana konfiguracja EMA, nie połączenie z oryginalnym skryptem TradingView.',
   'Samo dotknięcie czerwonej lub zielonej linii nie jest sygnałem wejścia. Model wymaga także momentum, wolumenu, właściwego reżimu i kontroli ryzyka.'],
  ichimoku:['Chmura Ichimoku','Ichimoku łączy kierunek trendu, równowagę ceny i obszary możliwego wsparcia/oporu. Tenkan i Kijun są środkami zakresów cen, a Senkou A i B tworzą chmurę.',
   'Cena ponad chmurą i Tenkan ponad Kijun wspierają trend wzrostowy; poniżej chmury i odwrotny układ — spadkowy. Wewnątrz chmury kierunek jest mniej czytelny.',
   'Okresy 9/26/52, chmura przesunięta o 26 świec. Decyzja używa chmury wyznaczonej wcześniej oraz porównania z ceną sprzed 26 świec. Chikou jest rysowana wstecz i nie dostarcza przyszłej informacji do sygnału.',
   'Chmura nie gwarantuje zatrzymania ceny. W konsolidacji pojawiają się fałszywe przebicia; sprawdzaj reżim ADX i momentum.'],
  bollinger:['Wstęgi Bollingera','Linia środkowa to prosta średnia 20 zamknięć, a wstęgi są oddalone o dwa odchylenia standardowe. Ich szerokość opisuje zmienność.',
   'Wąskie wstęgi oznaczają niską zmienność, szerokie — większą. Zwężenie nie wskazuje kierunku kolejnego ruchu. Cena może długo poruszać się wzdłuż górnej wstęgi w silnym trendzie.',
   'W trendzie aplikacja oczekuje zamknięcia między linią środkową i górną. W konsolidacji szuka low poniżej lub na dolnej wstędze i zamknięcia ponad nią, z potwierdzeniem momentum i wolumenu.',
   'Dotknięcie górnej wstęgi nie oznacza automatycznie „sprzedaj”, a dolnej „kup”. Najpierw odróżnij trend od konsolidacji za pomocą ADX.'],
  rsi:['RSI 14','RSI mierzy relację wygładzonych wzrostów i spadków ceny w 14 świecach. Ma skalę 0–100 i opisuje momentum, a nie wartość godziwą aktywa.',
   'Powyżej 70 zwykle mówi się o wykupieniu, poniżej 30 o wyprzedaniu. Poziom 50 rozdziela przewagę wzrostów i spadków. W silnym trendzie RSI może długo pozostawać w skrajnej strefie.',
   'W modelu trendu aplikacja przyjmuje RSI 50–70 jako potwierdzenie wejścia, a poniżej 45 jako osłabienie przy wyjściu. Model konsolidacji ma inne progi: 30–50 dla wejścia i co najmniej 60 dla wyjścia.',
   '„Wyprzedany” nie oznacza, że cena musi wzrosnąć. RSI, Stochastic i MACD należą tu do jednej grupy momentum i nie są trzema niezależnymi głosami.'],
  alligator:['Aligator','Trzy wygładzone średnie mediany (high+low)/2 pomagają rozpoznać trend. Szczęka: 13 świec/przesunięcie 8, zęby: 8/5, wargi: 5/3.',
   'Splątane linie sugerują uśpienie i ruch boczny. Rozchodzące się linie w kolejności wargi > zęby > szczęka wspierają wzrost; odwrotna kolejność wspiera spadek.',
   'Aplikacja używa SMMA i dodatnich przesunięć; dla danej świecy odczytuje wyłącznie już znane wartości. Układ Aligatora odpowiada za grupę trendu.',
   'Przesunięte linie nie przewidują przyszłej ceny. Potwierdzaj trend przez ADX i Momentum; unikaj interpretowania każdego przecięcia jako nowego zlecenia.'],
  obv:['OBV — równowaga wolumenu','Gdy zamknięcie rośnie, OBV dodaje wolumen świecy; gdy spada, odejmuje go. Przy braku zmiany pozostaje bez zmian. Pokazuje, czy wolumen wspiera kierunek ceny.',
   'Rosnący OBV przy rosnącej cenie potwierdza ruch. Rozbieżność kierunku OBV i ceny może sygnalizować słabsze potwierdzenie, ale nie wyznacza terminu zwrotu.',
   'Aplikacja zaczyna OBV od zera. Dla potwierdzenia wzrostu wymaga wartości ponad EMA20 OBV i ponad OBV sprzed pięciu świec. Brak użytecznego wolumenu blokuje potwierdzenie.',
   'Bezwzględne poziomy OBV zależą od początku historii i źródła. To nie bezpośredni pomiar napływu pieniędzy; każda transakcja ma kupującego i sprzedającego.'],
  stochastic:['Oscylator stochastyczny 14 / 3 / 3','Stochastic mierzy położenie zamknięcia względem najwyższej i najniższej ceny z 14 świec. Wygładzone linie %K i %D mają skalę 0–100.',
   '%K ponad %D oznacza poprawę krótkiego momentum. Strefy poniżej 20 i powyżej 80 opisują położenie blisko krańców zakresu, a nie obowiązkowy zwrot ceny.',
   'W trendzie aplikacja wymaga %K > %D oraz %K między 50 i 80. W konsolidacji oczekuje %K > %D i %K ≤ 35, razem z układem dolnej wstęgi Bollingera.',
   'Przecięcia bywają częste i fałszywe. Czytaj je w kontekście trendu lub konsolidacji i nie traktuj jako niezależnego potwierdzenia tego samego sygnału RSI.'],
  fibonacci:['Poziomy korekty Fibonacciego','Poziomy 23,6%, 38,2%, 50%, 61,8% i 78,6% oznaczają części cofnięcia wcześniejszego ruchu. 50% jest tradycyjnym poziomem korekty, nie ilorazem ciągu Fibonacciego.',
   'Poziomy wskazują obszary do obserwacji reakcji ceny. Przykładowo korekta 61,8% oddaje około 61,8% mierzonego ruchu. Sama obecność ceny przy linii niczego nie potwierdza.',
   'Aplikacja automatycznie kotwiczy poziomy na kierunkowych ekstremach ostatnich 55 świec. Nowe ekstrema mogą zmienić poziomy. Fibonacci jest kontekstem i nie daje dodatkowego głosu wejścia.',
   'Wybór początku i końca ruchu istotnie wpływa na wynik. Szukaj potwierdzenia przez cenę, trend i wolumen; nie ustawiaj zlecenia tylko dlatego, że kurs dotknął poziomu.'],
  adx:['ADX 14 — siła trendu','ADX mierzy siłę ruchu kierunkowego. Sam nie wskazuje, czy trend jest wzrostowy, czy spadkowy.',
   'Rosnący ADX sugeruje wzmacnianie trendu w jego aktualnym kierunku. Spadający ADX może oznaczać jego słabnięcie, niekoniecznie odwrócenie. Progi są umownymi filtrami.',
   'Aplikacja używa ADX ≥ 20 dla modeli trendu i ADX < 20 dla konsolidacji. Kierunek odczytuje osobno z EMA, Ichimoku lub Aligatora.',
   'Wysoki ADX występuje także przy silnym spadku. Nie czytaj wzrostu ADX jako polecenia kupna.'],
  sar:['Parabolic SAR','SAR wyznacza punkty pod lub nad ceną i podąża za trendem. W tym modelu przyspieszenie zaczyna od 0,02 i rośnie do 0,20.',
   'Punkty poniżej ceny wspierają kierunek wzrostowy, powyżej — spadkowy. Przeskok strony wskazuje zmianę kierunku według reguł SAR.',
   'SAR należy do grupy trendu i musi zgadzać się z pozostałymi wybranymi narzędziami tej grupy. Stop transakcyjny w aplikacji nadal jest wyznaczany z ATR, niezależnie od punktów SAR.',
   'W ruchu bocznym SAR często zmienia stronę i generuje straty na kolejnych zwrotach. Używaj go z filtrem ADX; punkt SAR nie gwarantuje ceny wyjścia.'],
  momentum:['Momentum 10','Momentum porównuje bieżące zamknięcie z zamknięciem sprzed 10 świec: 100 × cena teraz / cena wcześniej.',
   'Poziom neutralny to 100. Odczyt 103 oznacza cenę o 3% wyższą niż 10 świec temu; 97 — o 3% niższą. Zmiana wartości opisuje dynamikę tego porównania.',
   'Aplikacja traktuje wartość ponad 100 jako potwierdzenie wzrostowego momentum, a poniżej 100 jako spadkowego. Równość daje odczyt neutralny.',
   'To relacja do wybranego punktu historii, nie prognoza przyszłego zwrotu. Łącz z układem trendu, ADX i OBV.'],
  macd:['MACD 12 / 26 / 9','MACD to różnica EMA12 i EMA26; linią sygnałową jest EMA9 MACD. Histogram pokazuje różnicę MACD i linii sygnałowej.',
   'Dodatni histogram oznacza MACD ponad linią sygnałową, ujemny — poniżej. Wzrost histogramu może wskazywać poprawę momentum nawet wtedy, gdy pozostaje on ujemny.',
   'Aplikacja używa dodatniego histogramu jako potwierdzenia wzrostu, a ujemnego przy wyjściu. MACD należy do jednej grupy momentum razem z innymi oscylatorami.',
   'MACD opiera się na EMA, więc częściowo powtarza ich informację i reaguje z opóźnieniem. Nie licz EMA i MACD jako dwóch niezależnych dowodów skuteczności.'],
  bxtrender:['B-Xtrender — lokalna adaptacja QuantTherapy','Krótka składowa: RSI15(EMA5 − EMA20) − 50. Długa: RSI15(EMA20) − 50. To dwa ujęcia momentum wokół poziomu zero.',
   'Obie składowe ponad zerem wspierają wzrost, obie pod zerem — spadek. Rozbieżność lub zero oznaczają brak zgodnego potwierdzenia. Jaśniejszy słupek oznacza wzrost odczytu względem poprzedniego.',
   'Wąskie słupki są krótką składową, szerokie jasne — długą. Niebieska T3 i potwierdzone punkty zwrotne są dodatkowym kontekstem; nie uczestniczą w głosowaniu. To lokalne formuły, nie usługa TradingView.',
   'Punkt zwrotu T3 sam nie jest sygnałem kupna. Reguły ryzyka, stop ATR, grupy i blokada historyczna są regułami Inwestapp, a nie pełną kopią strategii Backtest Edition.'],
  atr:['ATR 14 — zmienność i ryzyko','ATR jest wygładzoną średnią rzeczywistego zakresu świecy. Uwzględnia high–low oraz luki względem poprzedniego zamknięcia. Jest wyrażony w jednostkach ceny.',
   'Większy ATR oznacza większy typowy zakres ruchu. ATR 0,02 przy cenie 1,00 oznacza zakres około 2% ceny, a nie oczekiwany wzrost o 2%.',
   'Aplikacja wyznacza orientacyjny stop 2 × ATR i cel 3 × ATR od ceny wejścia. Rozmiar pozycji ogranicza budżet ryzyka i koszty. Filtr kontekstu wymaga dodatniego ATR nie większego niż 8% ceny.',
   'ATR nie przewiduje kierunku. Stop nie gwarantuje maksymalnej straty: luka, spread, poślizg i przerwa w odczytach mogą ją zwiększyć.']
 };
 function button(id,label=lessons[id]?.[0]){
  const b=document.createElement('button');b.type='button';b.className='tool-help';b.textContent='?';b.dataset.helpTool=id;b.setAttribute('aria-label','Jak czytać: '+label);b.setAttribute('aria-haspopup','dialog');b.title='Wyjaśnienie: '+label;return b;
 }
 document.addEventListener('click',event=>{
  const trigger=event.target.closest('[data-help-tool]');if(!trigger)return;const lesson=lessons[trigger.dataset.helpTool];if(!lesson)return;event.preventDefault();event.stopPropagation();
  const dialog=document.getElementById('tool-help-dialog');document.getElementById('tool-help-title').textContent=lesson[0];const content=document.getElementById('tool-help-content');content.replaceChildren();
  for(const[i,title]of ['Za co odpowiada?','Jak czytać?','Jak działa w Inwestapp?','Na co uważać?'].entries()){const h=document.createElement('h3'),p=document.createElement('p');h.textContent=title;p.textContent=lesson[i+1];content.append(h,p);}
  if(!dialog.open)dialog.showModal();
 });
 document.addEventListener('DOMContentLoaded',()=>{
  const dialog=document.getElementById('tool-help-dialog');document.getElementById('tool-help-close').onclick=()=>dialog.close();
  dialog.addEventListener('click',e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dialog.close();});
 });
 if(typeof window!=='undefined')window.ToolEducation={button,lessons};
})();
