/* Dedicated temporary database. Creates/cancels history tests and its own PAPER account. */
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8070';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],alertEvents:[]}}));
 await page.route('**/api/analyze?*',r=>r.fulfill({status:502,json:{error:'Controlled quote outage'}}));
 await page.route('**/api/exchange/health',r=>r.fulfill({json:{verified:true,entryAllowed:true,reason:'Publiczny status OKX sprawdzony — fixture'}}));
 try{
  await page.goto(base);await page.waitForFunction(()=>guideReady&&tab==='home');
  assert.equal(await page.locator('body').getAttribute('data-view'),'simple');assert.ok(await page.locator('[data-tab="automation"]').isHidden());
  assert.ok(await page.locator('#guide-paper-start').isDisabled());assert.match(await page.locator('#guide-ready').textContent(),/brak kluczy/);
  await page.selectOption('#guide-form [name="instrument"]','XLM');await page.fill('#guide-form [name="capital"]','20000');
  await page.click('#guide-form [type="submit"]');await page.waitForFunction(()=>tab==='history');
  assert.match(await page.locator('#guide-test-config').textContent(),/XLM|Stellar/);
  await page.selectOption('#guide-test-form [name="mode"]','demo');await page.click('#guide-test-form [type="submit"]');
  await page.waitForFunction(()=>document.querySelector('#guide-job-state').textContent.includes('Raport zapisany'),null,{timeout:60000});
  assert.match(await page.locator('#guide-verdict').textContent(),/syntetyczne/);assert.equal(await page.locator('#guide-test-metrics .metric').count(),4);
  assert.ok(await page.locator('#guide-report-open').isEnabled());assert.ok(await page.locator('#guide-paper-start').isDisabled());
  const saved=await page.evaluate(()=>guideReport.id);await page.reload();await page.waitForFunction(id=>guideReport?.id===id,saved);
  await page.click('[data-tab="history"]');assert.equal(await page.evaluate(()=>guideReport.id),saved);
  await page.click('#guide-report-open');await page.waitForFunction(()=>tab==='bot');assert.equal(await page.locator('body').getAttribute('data-view'),'advanced');
  assert.ok(await page.locator('#replay-chart svg').isVisible());assert.match(await page.locator('#replay-state').textContent(),/DEMONSTRACJA/);
  // Controlled classification fixture verifies the UI gate; it is not live market evidence.
  await page.evaluate(()=>{guideReport={...guideReport,demo:false,mode:'live'};guideBase={...guideReport.config};for(const[k,v]of Object.entries(guideBase)){const input=field($('guide-form'),k);if(input)input.value=v;}updateGuide();setTab('home');});
  assert.ok(await page.locator('#guide-paper-start').isEnabled());await page.fill('#guide-form [name="risk"]','2');assert.ok(await page.locator('#guide-paper-start').isDisabled());
  await page.fill('#guide-form [name="risk"]','1');assert.ok(await page.locator('#guide-paper-start').isEnabled());
  await page.click('#guide-paper-start');await page.waitForFunction(()=>document.querySelector('#guide-bot-state').textContent.includes('SYMULACJA AKTYWNA'));
  await page.click('#guide-paper-stop');await page.waitForFunction(()=>document.querySelector('#guide-bot-state').textContent.includes('SYMULACJA ZATRZYMANA'));
  const demo=await(await page.request.get(base+'/api/demo/status')).json();assert.equal(demo.state,null);
  await page.click('#view-toggle');assert.equal(await page.locator('body').getAttribute('data-view'),'simple');
  await page.setViewportSize({width:390,height:844});await page.locator('#guide-bot-state').scrollIntoViewIfNeeded();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#guide-bot-state').screenshot({path:'/tmp/inwestapp-v230-guide-mobile.png'});
  assert.deepEqual(errors,[]);console.log('PASS: simple defaults, advanced access, guided full async replay, persisted report, no synthetic start, config matching, explicit PAPER start/stop, mobile layout.');
 }finally{
  try{const s=await(await page.request.get(base+'/api/session',{headers:{'X-Inwestapp-Client':'browser'}})).json();await page.request.post(base+'/api/bot/stop',{data:{},headers:{'X-Inwestapp-Token':s.csrfToken}});}finally{await browser.close();}
 }
})().catch(e=>{console.error(e);process.exit(1)});
