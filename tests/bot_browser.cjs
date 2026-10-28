/* Optional integration test. Dedicated server + temporary INWESTAPP_DATA_DIR only.
   Creates and stops its own PAPER account; never run against personal storage. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8023';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],alertEvents:[]}}));
 await page.route('**/api/analyze?*',r=>r.fulfill({status:502,json:{error:'Controlled feed failure during bot UI test'}}));
 try{
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#server-version').textContent==='2.1.0');
  await page.click('[data-tab="bot"]');await page.waitForFunction(()=>document.querySelectorAll('#replay-form [name="preset"] option').length===5);
  await page.waitForFunction(()=>document.querySelector('#bot-state').textContent!=='Wczytywanie stanu…');
  await page.selectOption('#bot-form [name="market"]','spot');
  assert.equal(await page.locator('#bot-form .contract-only:visible').count(),0);
  await page.selectOption('#bot-form [name="market"]','perpetual');assert.equal(await page.locator('#bot-form .contract-only:visible').count(),4);
  assert.equal(await page.inputValue('#bot-form [name="source"]'),'okx');assert.ok(await page.locator('#bot-form [name="source"] [value="reference"]').evaluate(e=>e.disabled));
  assert.ok(await page.locator('#bot-form [name="instrument"] [value="GOLD"]').evaluate(e=>e.disabled));
  await page.selectOption('#bot-form [name="instrument"]','XLM');await page.fill('#bot-form [name="leverage"]','3');
  await page.click('#bot-form [type="submit"]');await page.waitForFunction(()=>document.querySelector('#bot-form .form-state').textContent.includes('aktywny'));
  await page.click('#bot-stop');await page.waitForFunction(()=>document.querySelector('#bot-state').textContent.includes('ZATRZYMANY'));
  const stateBefore=await page.evaluate(async()=> (await (await fetch('/api/bot')).json()).state);
  assert.equal(stateBefore.config.market,'perpetual');assert.equal(stateBefore.config.leverage,3);assert.equal(stateBefore.active,false);
  await page.click('#replay-copy');assert.equal(await page.inputValue('#replay-form [name="market"]'),'perpetual');assert.equal(await page.inputValue('#replay-form [name="instrument"]'),'XLM');
  await page.selectOption('#replay-form [name="mode"]','demo');
  await page.click('#replay-form [type="submit"]');await page.waitForFunction(()=>document.querySelector('#replay-form .form-state').textContent.includes('Raport zapisano'));
  assert.match(await page.locator('#replay-state').textContent(),/DEMONSTRACJA.*perpetual.*3×/);
  assert.equal(await page.locator('#replay-summary .metric').count(),5);assert.ok(await page.locator('#replay-chart svg').isVisible());
  assert.doesNotMatch(await page.locator('#replay-chart svg polyline').getAttribute('points'),/NaN|undefined/);
  assert.match(await page.locator('#replay-state').textContent(),/kroczącą oceną wyłącznie wcześniejszych świec/);
  const stateAfter=await page.evaluate(async()=> (await (await fetch('/api/bot')).json()).state);assert.deepEqual(stateAfter,stateBefore);
  const [download]=await Promise.all([page.waitForEvent('download'),page.click('#replay-download')]);
  const report=JSON.parse(await fs.readFile(await download.path(),'utf8'));assert.equal(report.market,'perpetual');assert.equal(report.config.leverage,3);assert.equal(report.demo,true);assert.ok(report.equity.length>0);
  await page.reload();await page.click('[data-tab="bot"]');await page.waitForFunction(()=>document.querySelector('#replay-records button'));
  await page.locator('details:has(#replay-records) > summary').click();
  await page.locator('#replay-records button').first().click();await page.waitForFunction(()=>document.querySelector('#replay-download').disabled===false);
  assert.match(await page.locator('#replay-state').textContent(),/perpetual/);
  await page.waitForFunction(()=>document.querySelectorAll('#source-form [name="template"] option').length===3);
  assert.match(await page.locator('#strategy-providers').textContent(),/deprecated/);
  await page.selectOption('#source-form [name="instrument"]','XLM');await page.selectOption('#source-form [name="market"]','perpetual');
  await page.selectOption('#source-form [name="template"]','adx_momentum');await page.click('#source-form [type="submit"]');
  await page.waitForFunction(()=>document.querySelector('#source-form .form-state').textContent.includes('Zapisano źródło'));
  await page.waitForFunction(()=>document.querySelector('#mcp-records').textContent.includes('GPL-3.0'));
  assert.match(await page.locator('#mcp-records').textContent(),/XLM.*1h.*perpetual/);assert.match(await page.locator('#mcp-records pre').first().textContent(),/GPL-3.0/);
  await page.locator('#replay-form').screenshot({path:'/tmp/inwestapp-v180-replay-form.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#replay-chart').scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile viewport must not overflow');
  await page.locator('#replay-chart').screenshot({path:'/tmp/inwestapp-v180-replay-chart.png'});
  assert.deepEqual(errors,[]);console.log('PASS: futures controls, paper start/stop, replay/config copy, independent account, JSON download, persistence, public strategy context, mobile layout.');
 }finally{try{const session=await(await page.request.get(base+'/api/session',{headers:{'X-Inwestapp-Client':'browser'}})).json();await page.request.post(base+'/api/bot/stop',{data:{},headers:{'X-Inwestapp-Token':session.csrfToken}});}finally{await browser.close();}}
})().catch(e=>{console.error(e);process.exit(1)});
