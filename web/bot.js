let botLoaded=false,botConfigLoaded=false,mcpTools=[];
const priorWorkspaceTab=window.workspaceTabChanged;
window.workspaceTabChanged=next=>{priorWorkspaceTab?.(next);if(next==='bot'){loadBotPresets().then(loadBot);loadResearch();}};
async function loadBotPresets(){if(botLoaded)return;try{const c=catalog||await api('/api/catalog');document.querySelectorAll('.preset-select').forEach(select=>select.replaceChildren(...Object.entries(c.presets).map(([id,p])=>{const o=element('option',p.name);o.value=id;return o;})));botLoaded=true;}catch(err){text('bot-state',err.message);}}
async function loadBot(){
 try{
  const r=await api('/api/bot'),s=r.state;if(s?.config&&!botConfigLoaded){for(const[k,v]of Object.entries(s.config)){const input=field($('bot-form'),k);if(input)input.value=v;}botConfigLoaded=true;}if(s)field($('bot-form'),'capital').readOnly=s.tradeCount>0;text('bot-state',s?`${s.active?'AKTYWNY':'ZATRZYMANY'} · ${s.status} · ostatni cykl ${s.lastHeartbeat?quoteTime(s.lastHeartbeat):'oczekiwanie'}${s.lastDecision?' · '+s.lastDecision.action+': '+s.lastDecision.reason:''}`:'Bot nie był jeszcze uruchamiany. Wybierz instrument i parametry.');
  $('bot-summary').replaceChildren(metric('Kapitał papierowy',s?money(s.equity):'—',s?.position&&!s.valuationFresh?'Brak świeżej wyceny':'Po kosztach likwidacji'),metric('Wynik zamkniętych',money(s?.realized??0),(s?.tradeCount??0)+' transakcji',s?.realized<0?'negative':'positive'),metric('Wynik dnia UTC',s?money(s.dailyPnl):'—',s?.day||'Dzień ustali pierwszy poprawny odczyt'),metric('Pozycja / zlecenie',s?.position?'Otwarta':s?.pending?'Oczekuje':'Brak',s?.config?assetName(s.config.instrument)+' · '+s.config.timeframe:'Brak rzeczywistych zleceń'));
  $('bot-close').disabled=!s?.position;
  if(s?.position){const p=s.position;text('bot-position',`${assetName(s.config.instrument)} · wejście $ ${price(p.entry)} · ${fmt(p.units,6)} jednostek · stop $ ${price(p.stop)} · cel $ ${price(p.target)} · data ${displayDate(p.entry_at)}. Ostatnia wycena: ${s.lastQuote?quoteTime(s.lastQuote.asOf):'brak'}.`);}else text('bot-position',s?.pending?`Oczekuje ${s.pending.side}; wykonanie wymaga nowej, świeżej ceny po decyzji.`:'Nie ma otwartej papierowej pozycji.');
  $('bot-trades').replaceChildren(...r.trades.map(t=>{const tr=element('tr');for(const value of [assetName(t.instrument),displayDate(t.entry_at),displayDate(t.exit_at),fmt(t.pnl),t.reason])tr.append(element('td',value));return tr;}));
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
 text('lab-state','Trwa porównanie historii i końcowego okresu…');const r=await api('/api/strategies/test',body);text('lab-state',(r.demo?'DEMONSTRACJA — dane syntetyczne. ':'')+`${r.instrument} · ${r.bars} świec · koszt ${r.costs} pb i poślizg ${r.slippage} pb / stronę · końcowy test od ${displayDate(r.splitDate)}. `+r.notice);
 $('lab-results').replaceChildren(...r.rows.map(row=>{const card=element('article',undefined,'card');card.append(element('h3',row.name));const table=element('div',undefined,'metrics');for(const [name,m]of [['Okres początkowy',row.initial],['Końcowe 30%',row.test]])table.append(metric(name,fmt(m.returnPct)+'%',`${m.trades} transakcji · PF ${m.profitFactor===null?'nieokreślony':fmt(m.profitFactor)} · obsunięcie ${fmt(m.maxDrawdown)}%`,m.returnPct>=0?'positive':'negative'));card.append(table,element('p',row.researchFilterPassed?'Przeszedł minimalny filtr badawczy. Nie potwierdza przyszłego zysku.':row.reasons.join(' '),'fine'));return card;}));message(e.target,'Porównanie gotowe. Bot i wybrany zestaw nie zostały zmienione.');
 });};
$('mcp-check').onclick=async()=>{
 $('mcp-check').disabled=true;text('mcp-state','Sprawdzanie protokołu MCP i katalogu narzędzi…');
 try{const r=await api('/api/mcp/status');text('mcp-state',r.connected?`Połączono z trader.dev · ${r.totalTools} narzędzi, ${r.tools.length} badawczych do strategii. ${r.notice}`:r.error);mcpTools=r.tools||[];$('mcp-form').hidden=!r.connected||!mcpTools.length;field($('mcp-form'),'tool').replaceChildren(...mcpTools.map(t=>{const o=element('option',t.name);o.value=t.name;return o;}));showMcpSchema();}catch(err){text('mcp-state',err.message);}finally{$('mcp-check').disabled=false;}
};
function showMcpSchema(){const t=mcpTools.find(t=>t.name===field($('mcp-form'),'tool').value);text('mcp-schema',t?JSON.stringify(t.inputSchema,null,2):'Brak dozwolonych narzędzi badawczych.');}
field($('mcp-form'),'tool').onchange=showMcpSchema;
$('mcp-form').onsubmit=e=>{e.preventDefault();submit(e.target,async()=>{const body=formBody(e.target);body.arguments=JSON.parse(body.arguments);await api('/api/mcp/research',body);message(e.target,'Zapisano materiał z MCP jako niezweryfikowany. Nie uruchomiono pobranego kodu.');await loadResearch();});};
async function loadResearch(){try{const r=await api('/api/strategies/research');$('mcp-records').replaceChildren(...r.records.map(item=>{const card=element('details',undefined,'card bot-details');card.append(element('summary',`${item.tool} · ${quoteTime(item.fetchedAt)} · materiał niezweryfikowany`),element('pre',JSON.stringify(item.content,null,2)));return card;}));}catch(e){text('mcp-records',e.message);}}
setInterval(()=>{if(tab==='bot'&&!document.hidden)loadBot();},15000);
