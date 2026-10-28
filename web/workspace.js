/* Persistent personal workspace; market data and external text never become HTML. */
let alertsState={alerts:[],events:[]},journalState={trades:[]},workspaceRequests={};
const seenEvents=new Set(),openedAt=Date.now();
let audioContext=null,notificationsEnabled=false;
window.hasActiveAlerts=false;
const field=(form,name)=>form.elements.namedItem(name);
const element=(tag,content,cls)=>{const e=document.createElement(tag);if(content!==undefined)e.textContent=content;if(cls)e.className=cls;return e;};
const money=v=>Number.isFinite(v)?'$ '+fmt(v):'Brak wyceny';
const localDate=iso=>{const d=iso?new Date(iso):new Date();return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);};
function formBody(form){return Object.fromEntries(new FormData(form));}
function message(form,value,error=false){const e=form.querySelector('.form-state');e.textContent=value;e.className='form-state wide '+(error?'negative':'positive');}
async function api(path,body,method='POST'){
 const response=await fetch(path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Nie udało się wykonać operacji.');return value;
}
function action(label,fn){const b=element('button',label,'button secondary');b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();}catch(err){window.alert(err.message);}finally{b.disabled=false;}};return b;}
function externalLink(url,label){const a=element('a',label);if(/^https:\/\//.test(url)){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;}
function metric(label,value,detail,cls=''){const a=element('article',undefined,'metric');a.append(element('span',label),element('strong',value,cls),element('small',detail));return a;}
async function submit(form,fn){const button=form.querySelector('[type="submit"]');button.disabled=true;try{await fn();}catch(err){message(form,err.message,true);}finally{button.disabled=false;}}
function assetName(key){return INSTRUMENTS.find(i=>i.id===key)?.name||key;}
for(const select of document.querySelectorAll('.asset-select'))select.replaceChildren(...INSTRUMENTS.map(i=>{const option=element('option',i.name+' · USD');option.value=i.id;return option;}));
for(const select of document.querySelectorAll('.crypto-select')){
 select.replaceChildren(...INSTRUMENTS.filter(i=>i.kind==='crypto').map(i=>{const option=element('option',i.name+' · USDT');option.value=i.id;return option;}));
 select.value='XLM';
}

async function refreshAlerts(){
 const result=await api('/api/alerts');alertsState=result;
 const wasActive=window.hasActiveAlerts;window.hasActiveAlerts=result.alerts.some(a=>a.enabled);
 for(const event of result.events){if(!seenEvents.has(event.id)){seenEvents.add(event.id);if(Date.parse(event.created_at)>=openedAt)showAlert(event);}}
 $('alerts-list').replaceChildren(...result.alerts.map(a=>{
  const card=element('article',undefined,'card entry');const body=element('div');body.append(element('h3',`${assetName(a.instrument)} · ${a.direction==='above'?'≥':'≤'} $ ${quotePrice(a.price,a.instrument)}`),element('p',a.enabled?'Aktywny · czeka na odczyt ceny':`Uruchomiony ${quoteTime(a.triggered_at)}`,'fine'));
  const buttons=element('div',undefined,'entry-actions');if(!a.enabled)buttons.append(action('Uzbrój ponownie',async()=>{await api('/api/alerts/'+a.id+'/rearm',{});await refreshAlerts();startQuotePolling();}));
  buttons.append(action('Usuń',async()=>{await api('/api/alerts/'+a.id,{},'DELETE');await refreshAlerts();}));card.append(body,buttons);return card;
 }));
 if(!result.alerts.length)$('alerts-list').append(element('p','Nie ma jeszcze alertów. Dodaj próg powyżej lub poniżej bieżącej ceny.','empty-state'));
 $('alert-events').replaceChildren(...result.events.slice(0,30).map(e=>element('p',`${assetName(e.instrument)} · odczyt $ ${quotePrice(e.price,e.instrument)} · próg ${e.direction==='above'?'≥':'≤'} $ ${quotePrice(e.threshold,e.instrument)} · ${e.source} · cena z ${quoteTime(e.quote_at)} · alert ${quoteTime(e.created_at)}`,'fine')));
 if(!result.events.length)$('alert-events').append(element('p','Brak uruchomionych alertów.','fine'));
 if(!wasActive&&window.hasActiveAlerts)startQuotePolling();
}
function showAlert(e){
 const title=`${assetName(e.instrument)}: osiągnięto próg ceny`,body=`$ ${quotePrice(e.price,e.instrument)} · ${e.direction==='above'?'≥':'≤'} $ ${quotePrice(e.threshold,e.instrument)} · ${e.source} · cena z ${quoteTime(e.quote_at)}`;
 const toast=element('article',undefined,'card alert-toast');toast.append(element('strong',title),element('p',body),action('Zamknij',()=>toast.remove()));$('alert-toasts').prepend(toast);
 if(notificationsEnabled&&'Notification' in window&&Notification.permission==='granted'){try{new Notification(title,{body,tag:e.id});}catch{}}
 if(audioContext){try{const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.connect(gain);gain.connect(audioContext.destination);gain.gain.value=.08;oscillator.frequency.value=660;oscillator.start();oscillator.stop(audioContext.currentTime+.25);}catch{}}
}
window.onMarketSnapshot=payload=>{
 for(const e of payload.alertEvents||[])if(!seenEvents.has(e.id)){seenEvents.add(e.id);showAlert(e);}
 refreshAlerts().catch(()=>{});
 if(payload.monitorError)text('quote-state',payload.monitorError);
};
$('notification-enable').onclick=async()=>{
 try{const Audio=window.AudioContext||window.webkitAudioContext;if(Audio){audioContext=audioContext||new Audio();await audioContext.resume();}if('Notification' in window){const permission=await Notification.requestPermission();notificationsEnabled=permission==='granted';}text('notification-enable',notificationsEnabled?'Powiadomienia i dźwięk włączone':'Dźwięk włączony · komunikaty w aplikacji');}catch{text('notification-enable','Komunikaty pozostają dostępne w aplikacji');}
};
$('alert-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{await api('/api/alerts',formBody(e.target));message(e.target,'Alert zapisany. Przy spełnionym warunku może uruchomić się już przy najbliższym odczycie.');await refreshAlerts();startQuotePolling();});};

async function loadNews(){
 const id=Symbol();workspaceRequests.news=id;const key=$('news-instrument').value;text('news-state','Pobieranie kanałów RSS…');$('news-refresh').disabled=true;
 try{
  const result=await api('/api/news?instrument='+key);if(workspaceRequests.news!==id)return;
  const s=result.summary;text('news-state',result.notice);
  $('news-summary').replaceChildren(metric('Publikacje z ostatnich 72 h',String(s.recentCount),'Działające źródła z datą publikacji'),metric('Tytuły o wzroście',String(s.positive),'Proste rozpoznawanie słów, nie prognoza','positive'),metric('Tytuły o spadku',String(s.negative),'Nie określa wpływu na cenę','negative'),metric('Neutralne / mieszane',String(s.neutral+s.mixed),'Brak jednoznacznych słów kierunkowych'));
  $('news-sources').replaceChildren(...result.sources.map(source=>{const row=element('div',undefined,'notice'+(source.error?' warning':''));row.append(externalLink(source.url,source.provider),document.createTextNode(' · '+(source.error||'RSS pobrany '+quoteTime(source.fetchedAt))));if(source.stale&&source.fetchedAt)row.append(document.createTextNode(' · zachowano starszy odczyt z '+quoteTime(source.fetchedAt)));return row;}));
  $('news-list').replaceChildren(...result.items.map(item=>{const card=element('article',undefined,'card news-card');const tags=element('div',undefined,'news-tags');tags.append(element('span',item.source,'pill'),element('span',{positive:'Słowa o wzroście',negative:'Słowa o spadku',mixed:'Mieszany tytuł',neutral:'Neutralny tytuł'}[item.tone],'pill'));for(const t of item.themes)tags.append(element('span',t,'pill'));if(item.analystCommentary)tags.append(element('span','Komentarz / prognoza — sprawdź źródło','pill'));const h=element('h3');h.append(externalLink(item.url,item.title));card.append(tags,h,element('p',item.snippet,'fine'),element('small',(item.publishedAt?displayDate(item.publishedAt):'Źródło nie podało daty')+(item.staleSource?' · starszy odczyt RSS':'')));return card;}));
  if(!result.items.length)$('news-list').append(element('p','Brak dostępnych publikacji dla tego instrumentu. Sprawdź status źródeł lub spróbuj później.','empty-state'));
 }catch(err){if(workspaceRequests.news===id)text('news-state',err.message);}finally{if(workspaceRequests.news===id)$('news-refresh').disabled=false;}
}
$('news-refresh').onclick=loadNews;$('news-instrument').onchange=loadNews;

const tradeForm=$('journal-form');
function tradeState(){const closed=field(tradeForm,'state').value==='closed';for(const key of ['exit_price','exit_at']){field(tradeForm,key).disabled=!closed;field(tradeForm,key).required=closed;}if(closed&&!field(tradeForm,'exit_at').value)field(tradeForm,'exit_at').value=localDate();}
function resetTrade(){tradeForm.reset();field(tradeForm,'id').value='';field(tradeForm,'entry_at').value=localDate();field(tradeForm,'instrument').value=selected;tradeState();tradePreview();}
function tradePreview(){
 const body=formBody(tradeForm),units=Number(body.quantity)*Number(body.multiplier),entry=Number(body.entry_price),fees=Number(body.fees),sign=body.direction==='short'?-1:1;
 if(!(units>0&&entry>0)){text('trade-preview','Podaj ceny i ilość, żeby zobaczyć plan ryzyka.');return;}
 const risk=body.stop_price?sign*(entry-Number(body.stop_price))*units+fees:null,reward=body.target_price?sign*(Number(body.target_price)-entry)*units-fees:null;
 text('trade-preview',`Ekspozycja: ${money(units*entry)}. ${risk!==null?'Planowana strata do stopa z kosztami: '+money(risk)+'. ':''}${reward!==null?'Planowany zysk do celu po kosztach: '+money(reward)+'. ':''}${risk>0&&reward!==null?'Zysk / ryzyko: '+fmt(reward/risk)+' : 1. ':''}${body.state==='closed'&&body.exit_price?'Wynik netto: '+money((Number(body.exit_price)-entry)*units*sign-fees)+'. ':''}Luki i poślizg mogą zwiększyć stratę.`);
}
tradeForm.addEventListener('input',tradePreview);field(tradeForm,'state').onchange=()=>{tradeState();tradePreview();};$('trade-reset').onclick=resetTrade;
async function loadJournal(){
 text('journal-state','Wczytywanie dziennika i wyceny pozycji otwartych…');
 try{
  const result=await api('/api/journal');journalState=result;const s=result.summary;
  $('journal-summary').replaceChildren(metric('Wynik zamkniętych',money(s.realized),s.closed+' zamkniętych pozycji',s.realized>=0?'positive':'negative'),metric('Wynik otwartych',money(s.unrealized),s.open+' pozycji · wycena referencyjna',s.unrealized===null?'':s.unrealized>=0?'positive':'negative'),metric('Trafność zamkniętych',s.winRate===null?'—':fmt(s.winRate,1)+'%','Odsetek pozycji z dodatnim wynikiem po kosztach'),metric('Wycena',s.missingQuotes?'Niepełna':s.staleQuotes?'Starsze ceny':'Dostępna',`${s.missingQuotes} braków ceny · ${s.staleQuotes} starszych wycen`));
  text('journal-state',s.missingQuotes?'Brakuje aktualnej ceny dla części otwartych pozycji. Suma otwartych nie jest dostępna; znana część: '+money(s.unrealizedKnown)+'.':s.staleQuotes?'Część wycen używa starszych notowań. To wynik orientacyjny.':'Dziennik zapisany lokalnie. Wycena pozycji otwartych pochodzi z ostatniego odczytu, bez potwierdzenia u brokera.');
  $('journal-list').replaceChildren(...result.trades.map(t=>{
   const card=element('article',undefined,'card entry');const body=element('div');body.append(element('h3',`${assetName(t.instrument)} · ${t.direction==='long'?'Kupno':'Short'} · ${t.status==='closed'?'zamknięta':'otwarta'}`),element('p',`${fmt(t.quantity,4)} × ${fmt(t.multiplier,4)} · wejście $ ${price(t.entry_price)}${t.exit_price!==null?' · wyjście $ '+price(t.exit_price):' · wycena '+money(t.mark_price)} · koszty ${money(t.fees)}`,'fine'),element('strong',money(t.pnl)+(t.return_pct!==null?' · '+fmt(t.return_pct)+'%':''),t.pnl===null?'':t.pnl>=0?'positive':'negative'),element('p',`Wejście: ${displayDate(t.entry_at)}${t.exit_at?' · wyjście: '+displayDate(t.exit_at):' · cena z '+quoteTime(t.quote_at)+(t.valuation_stale?' (starsza / brak)':'')}${t.reward_risk!==null?' · plan zysk / ryzyko '+fmt(t.reward_risk)+' : 1':''}`,'fine'));
   if(t.note)body.append(element('p',t.note,'fine'));
   const buttons=element('div',undefined,'entry-actions');buttons.append(action('Edytuj / zamknij',()=>{for(const [key,value]of Object.entries(t)){const f=field(tradeForm,key);if(f)f.value=key.endsWith('_at')&&value?localDate(value):value??'';}field(tradeForm,'state').value=t.status==='closed'?'closed':'open';tradeState();tradePreview();tradeForm.scrollIntoView({behavior:'smooth',block:'start'});message(tradeForm,'Edytujesz wpis. Zmień stan na „Zamknięta”, aby podać cenę i datę wyjścia.');}),action('Usuń',async()=>{if(!confirm('Usunąć ten wpis z dziennika?'))return;await api('/api/trades/'+t.id,{},'DELETE');await loadJournal();}));card.append(body,buttons);return card;
  }));
  if(!result.trades.length)$('journal-list').append(element('p','Nie ma jeszcze transakcji. Dodaj pierwszy wpis powyżej.','empty-state'));
 }catch(err){text('journal-state',err.message);}
}
tradeForm.onsubmit=e=>{e.preventDefault();submit(tradeForm,async()=>{const body=formBody(tradeForm),id=body.id;body.entry_at=new Date(body.entry_at).toISOString();if(body.state==='closed')body.exit_at=new Date(body.exit_at).toISOString();else{body.exit_price=null;body.exit_at=null;}await api('/api/trades'+(id?'/'+id:''),body,id?'PUT':'POST');resetTrade();message(tradeForm,'Transakcja zapisana.');await loadJournal();});};
$('backup').onclick=async()=>{try{const result=await api('/api/export');const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='inwestapp-dane-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){text('journal-state',err.message);}};

async function loadForecasts(){
 const id=Symbol();workspaceRequests.forecast=id;text('forecast-state','Wczytywanie prognoz i ceny odniesienia…');
 try{
  const key=$('forecast-instrument').value,horizon=$('forecast-horizon').value;
  const result=await api('/api/forecasts?'+new URLSearchParams({instrument:key,horizon}));if(workspaceRequests.forecast!==id)return;
  const change=result.expectedChangePct;
  text('forecast-change',change===null?'Brak miarodajnego odczytu':(change>=0?'+':'')+fmt(change,1)+'%');$('forecast-change').className=change===null?'':change>=0?'positive':'negative';
  $('forecast-meter').hidden=change===null;$('forecast-meter').value=Math.max(-100,Math.min(100,change||0));
  text('forecast-detail',`${result.activeCount} aktywnych autorów · horyzont ${horizon} dni · ${result.basisSymbol}. ${result.medianTarget!==null?'Mediana celu: $ '+price(result.medianTarget)+'. ':''}${result.currentPrice!==null?'Cena odniesienia: $ '+price(result.currentPrice)+' z '+quoteTime(result.quoteAt)+'. ':''}${change===null?'Dodaj aktualne prognozy; licznik wymaga również aktualnej ceny.':'Licznik ma skalę od −100% do +100%; dokładna wartość jest wyżej. To prognoza ceny, nie oczekiwany wynik pozycji po kosztach.'}`);
  text('forecast-state',result.notice);
  $('forecasts-list').replaceChildren(...result.entries.map(r=>{const card=element('article',undefined,'card entry');const body=element('div');body.append(element('h3',r.analyst+' · cel $ '+price(r.target_price)),element('p',`${displayDate(r.issued_at)} · ${r.horizon_days} dni · ${r.basis_symbol}`,'fine'),externalLink(r.source_url,'Otwórz źródło'),element('p',r.note,'fine'));card.append(body,action('Usuń',async()=>{await api('/api/forecasts/'+r.id,{},'DELETE');await loadForecasts();}));return card;}));
  if(!result.entries.length)$('forecasts-list').append(element('p','Brak wpisanych prognoz dla tego instrumentu i horyzontu.','empty-state'));
 }catch(err){if(workspaceRequests.forecast===id){text('forecast-state',err.message);text('forecast-change','Brak danych');$('forecast-meter').hidden=true;}}
}
$('forecast-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{const body=formBody(e.target);body.instrument=$('forecast-instrument').value;body.horizon_days=Number($('forecast-horizon').value);body.issued_at=new Date(body.issued_at).toISOString();await api('/api/forecasts',body);message(e.target,'Prognoza zapisana. Mediana uwzględnia najwyżej najnowszy wpis jednego autora, opublikowany w ostatnich 30 dniach.');await loadForecasts();});};
$('forecast-instrument').onchange=loadForecasts;$('forecast-horizon').onchange=loadForecasts;$('forecasts-refresh').onclick=loadForecasts;
window.workspaceTabChanged=next=>{
 if(next==='alerts')refreshAlerts().catch(err=>text('alert-events',err.message));
 if(next==='journal')loadJournal();
 if(next==='news'){$('news-instrument').value=selected;loadNews();}
 if(next==='analysts'){$('forecast-instrument').value=selected;loadForecasts();}
};
resetTrade();field($('forecast-form'),'issued_at').value=localDate();
refreshAlerts().catch(()=>{text('alerts-list','Nie udało się wczytać alertów. Sprawdź połączenie z lokalnym serwerem.');});

setInterval(()=>{if(tab==='news'&&!document.hidden)loadNews();},15*60*1000);
