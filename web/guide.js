/* Beginner workflow reuses the existing validated engines and explicit actions. */
const guideDefaults={engine:'agents',source:'okx',market:'spot',leverage:1,direction:'both',capital:10000,risk:1,costs:10,slippage:5,daily_loss:3,max_drawdown:10,max_spread:30,max_exposure:25,max_deviation:3,maintenance_margin:.5,funding_bps:1};
let guideBase={...guideDefaults},guideReady=false,guideLoading=false,guideReport=null,guideJob=null,guideActive=false,guideOpenedId=null,guideLastCheck=0;
function setView(advanced){document.body.dataset.view=advanced?'advanced':'simple';$('view-toggle').textContent=advanced?'Prosty widok':'Więcej funkcji i ustawień';$('view-toggle').setAttribute('aria-pressed',String(advanced));try{localStorage.setItem('inwestapp.view',advanced?'advanced':'simple');}catch{}}
window.enableAdvanced=()=>setView(true);
$('view-toggle').onclick=()=>{const advanced=document.body.dataset.view!=='advanced';setView(advanced);if(!advanced&&document.querySelector('.nav.advanced-only[data-tab="'+tab+'"]'))setTab('home');};
try{setView(localStorage.getItem('inwestapp.view')==='advanced');}catch{setView(false);}
function guideConfig(){
 const values=formBody($('guide-form')),cfg={...guideBase,...values};
 for(const name of ['capital','risk','leverage'])cfg[name]=Number(cfg[name]);
 if(cfg.market==='spot')cfg.leverage=1;else{cfg.source='okx';cfg.engine='agents';}
 if(INSTRUMENTS.find(i=>i.id===cfg.instrument)?.kind!=='crypto')cfg.source='reference';
 cfg.currency=cfg.source==='okx'?'USDT':'USD';return cfg;
}
function guideMatches(){if(!guideReport)return false;const cfg=guideConfig();return Object.entries(guideReport.config).every(([k,v])=>String(cfg[k])===String(v));}
function updateGuide(){
 const form=$('guide-form'),crypto=INSTRUMENTS.find(i=>i.id===field(form,'instrument').value)?.kind==='crypto';
 field(form,'market').querySelector('[value="perpetual"]').disabled=!crypto;if(!crypto)field(form,'market').value='spot';
 const futures=field(form,'market').value==='perpetual';$('guide-leverage').hidden=!futures;field(form,'leverage').disabled=!futures;
 field(form,'source').querySelector('[value="okx"]').disabled=!crypto;
 if(!crypto)field(form,'source').value='reference';else if(futures)field(form,'source').value='okx';
 field(form,'source').disabled=futures||!crypto;
 // Disabled controls are intentionally supplied from the visible market choice.
 const cfg=guideConfig();if(!crypto)cfg.source='reference';
 const summary=`${assetName(cfg.instrument)} · ${cfg.market==='spot'?'spot':'futures '+cfg.leverage+'×'} · ${cfg.timeframe} · ${catalog?.presets?.[cfg.preset]?.name||'wczytywanie zestawu'} · ${cfg.capital} ${cfg.currency} · ryzyko ${cfg.risk}%.`;
 const assumptions=`Koszt ${cfg.costs} pb i poślizg ${cfg.slippage} pb na stronę; spread testowy 10 pb. Limit straty dnia ${cfg.daily_loss}%, obsunięcia ${cfg.max_drawdown}%, ${futures?'depozytu':'ekspozycji'} ${cfg.max_exposure}%. ${futures?'Funding i depozyt utrzymania są założeniami, chyba że wybierzesz pełne dane kontraktowe.':''} Pełne parametry zmienisz w panelu zaawansowanym.`;
 text('guide-assumptions',summary+' '+assumptions);text('guide-test-config',summary+' '+assumptions);
 const contract=field($('guide-test-form'),'market_data');contract.querySelector('[value="contract"]').disabled=!futures||field($('guide-test-form'),'mode').value!=='live';if(contract.selectedOptions[0]?.disabled)contract.value='assumptions';
 const matching=guideMatches();$('guide-paper-start').disabled=!guideReady||guideActive||!matching||guideReport?.demo||!guideReport?.historicalGuardReplayed;
 text('guide-last-test',guideReport?`${guideReport.instrument} · ${guideReport.config.timeframe} · ${guideReport.metrics.closedTrades} transakcji · ${guideReport.demo?'dane syntetyczne':matching?'ustawienia zgodne z formularzem':'ustawienia zmienione — wykonaj nowy test'}. Raport nie jest dopuszczeniem OKX Demo.`:'Brak wybranego raportu. Zacznij od testu na rzeczywistej historii.');
}
async function loadGuide(force=false){
 if(guideLoading||force!==true&&Date.now()-guideLastCheck<5000)return;guideLoading=true;
 try{
  await loadBotPresets();const [bot,demo,cg,ops,health,security]=await Promise.all([api('/api/bot'),api('/api/demo/status'),api('/api/coingecko/status'),api('/api/ops/status'),api('/api/exchange/health'),api('/api/security')]);
  if(!guideReady){if(bot.state?.config){guideBase={...guideDefaults,...bot.state.config};for(const[k,v]of Object.entries(guideBase)){const input=field($('guide-form'),k);if(input)input.value=v;}}else field($('guide-form'),'preset').value='balanced';guideReady=true;}
  guideActive=Boolean(bot.state?.active);const state=bot.state;
  text('guide-bot-state',state?`${guideActive?'SYMULACJA AKTYWNA':'SYMULACJA ZATRZYMANA'} · ${state.config.instrument} · ${state.position?'otwarta pozycja':state.pending?'oczekuje wykonanie':'brak pozycji'} · ${state.status}`:'Symulacja nie była uruchamiana. Wybierz ustawienia i sprawdź historię.');
  text('guide-wait-reason',state?.lastDecision?.reason||'Przyczyna decyzji pojawi się po poprawnym cyklu analizy. Brak transakcji może wynikać z jakości danych, niezgodnych wskaźników albo niespełnionego filtra historycznego.');
  const rows=[`Pliki aplikacji: ${security.integrity.verified?'zgodne z paczką':'niezgodne — pobierz cały ZIP ponownie'}.`,health.reason,
   `OKX Demo: ${demo.configured?'klucze obecne; połączenie wymaga osobnego sprawdzenia':'brak kluczy; handel papierowy pozostaje dostępny'}. ${demo.state?.active?'Demo jest aktywne — sterowanie w Centrum automatyzacji.':''}`,
   `CoinGecko: ${cg.configured?'klucz obecny; sprawdź odczyt w jego panelu':'opcjonalny klucz nieuzupełniony'}.`,
   `Powiadomienia: ${ops.notificationConfigured?'kanał skonfigurowany; sprawdź wiadomość testową':'opcjonalny kanał nieuzupełniony'}.`];
  $('guide-ready').replaceChildren(...rows.map(value=>element('p',value,'fine')));updateGuide();
 }catch(error){text('guide-action',error.message);}finally{guideLoading=false;guideLastCheck=Date.now();}
}
function showGuideReport(report){
 guideReport=report;const m=report.metrics;
 const title=report.demo?'Dane syntetyczne — tylko nauka obsługi':m.closedTrades<10?'Za mało transakcji do oceny':m.netPnl<=0||m.profitFactor===null||m.profitFactor<=1||m.maxDrawdown>report.config.max_drawdown||m.liquidations>0?'Test nie spełnia progu badawczego':'Raport wart dalszej walidacji';
 text('guide-verdict',title);text('guide-verdict-detail',`${report.instrument} · ${displayDate(report.startDate)} – ${displayDate(report.endDate)} · ${report.bars} świec po rozgrzewce. ${m.closedTrades===0?'Nie otwarto żadnej transakcji; wynik 0% nie potwierdza skuteczności. ':''}${report.blockedCount} zablokowanych wejść. Dopuszczenie OKX Demo wymaga odrębnej walidacji i zatwierdzenia. Giełdowych przerw i opóźnień sieci nie odtwarzamy historycznie.`);
 $('guide-test-metrics').replaceChildren(metric('Wynik netto',fmt(m.netPnl)+' '+report.currency,fmt(m.returnPct)+'%'),metric('Maks. obsunięcie',fmt(m.maxDrawdown)+'%',m.liquidations+' likwidacji modelowych'),metric('Transakcje',String(m.closedTrades),'PF '+(m.profitFactor===null?'nieokreślony':fmt(m.profitFactor))),metric('Koszty i funding',fmt(m.fees)+' / '+fmt(m.funding)+' '+report.currency,'Uwzględnione w wyniku'));
 $('guide-report-open').disabled=false;updateGuide();
}
async function loadGuideJobs(){
 try{
  const {jobs}=await api('/api/backtest-jobs');const active=jobs.find(j=>['queued','running','cancelling'].includes(j.state));
  guideJob=active||jobs[0]||null;const running=Boolean(active);$('guide-job-cancel').disabled=!running;$('guide-test-form').querySelector('[type="submit"]').disabled=running;
  if(guideJob){text('guide-job-state',`${guideJob.phase}${guideJob.error?' · '+guideJob.error:''}`);if(guideJob.report_id&&guideOpenedId!==guideJob.report_id){guideOpenedId=guideJob.report_id;showGuideReport(await api('/api/bot/backtests?id='+encodeURIComponent(guideJob.report_id)));}}
  $('guide-jobs').replaceChildren(...jobs.map(job=>{const card=element('article',undefined,'card');card.append(element('p',`${quoteTime(job.created_at)} · ${job.config.instrument} · ${job.config.timeframe} · ${job.phase}`));if(job.report_id)card.append(action('Otwórz wynik',async()=>showGuideReport(await api('/api/bot/backtests?id='+encodeURIComponent(job.report_id)))));if(job.error)card.append(element('p',job.error,'fine'));return card;}));
 }catch(error){text('guide-job-state',error.message);}
}
const priorGuideTab=window.workspaceTabChanged;
window.workspaceTabChanged=next=>{priorGuideTab?.(next);if(next==='home')loadGuide();if(next==='history'){updateGuide();loadGuideJobs();}};
$('guide-form').onsubmit=event=>{event.preventDefault();updateGuide();setTab('history');};
$('guide-form').addEventListener('input',updateGuide);$('guide-form').addEventListener('change',updateGuide);
$('guide-test-form').addEventListener('change',updateGuide);
$('guide-test-form').onsubmit=event=>{event.preventDefault();submit(event.target,async()=>{if(!guideReady||!$('guide-form').reportValidity())throw Error('Uzupełnij ustawienia na ekranie Start.');text('guide-job-state','Zlecanie nowego testu…');guideReport=null;updateGuide();$('guide-report-open').disabled=true;text('guide-verdict','Nowy test w toku');$('guide-test-metrics').replaceChildren();await api('/api/backtest-jobs',{...guideConfig(),...formBody(event.target),execution_model:'full'});message(event.target,'Test działa w tle. Możesz zmienić zakładkę; wynik będzie zapisany.');await loadGuideJobs();});};
$('guide-job-cancel').onclick=async()=>{try{if(guideJob)await api('/api/backtest-jobs/cancel',{id:guideJob.id});await loadGuideJobs();}catch(error){text('guide-job-state',error.message);}};
$('guide-report-open').onclick=()=>{if(guideReport){setTab('bot');renderReplay(guideReport);$('replay-state').scrollIntoView({behavior:'smooth',block:'center'});}};
$('guide-paper-start').onclick=async()=>{try{if(!guideMatches()||guideReport.demo||!guideReport.historicalGuardReplayed)throw Error('Wykonaj pełny test rzeczywistej historii z tymi ustawieniami.');$('guide-paper-start').disabled=true;await api('/api/bot/start',guideReport.config);text('guide-action','Uruchomiono wyłącznie handel papierowy. Blokady danych, strategii i ryzyka nadal obowiązują.');await loadGuide(true);}catch(error){text('guide-action',error.message);}};
$('guide-paper-stop').onclick=async()=>{try{await api('/api/bot/stop',{});await loadGuide(true);}catch(error){text('guide-action',error.message);}};
$('guide-advanced-bot').onclick=()=>setTab('bot');$('guide-refresh').onclick=()=>loadGuide(true);
$('guide-to-history').onclick=()=>setTab('history');$('guide-edit').onclick=()=>setTab('home');
$('guide-chart').onclick=()=>{const cfg=guideConfig();selected=cfg.instrument;$('timeframe').value=cfg.timeframe;$('mode').value=cfg.source==='okx'?'okx':'live';importCsv=null;renderInstruments();setTab('analysis');load();};
setInterval(()=>{if(['home','history'].includes(tab)&&!document.hidden&&guideJob&&['queued','running','cancelling'].includes(guideJob.state))loadGuideJobs();},2000);
setInterval(()=>{if(!document.hidden){if(tab==='home')loadGuide();if(tab==='history')loadGuideJobs();}},15000);
(async()=>{await loadGuide();setTab(tab);await loadGuideJobs();})();
