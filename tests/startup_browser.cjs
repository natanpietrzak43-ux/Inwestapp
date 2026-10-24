/* Optional: dedicated server with temporary INWESTAPP_DATA_DIR. */
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8019';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 async function page(){const p=await browser.newPage();await p.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],fetchedAt:new Date().toISOString(),alertEvents:[]}}));await p.route('**/api/analyze?*',r=>new URL(r.request().url()).searchParams.get('mode')==='demo'?r.continue():r.fulfill({status:502,json:{error:'Kontrolowana niedostępność notowań — test interfejsu.'}}));return p;}
 try{
  const p=await page(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base);
  await p.waitForFunction(()=>document.querySelector('#startup-state').textContent.includes('są wczytane'));
  assert.equal(await p.locator('#server-version').textContent(),'2.0.0');assert.equal(await p.locator('#tool-options .tool-help').count(),14);
  await p.click('#demo-chart');await p.waitForFunction(()=>document.querySelector('#price-chart svg')&&document.querySelector('#notice').textContent.includes('DEMONSTRACJA'));
  assert.ok(await p.locator('.chart-toolbar').isVisible());assert.equal(await p.locator('[data-chart-mode]').count(),4);assert.deepEqual(errors,[]);
  await p.screenshot({path:'/tmp/inwestapp-v200-ready.png',fullPage:true});await p.close();
  const old=await page();await old.route('**/api/health',r=>r.fulfill({json:{status:'ok',version:'1.6.0',instruments:['XRP','XLM']}}));await old.goto(base);
  await old.waitForFunction(()=>document.querySelector('#startup-state').textContent.includes('różni się'));
  assert.equal(await old.locator('#server-version').textContent(),'1.6.0');assert.ok(await old.locator('#demo-chart').isDisabled());assert.ok(await old.locator('#update-status.warning').isVisible());await old.close();
  const missing=await page();await missing.route('**/chart.js?*',r=>r.abort());await missing.goto(base);
  await missing.waitForFunction(()=>document.querySelector('#update-status').classList.contains('warning'));
  assert.ok(await missing.locator('#startup-state').textContent().then(t=>t.includes('Ctrl+F5')));assert.ok(await missing.locator('#show-chart').isDisabled());await missing.close();
  console.log('PASS: release badge, guided demo despite feed outage, old-server mismatch, and visible missing-script failure.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
