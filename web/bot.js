let botLoaded=false,botConfigLoaded=false,mcpTools=[];
const priorWorkspaceTab=window.workspaceTabChanged;
window.workspaceTabChanged=next=>{priorWorkspaceTab?.(next);if(next==='bot'){loadBotPresets().then(loadBot);loadResearch();loadReplayHistory();loadStrategySources();}};
async function loadBotPresets(){if(botLoaded)return;try{const c=catalog||await api('/api/catalog');document.querySelectorAll('.preset-select').forEach(select=>select.replaceChildren(...Object.entries(c.presets).map(([id,p])=>{const o=element('option',p.name);o.value=id;return o;})));botLoaded=true;}catch(err){text('bot-state',err.message);}}
async function loadBot(){
 try{
  const r=await api('/api/bot'),s=r.state;const unit=s?.config?.currency||'USD';const botMoney=v=>Number.isFinite(v)?fmt(v)+' '+unit:'—';if(s?.config&&!botConfigLoaded){for(const[k,v]of Object.entries(s.config)){const input=field($('bot-form'),k);if(input)input.value=v;}botConfigLoaded=true;}syncBotCurrency();renderAgentCycles(r);$('bot-archives').replaceChildren(...(r.archives||[]).map(a=>element('p',`${a.accountId} · ${a.config.instrument} · ${a.config.currency||'USD'} · wynik zamkniętych ${fmt(a.realized)} · ${a.tradeCount} transakcji. Szczegóły pozostają w eksporcie danych.`,'fine')));text('bot-state',s?`${s.active?'AKTYWNY':'ZATRZYMANY'} · ${s.status} · ostatni cykl ${s.lastHeartbeat?quoteTime(s.lastHeartbeat):'oczekiwanie'}${s.lastDecision?' · '+s.lastDecision.action+': '+s.lastDecision.reason:''}`:'Bot nie był jeszcze uruchamiany. Wybierz instrument i parametry.');
  $('bot-summary').replaceChildren(metric('Kapitał papierowy',s?botMoney(s.equity):'—',s?.position&&!s.valuationFresh?'Brak świeżej wyceny':'Po kosztach likwidacji'),metric('Wynik zamkniętych',botMoney(s?.realized??0),(s?.tradeCount??0)+' transakcji',s?.realized<0?'negative':'positive'),metric('Wynik dnia UTC',s?botMoney(s.dailyPnl):'—',s?.day||'Dzień ustali pierwszy poprawny odczyt'),metric('Pozycja / zlecenie',s?.position?'Otwarta':s?.pending?'Oczekuje':'Brak',s?.config?assetName(s.config.instrument)+' · '+s.config.timeframe:'Brak rzeczywistych zleceń'));
  $('bot-close').disabled=!s?.position;
  text('bot-model-notice',r.notice);
  if(s?.position){const p=s.position;text('bot-position',`${assetName(s.config.instrument)} · ${p.direction||'LONG'}${p.leverage?' · '+p.leverage+'×':''} · wejście ${price(p.entry)} ${unit} · ${fmt(p.units,6)} jednostek bazowych · stop ${price(p.stop)} ${unit} · cel ${price(p.target)} ${unit}${p.margin?' · depozyt '+fmt(p.margin)+' '+unit+' · likwidacja modelowa '+price(p.liquidationPrice):''} · data ${displayDate(p.entry_at)}. Ostatnia wycena: ${s.lastQuote?quoteTime(s.lastQuote.asOf):'brak'}.`);}else text('bot-position',s?.pending?`Oczekuje ${s.pending.side}; wykonanie wymaga nowej, świeżej ceny po decyzji.`:'Nie ma otwartej papierowej pozycji.');
  $('bot-trades').replaceChildren(...r.trades.map(t=>{const tr=element('tr');for(const value of [assetName(t.instrument)+' · '+(t.direction||'LONG')+(t.leverage?' '+t.leverage+'×':''),displayDate(t.entry_at),displayDate(t.exit_at),fmt(t.pnl)+' '+(t.currency||'USD'),t.reason])tr.append(element('td',value));return tr;}));
  if(!r.trades.length){const tr=element('tr');const td=element('td','Brak zamkniętych transakcji papierowych.');td.colSpan=5;tr.append(td);$('bot-trades').append(tr);}
  $('bot-events').replaceChildren(...r.events.map(e=>element('p',`${quoteTime(e.created_at)} · ${e.kind} · ${e.detail}`,'fine')));
 }catch(err){text('bot-state',err.message);}
}
$('bot-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{await api('/api/bot/start',formBody(e.target));message(e.target,'Bot papierowy aktywny. Pierwszy cykl nastąpi w ciągu około 15 s.');await loadBot();});};
$('bot-stop').onclick=async()=>{try{await api('/api/bot/stop',{});await loadBot();}catch(e){text('bot-state',e.message);}};
$('bot-close').onclick=async()=>{try{await api('/api/bot/close',{});await loadBot();}catch(e){text('bot-state',e.message);}};
$('bot-refresh').onclick=loadBot;
$('lab-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{
 const body=formBody(e.target);if(body.mode==='csv'){if(!importCsv)throw Error('Najpierw zaimportuj CSV w Przeglądzie rynku.');body.csv=importCsv;}
 text('lab-state','Trwa porównanie historii i końcowego okresu…');const r=await api('/api/strategies/test',body);text('lab-state',(r.demo?'DEMONSTRACJA — dane syntetyczne. ':'')+`${r.instrument} · ${r.source} · ${r.currency} · ${r.bars} świec · koszt ${r.costs} pb i poślizg ${r.slippage} pb / stronę · końcowy test od ${displayDate(r.splitDate)}. `+r.notice+' To test rdzenia reguł, bez kontroli jakości i limitów konta zespołu agentów.');
 $('lab-results').replaceChildren(...r.rows.map(row=>{const card=element('article',undefined,'card');card.append(element('h3',row.name));const table=element('div',undefined,'metrics');for(const [name,m]of [['Okres początkowy',row.initial],['Końcowe 30%',row.test]])table.append(metric(name,fmt(m.returnPct)+'%',`${m.trades} transakcji · PF ${m.profitFactor===null?'nieokreślony':fmt(m.profitFactor)} · obsunięcie ${fmt(m.maxDrawdown)}%`,m.returnPct>=0?'positive':'negative'));card.append(table,element('p',row.researchFilterPassed?'Przeszedł minimalny filtr badawczy. Nie potwierdza przyszłego zysku.':row.reasons.join(' '),'fine'));return card;}));message(e.target,'Porównanie gotowe. Bot i wybrany zestaw nie zostały zmienione.');
 });};
