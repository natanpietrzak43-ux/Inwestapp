const $ = id => document.getElementById(id);
const INSTRUMENTS = [{id:'XRP',name:'XRP',sub:'XRP / USD',icon:'×',class:'xrp'}, {id:'XLM',name:'Stellar',sub:'XLM / USD',icon:'S',class:'xlm'}, {id:'SILVER',name:'Srebro',sub:'Silver futures',icon:'Ag',class:'silver'}, {id:'OIL',name:'Ropa WTI',sub:'WTI futures',icon:'◈',class:'oil'}, {id:'GOLD',name:'Złoto',sub:'Gold futures',icon:'Au',class:'gold'}];
let selected='XRP', data=null, range=7, tab='analysis', importCsv=null, requestId=0, catalog=null;
const fmt=(v,n=2)=>Number.isFinite(v)?v.toLocaleString('pl-PL',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
const price=v=>fmt(v,v>0&&v<.0001?9:v<1?4:v<10?3:2);
const quotePrice=(v,id)=>fmt(v,v>0&&v<.0001?9:id==='XRP'?4:id==='XLM'?6:2);
const labels={BUY:'Kup',SELL:'Sprzedaj',WAIT:'Czekaj'};
function text(id,value){$(id).textContent=value;}
function toolIds(){return Array.from(document.querySelectorAll('#tool-options input:checked'),e=>e.value);}
function settings(){return {capital:Number($('capital').value),risk:Number($('risk').value),costs:Number($('costs').value),timeframe:$('timeframe').value,strategy:$('strategy').value,tools:toolIds()};}
try{const saved=JSON.parse(localStorage.getItem('inwestapp.settings')||'null');if(saved)for(const k of ['capital','risk','costs'])if(Number.isFinite(saved[k]))$(k).value=saved[k];}catch{}
function validSettings(){return ['capital','risk','costs'].every(id=>$(id).reportValidity());}
function renderInstruments(){
 $('instruments').replaceChildren(...INSTRUMENTS.map(i=>{
  const button=document.createElement('button');button.className='instrument'+(selected===i.id?' active':'');button.setAttribute('aria-pressed',selected===i.id);
  button.innerHTML=`<span class="coin ${i.class}">${i.icon}</span><span><strong>${i.name}</strong><small>${i.sub}</small></span><span class="chevron">›</span>`;
  button.onclick=()=>{selected=i.id;importCsv=null;renderInstruments();load();};return button;
 }));
}
function setTab(next){
 tab=next;const extra=['alerts','news','journal','analysts'].includes(next);
 document.querySelectorAll('.tab-panel,.workspace-panel').forEach(e=>e.hidden=e.id!==next);
 $('dashboard').hidden=extra||!data;
 for(const selector of ['.controls','.tools-panel','#notice','#error','#loading','#refresh']){const el=document.querySelector(selector);if(el){if(extra)el.setAttribute('data-workspace-hidden','');else el.removeAttribute('data-workspace-hidden');}}
 document.querySelectorAll('.nav').forEach(e=>{e.classList.toggle('active',e.dataset.tab===next);e.setAttribute('aria-pressed',e.dataset.tab===next);});
 text('breadcrumb',{analysis:'Przegląd rynku',backtest:'Test strategii',method:'Metodologia',alerts:'Alerty cenowe',news:'Wiadomości',journal:'Dziennik transakcji',analysts:'Prognozy analityków'}[next]);
 if(window.workspaceTabChanged)window.workspaceTabChanged(next);
}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{range=Number(b.dataset.range);document.querySelectorAll('[data-range]').forEach(x=>x.classList.toggle('selected',x===b));if(data)drawPrice();});
$('refresh').onclick=()=>load();
$('mode').onchange=()=>{importCsv=null;load();};
for(const key of ['capital','risk','costs'])$(key).onchange=()=>load();
$('file').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>8000000){showError('Plik CSV może mieć maksymalnie 8 MB.');return;}importCsv=await file.text();e.target.value='';load();};
function showError(message){$('error').hidden=false;const p=document.createElement('div');p.textContent=message;const button=document.createElement('button');button.className='button secondary';button.textContent='Obejrzyj demonstrację';button.onclick=()=>{$('mode').value='demo';importCsv=null;load();};$('error').replaceChildren(p,button);}
async function load(){
 startQuotePolling();
 if(!validSettings())return;
 const id=++requestId;data=null;$('dashboard').hidden=true;$('loading').hidden=false;$('error').hidden=true;$('refresh').disabled=true;
 text('notice',importCsv?'Analiza importowanego CSV…':$('mode').value==='demo'?'Tryb demonstracyjny — dane syntetyczne.':'Pobieranie zamkniętych świec wybranego interwału…');
 try{
  const config=settings();try{localStorage.setItem('inwestapp.settings',JSON.stringify(config));}catch{}
  const response=importCsv?await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:selected,csv:importCsv,...config})}):await fetch('/api/analyze?'+new URLSearchParams({instrument:selected,mode:$('mode').value,...config}));
  const result=await response.json();if(id!==requestId)return;if(!response.ok)throw new Error(result.error||'Błąd analizy.');data=result;render();$('dashboard').hidden=false;setTab(tab);
 }catch(err){if(id===requestId){showError(err.message);text('notice','Brak aktualnej analizy. Wybierz demonstrację lub zaimportuj własne dane CSV.');}}
 finally{if(id===requestId){$('loading').hidden=true;$('refresh').disabled=false;}}
}
function render(){
 const bars=data.bars,last=bars.at(-1),prev=bars.at(-2),ind=data.indicators.at(-1),d=data.decision,bt=data.backtest;
 text('history-gate',data.historyGuard.passed?'Test spełnia minimalne kryteria blokady wejścia. Nie potwierdza trwałej przewagi ani przyszłego zysku.':'Nowe wejścia kupna są blokowane: '+data.historyGuard.reasons.join('; ')+'. Sygnały wyjścia nadal działają.');$('history-gate').className=data.historyGuard.passed?'notice':'notice warning';
 $('notice').className='notice'+(data.mode==='demo'||data.stale?' warning':'');
 text('notice',data.mode==='demo'?'DEMONSTRACJA · Wszystkie ceny i wyniki są syntetyczne. Nie służą do decyzji transakcyjnych.':`${data.mode==='csv'?'IMPORT CSV · źródło wskazane przez użytkownika':'YAHOO FINANCE · dane referencyjne'} · Świeca z ${displayDate(data.lastDate)} · ${catalog.timeframes[data.timeframe].short} · USD${data.stale?' · NIEAKTUALNE DANE — sygnały zablokowane':''}`);
 text('price','$ '+price(last.close));const change=(last.close/prev.close-1)*100;text('change',`${change>=0?'+':''}${fmt(change)}% względem poprzedniej sesji`);$('change').className=change>=0?'positive':'negative';
 const trendTools=d.checks.filter(c=>c.group==='trend');const trend=data.strategy==='range'?(ind.adx<20?'Konsolidacja':'Poza reżimem'):trendTools.length&&trendTools.every(c=>c.state==='bull')?'Wzrostowy':trendTools.length&&trendTools.every(c=>c.state==='bear')?'Spadkowy':'Niejednoznaczny';text('trend',trend);$('trend').className=trend==='Wzrostowy'?'positive':trend==='Spadkowy'?'negative':'';text('trend-reference',data.selectedTools.includes('ema')?`EMA200 $ ${price(ind.ema200)}`:`ADX14 ${fmt(ind.adx,1)} · ${data.strategy==='trend'?'trend':'konsolidacja'}`);text('rsi',fmt(ind.rsi,1));text('rsi-label',data.selectedTools.includes('rsi')?(ind.rsi>70?'Powyżej 70':ind.rsi<30?'Poniżej 30':ind.rsi>=50?'Dodatnie momentum':'Słabsze momentum'):'Informacyjnie · poza modelem');text('atr','$ '+price(ind.atr));text('atr-label',fmt(ind.atr/last.close*100)+'% ostatniej ceny');
 text('chart-title',data.instrument.id==='XRP'||data.instrument.id==='XLM'?data.instrument.id+' / USD':data.instrument.name);text('chart-subtitle',data.instrument.description);text('chart-date','Świeca z '+displayDate(data.lastDate));text('chart-interval',`${range} dni widoku · ${catalog.timeframes[data.timeframe].short}`);text('signal-timeframe',catalog.timeframes[data.timeframe].short);
 text('decision-summary',`${labels[d.action].toUpperCase()} · ${d.action==='SELL'?'Sygnał zamknięcia posiadanej pozycji kupna. To nie otwarcie shorta.':d.action==='BUY'?'Grupy potwierdzają wejście; sprawdź wielkość pozycji i koszty u brokera.':'Poczekaj na zgodne warunki. Nie otwieraj pozycji tylko dlatego, że cena się porusza.'} ${d.reason}`);
 text('signal',labels[d.action]);text('reason',d.reason);$('signal-icon').innerHTML=`<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="${{BUY:'M5 17 17 5M7 5h10v10',SELL:'M5 5 17 17M7 17h10V7',WAIT:'M8 5v14M16 5v14'}[d.action]}" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>`;$('signal-icon').className='signal-icon '+d.action.toLowerCase();text('score',`${d.score} / ${d.total}`);$('score-bars').innerHTML=Array.from({length:d.total},(_,i)=>`<i class="${i<d.score?'filled':''}"></i>`).join('');text('demo-model',d.technicalAction!==d.action?`Układ techniczny: ${labels[d.technicalAction]} · decyzja po blokadach: ${labels[d.action]}`:d.modelAction?`Model na tych danych: ${labels[d.modelAction]} · sygnał zablokowany`: '');
 $('group-checks').replaceChildren(...d.groups.map(c=>{const row=document.createElement('div');row.textContent=(c.ok?'✓ ':'– ')+c.name;row.className=c.ok?'positive':'muted';row.title=c.detail;return row;}));text('selected-count',`${data.selectedTools.length} wybranych narzędzi`);
 $('checks').replaceChildren(...d.checks.map(c=>{const row=document.createElement('div');row.className='check'+(c.ok?' pass':'');const mark=document.createElement('span');mark.textContent=c.ok?'✓':c.state==='bear'?'↓':'–';const inner=document.createElement('div'),name=document.createElement('strong'),detail=document.createElement('small');name.textContent=c.name;detail.textContent=`${{bull:'Potwierdzenie',bear:'Spadek / wyjście',neutral:'Neutralnie',missing:'Brak danych'}[c.state]} · ${fmt(c.value,c.id==='obv'?0:3)}. ${c.detail}`;inner.append(name,detail);row.append(mark,inner);return row;}));
 const plan=data.plan;const commodity=data.instrument.kind==='commodity';text('plan-note',commodity?'Surowce: tylko poziomy cenowe. Wielkość zlecenia wymaga mnożnika i warunków brokera.':d.action==='BUY'?'Orientacyjne poziomy dla nowego wejścia.':'Scenariusz poglądowy. Obecny wniosek nie zaleca nowego wejścia.');
 const rows=[['Cena odniesienia','$ '+price(plan.entry)],['Stop loss · 2 × ATR','$ '+price(plan.stop)],['Take profit · 3 × ATR','$ '+price(plan.target)],['Zysk / ryzyko przed kosztami','1,5 : 1'],['Budżet ryzyka','$ '+fmt(plan.riskBudget)]];
 if(!commodity)rows.push(['Maks. liczba jednostek',fmt(plan.units,4)],['Wartość pozycji','$ '+fmt(plan.notional)]);
 $('plan').replaceChildren(...rows.flatMap(([k,v])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;return[dt,dd];}));
 const items=[['Wynik strategii',fmt(bt.returnPct)+'%',`${bt.trades.length} zamkniętych transakcji`,bt.returnPct>=0?'positive':'negative'],['Kup i trzymaj',fmt(bt.benchmarkPct)+'%','Ten sam okres i koszty',''],['Maks. obsunięcie',fmt(bt.maxDrawdown)+'%','Spadek od szczytu kapitału',''],['Trafność transakcji',bt.winRate===null?'Brak transakcji':fmt(bt.winRate,1)+'%',`Profit factor: ${bt.profitFactor===null?'nieokreślony':fmt(bt.profitFactor)}`,'']];
 $('bt-metrics').innerHTML=items.map(([title,value,sub,cls])=>`<article class="metric"><span>${title}</span><strong class="${cls}">${value}</strong><small>${sub}</small></article>`).join('');
 text('backtest-period',displayDate(bt.startDate)+' → '+displayDate(bt.endDate));text('sample-warning',bt.sampleWarning?'Mała próba: mniej niż 30 zamkniętych transakcji. Wynik nie potwierdza przewagi strategii.':'Wynik na danych historycznych. Sprawdź inne okresy i handel próbny przed wdrożeniem.');$('sample-warning').className='notice warning';
 text('holdout',`Końcowe 30% okresu, od ${displayDate(bt.holdoutDate)}: ${bt.holdoutTrades} zamkniętych transakcji otwartych w tym oknie; wynik netto $ ${fmt(bt.holdoutPnl)}. Test ocenia rdzeń wybranych reguł bez historycznego stosowania blokady bieżącego kupna. Ten fragment nie jest niezależną walidacją.${bt.openPosition?' Jedna pozycja pozostaje otwarta i jest wyceniana w krzywej kapitału.':''}`);
 text('trade-count',bt.trades.length+' łącznie');
 $('trades').replaceChildren(...bt.trades.slice().reverse().map(t=>{const tr=document.createElement('tr');[displayDate(t.entryDate),displayDate(t.exitDate),price(t.entry),price(t.exit),fmt(t.pnl),t.reason].forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if(i===4)td.className=t.pnl>=0?'positive':'negative';tr.append(td);});return tr;}));
 if(!bt.trades.length)$('trades').innerHTML='<tr><td colspan="6">Brak zamkniętych transakcji w tym okresie.</td></tr>';
 drawPrice();drawEquity();
}
function svgNode(name,attributes={},content){const el=document.createElementNS('http://www.w3.org/2000/svg',name);for(const[k,v]of Object.entries(attributes))el.setAttribute(k,v);if(content!==undefined)el.textContent=content;return el;}
function chartBase(container,rows,values,bounds=null,ticks=5){
 const width=800,height=280,pad={l:7,r:77,t:17,b:27},plotW=width-pad.l-pad.r,plotH=height-pad.t-pad.b;
 let min=Math.min(...values),max=Math.max(...values),spread=max-min||Math.abs(max)*.01||1;min-=spread*.09;max+=spread*.09;if(bounds){min=bounds[0];max=bounds[1];}
 const x=i=>pad.l+i/(Math.max(1,rows.length-1))*plotW,y=v=>pad.t+(max-v)/(max-min)*plotH;
 const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img'});
 for(let i=0;i<5;i++){const value=min+(max-min)*i/4,yy=y(value);svg.append(svgNode('line',{x1:pad.l,y1:yy,x2:width-pad.r,y2:yy,stroke:'#edf1ee','stroke-dasharray':'3 4'}),svgNode('text',{x:width-pad.r+12,y:yy+4},price(value)));}
 for(let i=0;i<ticks;i++){const index=Math.round((rows.length-1)*i/(ticks-1));svg.append(svgNode('text',{x:x(index),y:height-5,'text-anchor':i===0?'start':i===ticks-1?'end':'middle'},displayDate(rows[index].date,false)));}
 container.replaceChildren(svg);return {svg,x,y,plotW};
}
function line(svg,rows,value,x,y,color,dashed=false){let path='',started=false;rows.forEach((r,i)=>{const v=value(r,i);if(v===null||v===undefined){started=false;return;}path+=`${started?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)} `;started=true;});const node=svgNode('path',{d:path,fill:'none',stroke:color,'stroke-width':'1.7',...(dashed?{'stroke-dasharray':'5 4'}:{})});svg.append(node);return node;}
function displayDate(value,full=true){
 const date=new Date(value);if(!Number.isFinite(date.getTime()))return value;
 const hourly=value.includes('T');return date.toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',day:'2-digit',month:'2-digit',...(full?{year:'numeric'}:{}),...(hourly?{hour:'2-digit',minute:'2-digit'}:{})});
}
function visibleRows(){
 const end=Date.parse(data.bars.at(-1).date)+catalog.timeframes[data.timeframe].seconds*1000,cutoff=end-range*86400000;
 let offset=data.bars.findIndex(b=>Date.parse(b.date)>=cutoff);if(offset<0)offset=data.bars.length-1;
 return{rows:data.bars.slice(offset),inds:data.indicators.slice(offset)};
}
function drawPrice(){
 const available=data.history.availableDays;const limited=available<range-catalog.timeframes[data.timeframe].seconds/86400-1;
 text('coverage-note',`Widok: ostatnie ${range} dni. Dostępna historia: ${displayDate(data.history.first)} → ${displayDate(data.history.last)} (${fmt(available,0)} dni).${limited?' Brakuje części żądanego zakresu; pokazujemy wyłącznie dostępne świece.':''}${['15m','30m'].includes(data.timeframe)?' Yahoo zwykle ogranicza M15/M30 do 60 dni; dla 90/180 dni wybierz H1/H2/H4/D1 lub importuj CSV.':''}`);$('coverage-note').className=limited?'notice warning':'fine';
 const {rows,inds}=visibleRows(),chosen=new Set(data.selectedTools);
 const keys=[];if(chosen.has('ema'))keys.push('ema20','ema50','ema200');if(chosen.has('ichimoku'))keys.push('tenkan','kijun','cloudA','cloudB');if(chosen.has('alligator'))keys.push('alligatorJaw','alligatorTeeth','alligatorLips');if(chosen.has('bollinger'))keys.push('bbUpper','bbLower','bbMid');if(chosen.has('sar'))keys.push('sar');
 const fib=chosen.has('fibonacci')?inds.at(-1).fibonacci:null;
 const values=rows.flatMap((r,i)=>[r.low,r.high,...keys.map(k=>inds[i][k])].filter(Number.isFinite));if(fib)values.push(...Object.values(fib.levels));
 const {svg,x,y,plotW}=chartBase($('price-chart'),rows,values);svg.prepend(svgNode('title',{},`${data.instrument.name}, ${data.timeframe}, ${range} dni historii`));
 const add=(key,color,tool,dashed=false)=>{const path=line(svg,inds,r=>r[key],x,y,color,dashed);path.setAttribute('data-tool',tool);path.setAttribute('data-indicator',key);return path;};
 function fillBand(upper,lower,color,tool){const points=inds.flatMap((r,i)=>Number.isFinite(r[upper])&&Number.isFinite(r[lower])?[i]:[]);if(points.length<2)return;const coordinates=points.map(i=>`${x(i)},${y(inds[i][upper])}`).concat(points.slice().reverse().map(i=>`${x(i)},${y(inds[i][lower])}`));svg.append(svgNode('polygon',{points:coordinates.join(' '),fill:color,'fill-opacity':.08,'data-tool':tool}));}
 if(chosen.has('bollinger'))fillBand('bbUpper','bbLower','#659dab','bollinger');
 if(chosen.has('ichimoku'))for(let i=1;i<inds.length;i++){const a=inds[i-1],b=inds[i];if([a.cloudA,a.cloudB,b.cloudA,b.cloudB].every(Number.isFinite))svg.append(svgNode('polygon',{points:`${x(i-1)},${y(a.cloudA)} ${x(i)},${y(b.cloudA)} ${x(i)},${y(b.cloudB)} ${x(i-1)},${y(a.cloudB)}`,fill:b.cloudA>=b.cloudB?'#63a985':'#c78077','fill-opacity':.16,'data-tool':'ichimoku'}));}
 const w=Math.max(.8,Math.min(12,plotW/rows.length*.58));
 rows.forEach((r,i)=>{const color=r.close>=r.open?'#4d9e88':'#c58b80';const g=svgNode('g',{'data-candle':r.date});g.append(svgNode('title',{},`${displayDate(r.date)} · O ${price(r.open)} · H ${price(r.high)} · L ${price(r.low)} · C ${price(r.close)}`),svgNode('line',{x1:x(i),x2:x(i),y1:y(r.high),y2:y(r.low),stroke:color,'stroke-width':.8}),svgNode('rect',{x:x(i)-w/2,y:Math.min(y(r.open),y(r.close)),width:w,height:Math.max(1,Math.abs(y(r.open)-y(r.close))),fill:color}));svg.append(g);});
 if(chosen.has('ema')){add('ema20','#748fae','ema');add('ema50','#cfac6b','ema');add('ema200','#9473b8','ema').setAttribute('stroke-width','2.3');}
 if(chosen.has('bollinger')){add('bbUpper','#659dab','bollinger');add('bbLower','#659dab','bollinger');add('bbMid','#659dab','bollinger',true);}
 if(chosen.has('alligator')){add('alligatorJaw','#748fae','alligator');add('alligatorTeeth','#c78077','alligator');add('alligatorLips','#4d9e88','alligator');}
 if(chosen.has('ichimoku')){add('tenkan','#cfac6b','ichimoku');add('kijun','#9473b8','ichimoku');add('cloudA','#63a985','ichimoku',true);add('cloudB','#c78077','ichimoku',true);let lag='';rows.forEach((r,i)=>{if(i>=26)lag+=`${i===26?'M':'L'}${x(i-26)},${y(r.close)} `;});svg.append(svgNode('path',{d:lag,fill:'none',stroke:'#92a377','stroke-width':1,'data-tool':'ichimoku'}));}
 if(chosen.has('sar'))inds.forEach((r,i)=>{if(Number.isFinite(r.sar))svg.append(svgNode('circle',{cx:x(i),cy:y(r.sar),r:2,fill:'#b38b58','data-tool':'sar'}));});
 if(fib){const start=Math.max(0,rows.length-55);for(const[ratio,value]of Object.entries(fib.levels)){svg.append(svgNode('line',{x1:x(start),x2:x(rows.length-1),y1:y(value),y2:y(value),stroke:'#a89572','stroke-dasharray':'4 4','stroke-width':1,'data-tool':'fibonacci'}),svgNode('text',{x:x(start)+5,y:y(value)-4},fmt(Number(ratio)*100,1)+'%'));}text('fib-note',`Fibonacci: automatyczne ekstrema ostatnich 55 świec (${displayDate(fib.startDate)} → ${displayDate(fib.endDate)}). Kierunek: ${fib.direction==='up'?'wzrost':fib.direction==='down'?'spadek':'nieustalony'}. Poziomy są kontekstem.`);}
 $('fib-note').hidden=!fib;
 const colors={ema:'#9473b8',ichimoku:'#63a985',alligator:'#748fae',sar:'#b38b58',bollinger:'#659dab',fibonacci:'#a89572'};
 $('chart-legend').replaceChildren(...Array.from(chosen).filter(t=>catalog.tools[t].overlay).map(t=>{const span=document.createElement('span'),dot=document.createElement('i');dot.className='legend-dot';dot.style.background=colors[t];span.append(dot,document.createTextNode(catalog.tools[t].name));return span;}));
 text('chart-interval',`${rows.length} świec · ${range} dni · ${catalog.timeframes[data.timeframe].short}`);drawIndicatorCharts(rows,inds);
}
function drawIndicatorCharts(rows,inds){
 $('indicator-charts').replaceChildren();
 const specs={rsi:{keys:['rsi'],bounds:[0,100],levels:[30,70]},stochastic:{keys:['stochK','stochD'],bounds:[0,100],levels:[20,80]},adx:{keys:['adx'],bounds:[0,100],levels:[20]},momentum:{keys:['momentum'],levels:[100]},obv:{keys:['obv','obvEma']},macd:{keys:['macd','macdSignal','macdHist'],levels:[0]}};
 for(const tool of data.selectedTools){const spec=specs[tool];if(!spec)continue;const card=document.createElement('article');card.className='card indicator-card';card.dataset.tool=tool;const head=document.createElement('div');head.className='card-head';const title=document.createElement('h2');title.textContent=catalog.tools[tool].name;const value=document.createElement('span');value.className='muted';value.textContent=spec.keys.map(k=>fmt(inds.at(-1)[k],tool==='obv'?0:2)).join(' / ');head.append(title,value);const area=document.createElement('div');area.className='chart oscillator-chart';card.append(head,area);$('indicator-charts').append(card);const values=inds.flatMap(r=>spec.keys.map(k=>r[k]).filter(Number.isFinite));if(!values.length){area.textContent='Brak danych.';continue;}if(spec.levels)values.push(...spec.levels);const {svg,x,y}=chartBase(area,rows,values,spec.bounds||null,3);for(const level of spec.levels||[])svg.append(svgNode('line',{x1:x(0),x2:x(rows.length-1),y1:y(level),y2:y(level),stroke:'#b6c5bc','stroke-dasharray':'4 4'}));spec.keys.forEach((key,i)=>line(svg,inds,r=>r[key],x,y,['#198d74','#b18b60','#879cac'][i],i===1));}
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
 if(document.hidden&&!window.hasActiveAlerts){text('quote-state','Odświeżanie wstrzymane — karta jest nieaktywna.');paintQuoteCards();return;}
 pollQuotes(generation);
}
async function pollQuotes(generation){
 const controller=new AbortController();quoteController=controller;const timeout=setTimeout(()=>controller.abort(),18000);
 text('quote-state','Pobieranie cen ze źródeł…');$('quote-refresh').disabled=true;
 try{
  const response=await fetch('/api/quotes',{signal:controller.signal});const payload=await response.json();if(generation!==quoteGeneration)return;if(!response.ok)throw new Error('Błąd notowań');quoteRows=payload.quotes;if(window.onMarketSnapshot)window.onMarketSnapshot(payload);
  const good=quoteRows.filter(q=>q.status==='ok').length;const interval=Number($('quote-interval').value);text('quote-state',`${good} / 5 źródeł odpowiedziało · ${interval?'kolejny odczyt za '+interval+' s':window.hasActiveAlerts?'alerty: odczyt co 15 s':'odświeżanie ręczne'} · odbiór ${quoteTime(payload.fetchedAt)}`);
 }catch{
  if(generation!==quoteGeneration)return;quoteRows=INSTRUMENTS.map(i=>{const old=quoteRows.find(q=>q.instrument===i.id);return{instrument:i.id,status:'error',error:'Nie udało się pobrać cen. Sprawdź połączenie lub spróbuj później.',lastQuote:old?.status==='ok'?old:old?.lastQuote||null};});text('quote-state','Błąd pobierania · ostatnie znane ceny oznaczono jako nieaktualne.');
 }finally{
  clearTimeout(timeout);if(generation===quoteGeneration){quoteController=null;$('quote-refresh').disabled=false;paintQuoteCards();const interval=Number($('quote-interval').value);if((interval>0||window.hasActiveAlerts)&&(!document.hidden||window.hasActiveAlerts))quoteTimer=setTimeout(()=>pollQuotes(generation),(interval||15)*1000);}
 }
}
$('quote-refresh').onclick=startQuotePolling;
$('quote-interval').onchange=()=>{try{localStorage.setItem('inwestapp.quoteInterval',$('quote-interval').value);}catch{}startQuotePolling();};
document.addEventListener('visibilitychange',startQuotePolling);
setInterval(paintQuoteCards,1000);
initialize();
function choosePreset(name){const p=catalog.presets[name];if(!p)return;document.querySelectorAll('#tool-options input').forEach(e=>e.checked=p.tools.includes(e.value));$('preset').value=name;$('strategy').value=p.strategy;load();}
async function initialize(){
 createQuoteCards();renderInstruments();
 try{
  const response=await fetch('/api/catalog');if(!response.ok)throw Error('Brak katalogu narzędzi. Upewnij się, że uruchomiona jest wersja 1.3 z nowego folderu.');catalog=await response.json();
  let saved={};try{const value=JSON.parse(localStorage.getItem('inwestapp.settings')||'{}');saved=value&&typeof value==='object'?value:{};}catch{}
  const chosen=Array.isArray(saved.tools)?saved.tools.filter(t=>catalog.tools[t]):catalog.presets.balanced.tools;
  if(['trend','range'].includes(saved.strategy))$('strategy').value=saved.strategy;if(catalog.timeframes[saved.timeframe])$('timeframe').value=saved.timeframe;
  if(Array.isArray(saved.tools))$('preset').value='custom';
  const names={trend:'Trend',momentum:'Momentum',volume:'Wolumen',regime:'Reżim',context:'Kontekst'};
  $('tool-options').replaceChildren(...Object.entries(catalog.tools).map(([id,tool])=>{const label=document.createElement('label');label.className='tool-option';const input=document.createElement('input');input.type='checkbox';input.value=id;input.id='tool-'+id;input.checked=chosen.includes(id);const body=document.createElement('span'),title=document.createElement('strong'),group=document.createElement('small');title.textContent=tool.name;group.textContent=names[tool.group];body.append(title,group);label.append(input,body);label.title=tool.description;input.onchange=()=>{$('preset').value='custom';load();};return label;}));
  $('preset').onchange=()=>{if($('preset').value!=='custom')choosePreset($('preset').value);};$('reset-tools').onclick=()=>choosePreset('balanced');$('strategy').onchange=()=>{$('preset').value='custom';load();};$('timeframe').onchange=()=>{importCsv=null;load();};
  $('source-links').replaceChildren(...catalog.sources.map(s=>{const a=document.createElement('a');a.href=s.url;a.textContent=s.name;a.target='_blank';a.rel='noopener noreferrer';return a;}));load();
 }catch(err){$('loading').hidden=true;showError(err.message);startQuotePolling();}
}
