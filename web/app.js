const $ = id => document.getElementById(id);
const INSTRUMENTS = [{id:'XRP',name:'XRP',sub:'XRP / USD',icon:'×',class:'xrp'}, {id:'XLM',name:'Stellar',sub:'XLM / USD',icon:'S',class:'xlm'}, {id:'SILVER',name:'Srebro',sub:'Silver futures',icon:'Ag',class:'silver'}, {id:'OIL',name:'Ropa WTI',sub:'WTI futures',icon:'◈',class:'oil'}, {id:'GOLD',name:'Złoto',sub:'Gold futures',icon:'Au',class:'gold'}];
let selected='XRP', data=null, range=180, tab='analysis', importCsv=null, requestId=0;
const fmt=(v,n=2)=>Number.isFinite(v)?v.toLocaleString('pl-PL',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const price=v=>fmt(v,v<1?4:v<10?3:2);
const quotePrice=(v,id)=>fmt(v,id==='XRP'?4:id==='XLM'?6:2);
const labels={BUY:'Kup',SELL:'Sprzedaj',WAIT:'Czekaj'};
function text(id,value){$(id).textContent=value;}
function settings(){return {capital:Number($('capital').value),risk:Number($('risk').value),costs:Number($('costs').value)};}
try{const saved=JSON.parse(localStorage.getItem('inwestapp.settings')||'null');if(saved)for(const k of ['capital','risk','costs'])if(Number.isFinite(saved[k]))$(k).value=saved[k];}catch{}
function validSettings(){return ['capital','risk','costs'].every(id=>$(id).reportValidity());}
function renderInstruments(){
 $('instruments').replaceChildren(...INSTRUMENTS.map(i=>{
  const button=document.createElement('button');button.className='instrument'+(selected===i.id?' active':'');button.setAttribute('aria-pressed',selected===i.id);
  button.innerHTML=`<span class="coin ${i.class}">${i.icon}</span><span><strong>${i.name}</strong><small>${i.sub}</small></span><span class="chevron">›</span>`;
  button.onclick=()=>{selected=i.id;importCsv=null;renderInstruments();load();};return button;
 }));
}
function setTab(next){tab=next;document.querySelectorAll('.tab-panel').forEach(e=>e.hidden=e.id!==next);document.querySelectorAll('.nav').forEach(e=>{e.classList.toggle('active',e.dataset.tab===next);e.setAttribute('aria-pressed',e.dataset.tab===next);});text('breadcrumb',{analysis:'Przegląd rynku',backtest:'Test strategii',method:'Metodologia'}[next]);}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{range=Number(b.dataset.range);document.querySelectorAll('[data-range]').forEach(x=>x.classList.toggle('selected',x===b));if(data)drawPrice();});
$('refresh').onclick=()=>load();
$('mode').onchange=()=>{importCsv=null;load();};
for(const key of ['capital','risk','costs'])$(key).onchange=()=>load();
$('file').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>2000000){showError('Plik CSV może mieć maksymalnie 2 MB.');return;}importCsv=await file.text();e.target.value='';load();};
function showError(message){$('error').hidden=false;const p=document.createElement('div');p.textContent=message;const button=document.createElement('button');button.className='button secondary';button.textContent='Obejrzyj demonstrację';button.onclick=()=>{$('mode').value='demo';importCsv=null;load();};$('error').replaceChildren(p,button);}
async function load(){
 startQuotePolling();
 if(!validSettings())return;
 const id=++requestId;data=null;$('dashboard').hidden=true;$('loading').hidden=false;$('error').hidden=true;$('refresh').disabled=true;
 text('notice',importCsv?'Analiza importowanego CSV…':$('mode').value==='demo'?'Tryb demonstracyjny — dane syntetyczne.':'Pobieranie zamkniętych świec dziennych…');
 try{
  const config=settings();try{localStorage.setItem('inwestapp.settings',JSON.stringify(config));}catch{}
  const response=importCsv?await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:selected,csv:importCsv,...config})}):await fetch('/api/analyze?'+new URLSearchParams({instrument:selected,mode:$('mode').value,...config}));
  const result=await response.json();if(id!==requestId)return;if(!response.ok)throw new Error(result.error||'Błąd analizy.');data=result;render();$('dashboard').hidden=false;setTab(tab);
 }catch(err){if(id===requestId){showError(err.message);text('notice','Brak aktualnej analizy. Wybierz demonstrację lub zaimportuj własne dane CSV.');}}
 finally{if(id===requestId){$('loading').hidden=true;$('refresh').disabled=false;}}
}
function render(){
 const bars=data.bars,last=bars.at(-1),prev=bars.at(-2),ind=data.indicators.at(-1),d=data.decision,bt=data.backtest;
 $('notice').className='notice'+(data.mode==='demo'||data.stale?' warning':'');
 text('notice',data.mode==='demo'?'DEMONSTRACJA · Wszystkie ceny i wyniki są syntetyczne. Nie służą do decyzji transakcyjnych.':`${data.mode==='csv'?'IMPORT CSV · źródło wskazane przez użytkownika':'YAHOO FINANCE · dane referencyjne'} · Ostatnia świeca: ${data.lastDate} · D1 · USD${data.stale?' · NIEAKTUALNE DANE — sygnały zablokowane':''}`);
 text('price','$ '+price(last.close));const change=(last.close/prev.close-1)*100;text('change',`${change>=0?'+':''}${fmt(change)}% względem poprzedniej sesji`);$('change').className=change>=0?'positive':'negative';
 const trend=last.close>ind.ema200&&last.close>ind.sma200?'Wzrostowy':last.close<ind.ema200&&last.close<ind.sma200?'Spadkowy':'Mieszany';text('trend',trend);$('trend').className=trend==='Wzrostowy'?'positive':trend==='Spadkowy'?'negative':'';text('trend-reference',`EMA200 $ ${price(ind.ema200)} · SMA200 $ ${price(ind.sma200)}`);text('rsi',fmt(ind.rsi,1));text('rsi-label',ind.rsi>70?'Powyżej zakresu wejścia':ind.rsi<30?'Strefa wyprzedania':ind.rsi>=50?'Dodatnie momentum':'Słabsze momentum');text('atr','$ '+price(ind.atr));text('atr-label',fmt(ind.atr/last.close*100)+'% ostatniej ceny');
 text('chart-title',data.instrument.id==='XRP'||data.instrument.id==='XLM'?data.instrument.id+' / USD':data.instrument.name);text('chart-subtitle',data.instrument.description);text('chart-date','Do '+data.lastDate);
 text('signal',labels[d.action]);text('reason',d.reason);$('signal-icon').innerHTML=`<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="${{BUY:'M5 17 17 5M7 5h10v10',SELL:'M5 5 17 17M7 17h10V7',WAIT:'M8 5v14M16 5v14'}[d.action]}" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>`;$('signal-icon').className='signal-icon '+d.action.toLowerCase();text('score',`${d.score} / 6`);$('score-bars').innerHTML=Array.from({length:6},(_,i)=>`<i class="${i<d.score?'filled':''}"></i>`).join('');text('demo-model',d.modelAction?`Model na tych danych: ${labels[d.modelAction]} · sygnał zablokowany`: '');
 $('checks').replaceChildren(...d.checks.map(c=>{const row=document.createElement('div');row.className='check'+(c.ok?' pass':'');const mark=document.createElement('span');mark.textContent=c.ok?'✓':'–';const inner=document.createElement('div'),name=document.createElement('strong'),detail=document.createElement('small');name.textContent=c.name;detail.textContent=c.detail;inner.append(name,detail);row.append(mark,inner);return row;}));
 const plan=data.plan;const commodity=data.instrument.kind==='commodity';text('plan-note',commodity?'Surowce: tylko poziomy cenowe. Wielkość zlecenia wymaga mnożnika i warunków brokera.':d.action==='BUY'?'Orientacyjne poziomy dla nowego wejścia.':'Scenariusz poglądowy. Obecny wniosek nie zaleca nowego wejścia.');
 const rows=[['Cena odniesienia','$ '+price(plan.entry)],['Stop loss · 2 × ATR','$ '+price(plan.stop)],['Take profit · 3 × ATR','$ '+price(plan.target)],['Zysk / ryzyko przed kosztami','1,5 : 1'],['Budżet ryzyka','$ '+fmt(plan.riskBudget)]];
 if(!commodity)rows.push(['Maks. liczba jednostek',fmt(plan.units,4)],['Wartość pozycji','$ '+fmt(plan.notional)]);
 $('plan').replaceChildren(...rows.flatMap(([k,v])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;return[dt,dd];}));
 const items=[['Wynik strategii',fmt(bt.returnPct)+'%',`${bt.trades.length} zamkniętych transakcji`,bt.returnPct>=0?'positive':'negative'],['Kup i trzymaj',fmt(bt.benchmarkPct)+'%','Ten sam okres i koszty',''],['Maks. obsunięcie',fmt(bt.maxDrawdown)+'%','Spadek od szczytu kapitału',''],['Trafność transakcji',bt.winRate===null?'Brak transakcji':fmt(bt.winRate,1)+'%',`Profit factor: ${bt.profitFactor===null?'nieokreślony':fmt(bt.profitFactor)}`,'']];
 $('bt-metrics').innerHTML=items.map(([title,value,sub,cls])=>`<article class="metric"><span>${title}</span><strong class="${cls}">${value}</strong><small>${sub}</small></article>`).join('');
 text('backtest-period',bt.startDate+' → '+bt.endDate);text('sample-warning',bt.sampleWarning?'Mała próba: mniej niż 30 zamkniętych transakcji. Wynik nie potwierdza przewagi strategii.':'Wynik na danych historycznych. Sprawdź inne okresy i handel próbny przed wdrożeniem.');$('sample-warning').className='notice warning';
 text('holdout',`Końcowe 30% okresu, od ${bt.holdoutDate}: ${bt.holdoutTrades} zamkniętych transakcji otwartych w tym oknie; wynik netto $ ${fmt(bt.holdoutPnl)}.${bt.openPosition?' Jedna pozycja pozostaje otwarta i jest wyceniana w krzywej kapitału.':''}`);
 text('trade-count',bt.trades.length+' łącznie');
 $('trades').replaceChildren(...bt.trades.slice().reverse().map(t=>{const tr=document.createElement('tr');[t.entryDate,t.exitDate,price(t.entry),price(t.exit),fmt(t.pnl),t.reason].forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if(i===4)td.className=t.pnl>=0?'positive':'negative';tr.append(td);});return tr;}));
 if(!bt.trades.length)$('trades').innerHTML='<tr><td colspan="6">Brak zamkniętych transakcji w tym okresie.</td></tr>';
 drawPrice();drawEquity();
}
function svgNode(name,attributes={},content){const el=document.createElementNS('http://www.w3.org/2000/svg',name);for(const[k,v]of Object.entries(attributes))el.setAttribute(k,v);if(content!==undefined)el.textContent=content;return el;}
function chartBase(container,rows,values){
 const width=800,height=280,pad={l:7,r:77,t:17,b:27},plotW=width-pad.l-pad.r,plotH=height-pad.t-pad.b;
 let min=Math.min(...values),max=Math.max(...values),spread=max-min||max*.01||1;min-=spread*.09;max+=spread*.09;
 const x=i=>pad.l+i/(Math.max(1,rows.length-1))*plotW,y=v=>pad.t+(max-v)/(max-min)*plotH;
 const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img'});
 for(let i=0;i<5;i++){const value=min+(max-min)*i/4,yy=y(value);svg.append(svgNode('line',{x1:pad.l,y1:yy,x2:width-pad.r,y2:yy,stroke:'#edf1ee','stroke-dasharray':'3 4'}),svgNode('text',{x:width-pad.r+12,y:yy+4},price(value)));}
 for(let i=0;i<5;i++){const index=Math.round((rows.length-1)*i/4);svg.append(svgNode('text',{x:x(index),y:height-5,'text-anchor':i===0?'start':i===4?'end':'middle'},rows[index].date.slice(0,7)));}
 container.replaceChildren(svg);return {svg,x,y,plotW};
}
function line(svg,rows,value,x,y,color,dashed=false){let path='',started=false;rows.forEach((r,i)=>{const v=value(r,i);if(v===null||v===undefined){started=false;return;}path+=`${started?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)} `;started=true;});const node=svgNode('path',{d:path,fill:'none',stroke:color,'stroke-width':'1.7',...(dashed?{'stroke-dasharray':'5 4'}:{})});svg.append(node);return node;}
function drawPrice(){
 const offset=Math.max(0,data.bars.length-range),rows=data.bars.slice(offset),inds=data.indicators.slice(offset);
 const values=rows.flatMap((r,i)=>[r.low,r.high,inds[i].ema20,inds[i].ema50,inds[i].ema200,inds[i].sma200].filter(Number.isFinite));
 const {svg,x,y,plotW}=chartBase($('price-chart'),rows,values);svg.prepend(svgNode('title',{},`${data.instrument.name}, świece dzienne do ${data.lastDate}`));
 const w=Math.max(.8,plotW/rows.length*.58);
 rows.forEach((r,i)=>{const color=r.close>=r.open?'#4d9e88':'#c58b80';const g=svgNode('g');g.append(svgNode('title',{},`${r.date} · otwarcie ${price(r.open)} · high ${price(r.high)} · low ${price(r.low)} · zamknięcie ${price(r.close)}`),svgNode('line',{x1:x(i),x2:x(i),y1:y(r.high),y2:y(r.low),stroke:color,'stroke-width':.8}),svgNode('rect',{x:x(i)-w/2,y:Math.min(y(r.open),y(r.close)),width:w,height:Math.max(1,Math.abs(y(r.open)-y(r.close))),fill:color}));svg.append(g);});
 line(svg,inds,r=>r.ema20,x,y,'#748fae');line(svg,inds,r=>r.ema50,x,y,'#cfac6b');line(svg,inds,r=>r.sma200,x,y,'#afb9b5',true);
 const ema200=line(svg,inds,r=>r.ema200,x,y,'#9473b8');ema200.setAttribute('stroke-width','2.3');ema200.setAttribute('data-indicator','ema200');
}
function drawEquity(){const rows=data.backtest.equity;const {svg,x,y}=chartBase($('equity-chart'),rows,rows.flatMap(r=>[r.value,r.benchmark]));svg.prepend(svgNode('title',{},'Porównanie kapitału strategii i kup i trzymaj'));line(svg,rows,r=>r.benchmark,x,y,'#b0bcb5',true);line(svg,rows,r=>r.value,x,y,'#198d74');}
let quoteTimer=null,quoteController=null,quoteGeneration=0,quoteRows=[];
try{const saved=localStorage.getItem('inwestapp.quoteInterval');if(['0','15','30','60'].includes(saved))$('quote-interval').value=saved;}catch{}
function createQuoteCards(){
 $('quote-cards').replaceChildren(...INSTRUMENTS.map(i=>{const b=document.createElement('button');b.className='quote-card';b.dataset.instrument=i.id;b.innerHTML=`<span class="quote-name">${i.name}<span class="quote-badge">—</span></span><strong class="quote-price">—</strong><span class="quote-spread"></span><span class="quote-provider"></span><span class="quote-time"></span><span class="quote-quality"></span>`;b.onclick=()=>{selected=i.id;importCsv=null;renderInstruments();load();};return b;}));
}
function quoteTime(value){const date=new Date(value);return Number.isFinite(date.getTime())?date.toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})+' · Warszawa':'—';}
function paintQuoteCards(){
 const enabled=$('mode').value==='live'&&!importCsv;
 for(const card of $('quote-cards').children){
  const id=card.dataset.instrument,row=quoteRows.find(q=>q.instrument===id),q=row?.status==='error'?row.lastQuote:row;
  const set=(cls,value)=>card.querySelector('.'+cls).textContent=value;
  card.classList.toggle('selected',id===selected);
  card.setAttribute('aria-pressed',String(id===selected));
  if(!enabled||!q){set('quote-badge',enabled&&row?.status==='error'?'Błąd':enabled?'—':'Pauza');set('quote-price','—');set('quote-spread','');set('quote-provider',enabled?row?.error||'Oczekiwanie na źródło':'Ceny bieżące wstrzymane');set('quote-time','');set('quote-quality','');card.classList.toggle('quote-stale',Boolean(row?.status==='error'));continue;}
  const age=Math.max(0,(Date.now()-Date.parse(q.asOf))/1000),stale=q.stale||row.status==='error'||age>(['XRP','XLM'].includes(id)?120:600);
  set('quote-price','$ '+quotePrice(q.price,id));set('quote-badge',row.status==='error'?'Błąd':stale?'Starsza cena':q.timingType==='exchange'?'Giełda':'Ref.');set('quote-provider',q.provider+' · '+q.sourceSymbol);set('quote-spread',q.bid!==null&&q.ask!==null?`Bid ${quotePrice(q.bid,id)} / Ask ${quotePrice(q.ask,id)}`:'Cena referencyjna futures');set('quote-time','Cena z '+quoteTime(q.asOf));
  const lag=q.timingType==='exchange'?'Ostatnia transakcja giełdowa':q.delaySeconds===null?'Opóźnienie niepotwierdzone':`Opóźnienie wg źródła: ${fmt(q.delaySeconds/60,1)} min`;
  set('quote-quality',row.status==='error'?'Awaria źródła · ostatnia znana cena':(q.marketState==='outside_session'?'Poza sesją źródła · ':stale?'Starsze notowanie · ':'')+lag);card.classList.toggle('quote-stale',stale);card.title=`${q.provider}\nCzas notowania: ${q.asOf}\nOdebrano: ${q.receivedAt}\nWiek: ${Math.round(age)} s${row.status==='error'?'\n'+row.error:''}`;
 }
}
function startQuotePolling(){
 clearTimeout(quoteTimer);if(quoteController)quoteController.abort();$('quote-refresh').disabled=false;const generation=++quoteGeneration;
 if($('mode').value!=='live'||importCsv){quoteRows=[];text('quote-state','Wstrzymane w trybie demonstracyjnym lub przy imporcie CSV.');paintQuoteCards();return;}
 if(document.hidden){text('quote-state','Odświeżanie wstrzymane — karta jest nieaktywna.');paintQuoteCards();return;}
 pollQuotes(generation);
}
async function pollQuotes(generation){
 const controller=new AbortController();quoteController=controller;const timeout=setTimeout(()=>controller.abort(),18000);
 text('quote-state','Pobieranie cen ze źródeł…');$('quote-refresh').disabled=true;
 try{
  const response=await fetch('/api/quotes',{signal:controller.signal});const payload=await response.json();if(generation!==quoteGeneration)return;if(!response.ok)throw new Error('Błąd notowań');quoteRows=payload.quotes;
  const good=quoteRows.filter(q=>q.status==='ok').length;const interval=Number($('quote-interval').value);text('quote-state',`${good} / 5 źródeł odpowiedziało · ${interval?'kolejny odczyt za '+interval+' s':'odświeżanie ręczne'} · odbiór ${quoteTime(payload.fetchedAt)}`);
 }catch{
  if(generation!==quoteGeneration)return;quoteRows=INSTRUMENTS.map(i=>{const old=quoteRows.find(q=>q.instrument===i.id);return{instrument:i.id,status:'error',error:'Nie udało się pobrać cen. Sprawdź połączenie lub spróbuj później.',lastQuote:old?.status==='ok'?old:old?.lastQuote||null};});text('quote-state','Błąd pobierania · ostatnie znane ceny oznaczono jako nieaktualne.');
 }finally{
  clearTimeout(timeout);if(generation===quoteGeneration){quoteController=null;$('quote-refresh').disabled=false;paintQuoteCards();const interval=Number($('quote-interval').value);if(interval>0&&!document.hidden)quoteTimer=setTimeout(()=>pollQuotes(generation),interval*1000);}
 }
}
$('quote-refresh').onclick=startQuotePolling;
$('quote-interval').onchange=()=>{try{localStorage.setItem('inwestapp.quoteInterval',$('quote-interval').value);}catch{}startQuotePolling();};
document.addEventListener('visibilitychange',startQuotePolling);
setInterval(paintQuoteCards,1000);
createQuoteCards();renderInstruments();load();