$('mcp-check').onclick=async()=>{
 $('mcp-check').disabled=true;text('mcp-state','Sprawdzanie protokołu MCP i katalogu narzędzi…');
 try{const r=await api('/api/mcp/status');text('mcp-state',r.connected?`Połączono z trader.dev · ${r.totalTools} narzędzi, ${r.tools.length} badawczych do strategii. ${r.notice}`:r.error);mcpTools=r.tools||[];$('mcp-form').hidden=!r.connected||!mcpTools.length;field($('mcp-form'),'tool').replaceChildren(...mcpTools.map(t=>{const o=element('option',t.name);o.value=t.name;return o;}));showMcpSchema();}catch(err){text('mcp-state',err.message);}finally{$('mcp-check').disabled=false;}
};
function showMcpSchema(){const t=mcpTools.find(t=>t.name===field($('mcp-form'),'tool').value);text('mcp-schema',t?JSON.stringify(t.inputSchema,null,2):'Brak dozwolonych narzędzi badawczych.');}
field($('mcp-form'),'tool').onchange=showMcpSchema;
$('mcp-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{const body=formBody(e.target);body.arguments=JSON.parse(body.arguments);await api('/api/mcp/research',body);message(e.target,'Zapisano materiał z MCP jako niezweryfikowany. Nie uruchomiono pobranego kodu.');await loadResearch();});};
async function loadResearch(){try{const r=await api('/api/strategies/research');$('mcp-records').replaceChildren(...r.records.map(item=>{const card=element('details',undefined,'card bot-details');card.append(element('summary',`${item.tool} · ${item.context?item.context.instrument+' / '+item.context.timeframe+' / '+item.context.market+' · ':''}${quoteTime(item.fetchedAt)} · materiał niezweryfikowany`),element('pre',JSON.stringify(item,null,2)));return card;}));}catch(e){text('mcp-records',e.message);}}
setInterval(()=>{if(tab==='bot'&&!document.hidden)loadBot();},15000);

function syncAssetUnits(form,unit){const select=field(form,'instrument');for(const option of select.options){const asset=INSTRUMENTS.find(i=>i.id===option.value);option.textContent=asset.name+' · '+unit;option.disabled=unit==='USDT'&&asset.kind!=='crypto';}if(select.selectedOptions[0]?.disabled)select.value='XRP';}
function syncBotCurrency(){syncTradingForm($('bot-form'));const unit=field($('bot-form'),'source').value==='okx'?'USDT':'USD';document.querySelectorAll('.bot-currency').forEach(el=>el.textContent=unit);syncAssetUnits($('bot-form'),unit);}
field($('bot-form'),'source').onchange=syncBotCurrency;
function syncLabCurrency(){const unit=field($('lab-form'),'mode').value==='live'&&field($('lab-form'),'source').value==='okx'?'USDT':'USD';text('lab-currency',unit);syncAssetUnits($('lab-form'),unit);}
field($('lab-form'),'source').onchange=syncLabCurrency;field($('lab-form'),'mode').onchange=syncLabCurrency;
function renderAgentCycles(result){
 const cycles=result.cycles||[],cycle=cycles.find(c=>c.id===result.state?.lastCycle);
 const names={passed:'OK',blocked:'BLOKADA',approved:'ZGODA',bull:'WZROST',bear:'SPADEK',neutral:'NEUTRALNIE',received:'POBRANO',BUY:'KUP',SELL:'SPRZEDAJ',LONG:'LONG',SHORT:'SHORT',CLOSE:'ZAMKNIJ',WAIT:'CZEKAJ',skipped:'POMINIĘTO',filled:'WYKONANO',queued:'OCZEKUJE',not_submitted:'BRAK ZLECENIA'};
 const verdict=c=>`${names[c.action]||c.action} · ${c.instrument} / ${c.currency} · ${c.source} · ${c.timeframe} · ${quoteTime(c.created_at)}`;
 text('agent-result',cycle?verdict(cycle)+' · '+cycle.reason:'Brak cyklu bieżącego uruchomienia zespołu agentów.');
 $('agent-flow').replaceChildren();
 if(cycle){
  const stages=[...cycle.stages,{id:'execution',name:'Wykonanie papierowe',status:cycle.execution.status,reasons:[cycle.execution.reason]},
   {id:'journal',name:'Dziennik i ocena wyniku',status:'passed',reasons:[`Zapisano cykl ${cycle.id}. Zamknięte transakcje: ${cycle.account.closedTrades}. Wynik netto: ${fmt(cycle.account.realized)} ${cycle.currency}.`]}];
  for(const stage of stages){const card=element('article',undefined,'agent-stage '+(stage.status==='blocked'?'agent-blocked':''));card.append(element('small',names[stage.status]||stage.status),element('h3',stage.name));for(const reason of stage.reasons||[])card.append(element('p',reason,'fine'));$('agent-flow').append(card);}
 }
 $('agent-cycles').replaceChildren(...cycles.map(c=>{const row=element('details',undefined,'card bot-details');row.append(element('summary',verdict(c)),element('p',c.reason),element('pre',JSON.stringify(c,null,2)));return row;}));
}
syncBotCurrency();syncLabCurrency();

$('bot-account').onclick=()=>submit($('bot-form'),async()=>{const form=$('bot-form');if(!form.reportValidity())return;await api('/api/bot/account',formBody(form));botConfigLoaded=false;message(form,'Poprzednie konto zachowano w archiwum. Uruchomiono nowe konto symulacyjne.');await loadBot();});

function syncTradingForm(form){
 const futures=field(form,'market').value==='perpetual',source=field(form,'source');
 const csv=field(form,'mode')?.value==='csv'&&!futures;
 if(futures)source.value='okx';else if(csv)source.value='reference';for(const option of source.options){option.disabled=(futures&&option.value!=='okx')||(csv&&option.value!=='reference');if(option.value==='okx')option.textContent=futures?'OKX perpetual · USDT · krypto':'OKX spot · USDT · krypto';}
 const engine=field(form,'engine');if(futures&&engine)engine.value='agents';if(engine?.options)for(const option of engine.options)option.disabled=futures&&option.value!=='agents';
 for(const label of form.querySelectorAll('.contract-only')){label.hidden=!futures;for(const input of label.querySelectorAll('input,select'))input.disabled=!futures;}
 form.querySelector('.exposure-label').textContent=futures?'Maks. depozyt · % kapitału':'Maks. ekspozycja · % kapitału';
 if(field(form,'mode')){const csv=field(form,'mode').querySelector('[value="csv"]');if(csv)csv.disabled=futures;if(futures&&field(form,'mode').value==='csv')field(form,'mode').value='live';}
}
field($('bot-form'),'market').onchange=syncBotCurrency;
function syncReplay(){const form=$('replay-form');syncTradingForm(form);const unit=field(form,'source').value==='okx'?'USDT':'USD';form.querySelector('.replay-currency').textContent=unit;syncAssetUnits(form,unit);}
for(const name of ['market','source','mode'])field($('replay-form'),name).onchange=syncReplay;
$('replay-copy').onclick=async()=>{await loadBotPresets();for(const[k,v]of Object.entries(formBody($('bot-form')))){const input=field($('replay-form'),k);if(input)input.value=v;}syncReplay();message($('replay-form'),'Skopiowano ustawienia formularza bota. Test nie uruchomi ani nie zmieni konta.');};
let replayReport=null;
$('replay-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{const body=formBody(e.target);if(body.mode==='csv'){if(!importCsv||data?.mode!=='csv')throw Error('Najpierw poprawnie zaimportuj CSV w Przeglądzie rynku.');if(data.instrument.id!==body.instrument||data.timeframe!==body.timeframe)throw Error('Wybierz instrument i interwał zgodny z importem CSV.');body.csv=importCsv;body.csv_instrument=data.instrument.id;body.csv_timeframe=data.timeframe;}text('replay-state','Pobieranie zamkniętych świec i symulacja wybranego modelu…');const r=await api('/api/bot/backtest',body);renderReplay(r);await loadReplayHistory();message(e.target,'Raport zapisano. Konto bota pozostało bez zmian.');});};
function renderReplay(r){
 replayReport=r;const m=r.metrics,unit=r.currency;const amount=v=>fmt(v)+' '+unit;
 text('replay-state',(r.demo?'DEMONSTRACJA — syntetyczne dane. ':'')+`${r.instrument} · ${r.market} · ${r.config.leverage}× · ${r.source} · ${r.config.timeframe} · ${r.bars} świec · ${displayDate(r.startDate)} – ${displayDate(r.endDate)}. `+r.notice);
 $('replay-summary').replaceChildren(metric('Wynik netto',amount(m.netPnl),fmt(m.returnPct)+'%',m.netPnl>=0?'positive':'negative'),metric('Kapitał końcowy',amount(m.finalEquity),'Po zamknięciu ostatniej pozycji'),metric('Transakcje / wygrane',m.closedTrades+' / '+fmt(m.winRate)+'%','PF '+(m.profitFactor===null?'nieokreślony':fmt(m.profitFactor))),metric('Maks. obsunięcie',fmt(m.maxDrawdown)+'%',m.liquidations+' likwidacji modelowych'),metric('Koszty / funding',amount(m.fees)+' / '+amount(m.funding),r.blockedCount+' zablokowanych wejść; dodatni funding = obciążenie'));
 const chart=$('replay-chart');chart.hidden=false;chart.replaceChildren(element('h3','Krzywa kapitału · '+unit));
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 800 220');svg.setAttribute('role','img');svg.setAttribute('aria-label','Krzywa kapitału wybranej symulacji');
 const data=r.equity,low=Math.min(r.config.capital,...data.map(p=>p.value)),high=Math.max(r.config.capital,...data.map(p=>p.value)),span=high-low||1;
 const line=document.createElementNS(ns,'polyline'),step=Math.max(1,Math.floor(data.length/1000)),sample=data.filter((_,i)=>i%step===0||i===data.length-1);
 line.setAttribute('points',sample.map(p=>`${40+(data.indexOf(p)/Math.max(1,data.length-1))*740},${190-(p.value-low)/span*170}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#1666d8');line.setAttribute('stroke-width','2');svg.append(line);chart.append(svg,element('p',`${amount(low)} – ${amount(high)} · pełna krzywa i transakcje w raporcie JSON.`,'fine'));
 $('replay-trades').replaceChildren(...r.trades.slice(-200).reverse().map(t=>{const tr=element('tr');for(const v of [t.direction+' '+t.leverage+'×',displayDate(t.entryDate),displayDate(t.exitDate),amount(t.pnl),t.reason])tr.append(element('td',v));return tr;}));
 if(!r.trades.length){const row=element('tr'),cell=element('td','Brak transakcji spełniających warunki w tym okresie.');cell.colSpan=5;row.append(cell);$('replay-trades').append(row);}
 $('replay-download').disabled=false;
}
$('replay-download').onclick=()=>{if(!replayReport)return;const url=URL.createObjectURL(new Blob([JSON.stringify(replayReport,null,2)],{type:'application/json'})),a=element('a');a.href=url;a.download=`Inwestapp-${replayReport.instrument}-${replayReport.market}-backtest.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
async function loadReplayHistory(){try{const r=await api('/api/bot/backtests');$('replay-records').replaceChildren(...r.records.map(item=>{const card=element('article',undefined,'card');card.append(element('p',`${quoteTime(item.created_at)} · ${item.instrument} · ${item.market} · ${item.config.preset} · ${fmt(item.metrics.returnPct)}%${item.demo?' · DEMONSTRACJA':''}`),action('Otwórz raport',async()=>renderReplay(await api('/api/bot/backtests?id='+encodeURIComponent(item.id)))));return card;}));}catch(e){text('replay-records',e.message);}}
let sourcesLoaded=false;
async function loadStrategySources(){if(sourcesLoaded)return;try{const r=await api('/api/strategies/sources');$('strategy-providers').replaceChildren(...r.providers.map(p=>{const card=element('article',undefined,'card');card.append(element('h3',p.name),element('p',p.status),element('p',p.access+' · '+p.capability,'fine'),externalLink(p.url,'Dokumentacja źródła'));return card;}));field($('source-form'),'template').replaceChildren(...r.templates.map(t=>{const o=element('option',t.name);o.value=t.id;return o;}));sourcesLoaded=true;}catch(e){text('strategy-providers',e.message);}}
$('source-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{await api('/api/strategies/source',formBody(e.target));message(e.target,'Zapisano źródło i kontekst badania. Pobranego kodu nie uruchomiono.');await loadResearch();});};
syncBotCurrency();syncReplay();
field($('source-form'),'market').onchange=()=>syncAssetUnits($('source-form'),field($('source-form'),'market').value==='perpetual'?'USDT':'USD');
