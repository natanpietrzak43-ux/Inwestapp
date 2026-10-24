/* Dedicated temporary database only. No exchange keys/orders are used. */
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8032';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],alertEvents:[]}}));await page.route('**/api/analyze?*',r=>r.fulfill({status:502,json:{error:'Controlled feed failure'}}));
 try{
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#server-version').textContent==='2.0.0');
  await page.click('[data-tab="bot"]');await page.waitForFunction(()=>document.querySelectorAll('#bot-form [name="preset"] option').length===5);
  await page.waitForFunction(()=>document.querySelector('#bot-state').textContent!=='Wczytywanie stanu…');
  await page.selectOption('#bot-form [name="market"]','perpetual');await page.selectOption('#bot-form [name="instrument"]','XLM');await page.fill('#bot-form [name="leverage"]','2');
  await page.click('[data-tab="automation"]');await page.waitForFunction(()=>document.querySelector('#demo-credentials').textContent.includes('Brak kluczy'));
  assert.ok(await page.locator('#dashboard').isHidden());assert.ok(await page.locator('#demo-start').isDisabled());
  await page.click('#version-create');await page.waitForFunction(()=>document.querySelector('#automation-state').textContent.includes('Zapisano wersję'));
  assert.ok((await page.locator('#validation-form [name="versionId"] option').count())>=1);
  assert.ok(await page.locator('#approval-form [type="submit"]').isDisabled());assert.ok(await page.locator('#demo-start').isDisabled());
  await page.click('#demo-check');await page.waitForFunction(()=>document.querySelector('#automation-state').textContent.includes('Brak kluczy OKX Demo'));
  await page.click('#ops-backup');await page.waitForFunction(()=>document.querySelector('#ops-state').textContent.includes('Sprawdzona kopia'));
  await page.click('#ops-notify');await page.waitForFunction(()=>document.querySelector('#ops-state').textContent.includes('nic nie wysłano'));
  await page.click('#contract-form [type="submit"]');await page.waitForFunction(()=>document.querySelectorAll('#contract-spec .metric').length===4);
  assert.match(await page.locator('#contract-spec').textContent(),/XLM-USDT-SWAP/);assert.match(await page.locator('#contract-spec').textContent(),/100/);
  await page.locator('#automation-readiness').screenshot({path:'/tmp/inwestapp-v200-readiness.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#demo-state').scrollIntoViewIfNeeded();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#demo-state').screenshot({path:'/tmp/inwestapp-v200-demo-state.png'});
  const demo=await(await page.request.get(base+'/api/demo/status')).json();assert.equal(demo.state,null);assert.equal(demo.configured,false);
  assert.deepEqual(errors,[]);console.log('PASS: automation centre, frozen version, approval/key gates, read-only connection check, verified backup, truthful notifications, real contract spec, mobile layout; no demo orders.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
