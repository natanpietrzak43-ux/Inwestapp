/* Controlled provider fixtures; not evidence of authenticated CoinGecko access. */
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8060';
const instruments=JSON.parse(fs.readFileSync('web/instruments.js','utf8').split('Object.freeze(')[1].split(');')[0]).filter(i=>i.kind==='crypto');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 let configured=false,calls=0,outage=false;
 const usage={monthUTC:'2026-10',requests:3,budget:9000,remaining:8997,notice:'Controlled local request count'};
 const stamp=new Date().toISOString();
 const data={provider:'CoinGecko',currency:'USD',readOnly:true,usage,notice:'Dane zbiorcze. Odległość do ATH nie jest oczekiwanym zyskiem.',sections:{
  markets:{status:'ok',fetchedAt:stamp,cached:false,stale:false,data:instruments.map(i=>({instrument:i.id,name:i.name,id:i.id.toLowerCase(),price:2,change24h:1,change7d:2,change30d:-3,marketCap:1000000000,volume24h:100000000,toAthPct:100,status:'ok',asOf:stamp,stale:false}))},
  global:{status:'ok',fetchedAt:stamp,cached:false,stale:false,data:{marketCapUSD:2000000000000,volume24hUSD:100000000000,btcDominance:55,ethDominance:15,asOf:stamp}},
  trending:{status:'ok',fetchedAt:stamp,cached:false,stale:false,data:[{id:'unknown-token',name:'<img src=x onerror="window.CG_ATTACK=true">',symbol:'TEST',rank:null}]}
 }};
 await page.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],alertEvents:[]}}));
 await page.route('**/api/analyze?*',r=>r.fulfill({status:502,json:{error:'Controlled feed failure'}}));
 await page.route('**/api/coingecko/status',r=>r.fulfill({json:{configured,usage,readOnly:true}}));
 await page.route('**/api/coingecko/overview',r=>{calls++;return r.fulfill(outage?{status:502,json:{error:'Controlled CoinGecko outage'}}:{json:data});});
 try{
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#server-version').textContent==='2.2.0');
  assert.equal(calls,0);const before=await(await page.request.get(base+'/api/bot')).json();
  await page.click('[data-tab="coingecko"]');await page.waitForFunction(()=>document.querySelector('#coingecko-state').textContent.includes('Brak klucza'));
  assert.equal(calls,0);assert.equal(await page.isChecked('#coingecko-auto'),false);assert.ok(await page.locator('#dashboard').isHidden());
  configured=true;await page.click('#coingecko-refresh');await page.waitForFunction(()=>document.querySelectorAll('#coingecko-rows tr').length===16);
  assert.match(await page.locator('#coingecko-state').textContent(),/16 \/ 16/);assert.equal(calls,1);
  assert.match(await page.locator('#coingecko-budget').textContent(),/9000/);assert.equal(await page.locator('#coingecko-global .metric').count(),4);
  assert.equal(await page.locator('#coingecko-trending img, #coingecko-trending script').count(),0);assert.equal(await page.evaluate(()=>window.CG_ATTACK),undefined);
  assert.match(await page.locator('#coingecko-notice').textContent(),/nie jest oczekiwanym zyskiem/);
  assert.equal(await page.locator('#mode').inputValue(),'live');assert.equal(await page.locator('#instruments .instrument').count(),19);
  await page.evaluate(()=>{window.cgRealNow=Date.now;Date.now=()=>window.cgRealNow()+400000;paintCoinGeckoFreshness();});
  assert.equal(await page.locator('#coingecko-rows tr.quote-stale').count(),16);assert.match(await page.locator('#coingecko-state').textContent(),/0 \/ 16/);
  await page.evaluate(()=>{Date.now=window.cgRealNow;paintCoinGeckoFreshness();});
  outage=true;await page.click('#coingecko-refresh');await page.waitForFunction(()=>document.querySelector('#coingecko-state').textContent.includes('nieaktualny'));
  assert.ok(await page.locator('#coingecko-rows').evaluate(e=>e.classList.contains('quote-stale')));
  outage=false;await page.click('#coingecko-refresh');await page.waitForFunction(()=>!document.querySelector('#coingecko-rows').classList.contains('quote-stale'));
  assert.equal(await page.isChecked('#coingecko-auto'),false);
  const after=await(await page.request.get(base+'/api/bot')).json();assert.deepEqual(after.state,before.state);
  await page.locator('#coingecko-global').screenshot({path:'/tmp/inwestapp-v220-coingecko-market.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#coingecko-state').scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#coingecko-state').screenshot({path:'/tmp/inwestapp-v220-coingecko-mobile.png'});
  assert.deepEqual(errors,[]);console.log('PASS: CoinGecko setup state, manual batches, 16 prices, context, safe external text, live staleness, outage/recovery, independent execution source and mobile layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
