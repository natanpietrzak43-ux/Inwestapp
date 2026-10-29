/* CoinGecko is market context only; never modifies chart sources or bot state. */
let cgBusy=false,cgLast=null,cgGeneration=0,cgFailed=false;
const priorCoinGeckoTab=window.workspaceTabChanged;
window.workspaceTabChanged=next=>{priorCoinGeckoTab?.(next);if(next==='coingecko')loadCoinGecko();};
const cgMoney=v=>Number.isFinite(v)?'$ '+fmt(v,Math.abs(v)<1?6:2):'—';
const cgPercent=v=>Number.isFinite(v)?fmt(v,2)+'%':'—';
function cgBudget(value){text('coingecko-budget',`${value.monthUTC} UTC · żądania aplikacji ${value.requests} / lokalny budżet ${value.budget} · pozostało ${value.remaining}. ${value.notice}`);}
function cgSection(label,section){return `${label}: ${section.status==='error'?'BŁĄD · '+section.error:section.stale?'STARSZE DANE':'odczyt dostępny'}${section.fetchedAt?' · pobrano '+quoteTime(section.fetchedAt):''}${section.cached?' · bufor':''}`;}
async function loadCoinGecko(){
 if(cgBusy)return;cgBusy=true;const generation=++cgGeneration;$('coingecko-refresh').disabled=true;
 text('coingecko-state','Sprawdzanie konfiguracji CoinGecko…');
 try{
  const status=await api('/api/coingecko/status');cgBudget(status.usage);
  if(!status.configured){
   cgFailed=true;paintCoinGeckoFreshness();
   text('coingecko-state',status.error||'Brak klucza CoinGecko Demo. Uruchom Konfiguruj-CoinGecko.bat, wpisz klucz lokalnie i wróć tutaj. Wtyczka w czacie nie przekazuje klucza aplikacji.');
   $('coingecko-auto').checked=false;return;
  }
  text('coingecko-state','Pobieranie zbiorczego rynku CoinGecko…');
  const result=await api('/api/coingecko/overview');if(generation!==cgGeneration)return;
  cgLast=result;cgFailed=false;$('coingecko-rows').classList.remove('quote-stale');cgBudget(result.usage);text('coingecko-notice',result.notice);
  const sections=result.sections,market=sections.markets;
  const good=(market.data||[]).filter(r=>r.status==='ok'&&!r.stale).length;
  text('coingecko-state',`${good} / 16 świeżych cen · ${cgSection('Ceny',market)}`);
  $('coingecko-rows').replaceChildren(...(market.data||[]).map(row=>{
   const tr=element('tr');tr.classList.toggle('quote-stale',row.stale||row.status==='error');
   const values=row.status==='ok'?[row.name+' · '+row.instrument,cgMoney(row.price),cgPercent(row.change24h),cgPercent(row.change7d),cgPercent(row.change30d),cgMoney(row.marketCap),cgMoney(row.volume24h),cgPercent(row.toAthPct),quoteTime(row.asOf)+(row.stale?' · STARSZA CENA':'')]:[row.name+' · '+row.instrument,'Brak ceny','—','—','—','—','—','—',row.error];
   for(const value of values)tr.append(element('td',value));return tr;
  }));
  if(!(market.data||[]).length){const tr=element('tr'),td=element('td',market.error||'Brak danych.');td.colSpan=9;tr.append(td);$('coingecko-rows').append(tr);}
  const global=sections.global,g=global.data;
  text('coingecko-global-state',cgSection('Szeroki rynek',global)+(g?' · dane z '+quoteTime(g.asOf):''));
  $('coingecko-global').replaceChildren(...(g?[
   metric('Kapitalizacja rynku',cgMoney(g.marketCapUSD),'Zbiorcza wycena w USD'),
   metric('Wolumen 24 h',cgMoney(g.volume24hUSD),'Zgłoszony wolumen, nie głębokość arkusza zleceń'),
   metric('Dominacja BTC',cgPercent(g.btcDominance),'Udział w kapitalizacji CoinGecko'),
   metric('Dominacja ETH',cgPercent(g.ethDominance),'Kontekst rynku, nie sygnał transakcyjny')]:[]));
  $('coingecko-global').classList.toggle('quote-stale',global.stale);
  const trending=sections.trending;text('coingecko-trending-state',cgSection('Popularne wyszukiwania',trending));
  $('coingecko-trending').replaceChildren(...(trending.data||[]).map(row=>{
   const p=element('p');p.append(externalLink('https://www.coingecko.com/en/coins/'+encodeURIComponent(row.id),row.name+' · '+row.symbol));if(row.rank!==null)p.append(document.createTextNode(' · miejsce wg kapitalizacji '+fmt(row.rank,0)));return p;
  }));
  $('coingecko-trending').classList.toggle('quote-stale',trending.stale);
  paintCoinGeckoFreshness();
 }catch(error){cgFailed=true;paintCoinGeckoFreshness();text('coingecko-state',error.message);if(cgLast){text('coingecko-state',error.message+' Poprzedni widok jest nieaktualny.');$('coingecko-rows').classList.add('quote-stale');}}
 finally{cgBusy=false;$('coingecko-refresh').disabled=false;}
}
$('coingecko-refresh').onclick=()=>{$('coingecko-rows').classList.remove('quote-stale');loadCoinGecko();};
$('coingecko-auto').onchange=()=>{if($('coingecko-auto').checked&&tab==='coingecko'&&!document.hidden)loadCoinGecko();};
setInterval(()=>{if($('coingecko-auto').checked&&tab==='coingecko'&&!document.hidden)loadCoinGecko();},60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&tab==='coingecko'&&$('coingecko-auto').checked)loadCoinGecko();});
function paintCoinGeckoFreshness(){
 if(!cgLast)return;const now=Date.now(),sections=cgLast.sections,market=sections.markets;
 let fresh=0;const rows=Array.from($('coingecko-rows').children);
 (market.data||[]).forEach((row,index)=>{
  if(row.status!=='ok')return;
  const stale=cgFailed||row.stale||now-Date.parse(row.asOf)>300000;
  if(!stale)fresh++;const tr=rows[index];if(tr){tr.classList.toggle('quote-stale',stale);tr.lastElementChild.textContent=quoteTime(row.asOf)+(stale?' · STARSZA CENA':'');}
 });
 if(!cgFailed&&!cgBusy)text('coingecko-state',`${fresh} / 16 świeżych cen · ${cgSection('Ceny',market)}`);
 const g=sections.global,globalStale=cgFailed||g.stale||g.data&&now-Date.parse(g.data.asOf)>600000;
 $('coingecko-global').classList.toggle('quote-stale',Boolean(globalStale));
 text('coingecko-global-state',cgSection('Szeroki rynek',{...g,stale:globalStale})+(g.data?' · dane z '+quoteTime(g.data.asOf):''));
 const t=sections.trending,trendingStale=cgFailed||t.stale||t.fetchedAt&&now-Date.parse(t.fetchedAt)>900000;
 $('coingecko-trending').classList.toggle('quote-stale',Boolean(trendingStale));
 text('coingecko-trending-state',cgSection('Popularne wyszukiwania',{...t,stale:trendingStale}));
}
setInterval(()=>{if(tab==='coingecko'&&!document.hidden)paintCoinGeckoFreshness();},1000);
