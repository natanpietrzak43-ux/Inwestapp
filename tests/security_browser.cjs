/* Controlled attack probes against a dedicated local server; no real orders. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const http=require('node:http');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8050';
(async()=>{
 const attacker=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>Controlled foreign origin</title>');});
 await new Promise(resolve=>attacker.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/quotes**',r=>r.fulfill({json:{quotes:[],alertEvents:[]}}));
  await page.route('**/api/analyze?*',r=>new URL(r.request().url()).searchParams.get('mode')==='demo'?r.continue():r.fulfill({status:502,json:{error:'Controlled feed failure'}}));
  const response=await page.goto(base);
  assert.match(response.headers()['content-security-policy'],/frame-ancestors 'none'/);
  await page.waitForFunction(()=>document.querySelector('#startup-state').textContent.includes('są wczytane'));
  assert.equal(await page.locator('#instruments .instrument').count(),19);
  await page.click('#demo-chart');await page.locator('#instruments .instrument').filter({hasText:'Solana'}).click();
  await page.waitForFunction(()=>data?.instrument.id==='SOL');
  assert.equal(await page.evaluate(()=>data.decision.action),'WAIT');
  await page.click('[data-tab="alerts"]');await page.selectOption('#alert-form [name="instrument"]','SUI');
  await page.fill('#alert-form [name="price"]','2');await page.click('#alert-form [type="submit"]');
  await page.waitForFunction(()=>document.querySelectorAll('#alerts-list .entry').length===1);
  const id=await page.evaluate(async()=> (await(await fetch('/api/alerts')).json()).alerts[0].id);
  const attack='<img src=x onerror="window.INWESTAPP_ATTACKED=true"> <script>window.INWESTAPP_ATTACKED=true</script>';
  await page.route('**/api/news?*',r=>r.fulfill({json:{items:[{title:attack,snippet:attack,url:'https://example.com/article',source:attack,feed:'Fixture',publishedAt:null,staleSource:false,tone:'neutral',themes:[]}],sources:[],summary:{recentCount:0,positive:0,negative:0,mixed:0,neutral:0},notice:'Controlled hostile text'}}));
  await page.click('[data-tab="news"]');await page.waitForFunction(()=>document.querySelector('#news-list').textContent.includes('onerror'));
  assert.equal(await page.locator('#news-list img, #news-list script').count(),0);
  assert.equal(await page.evaluate(()=>window.INWESTAPP_ATTACKED),undefined);
  // Even an injected inline script element is stopped by the browser's CSP.
  const blocked=await page.evaluate(async()=>{
   let violation=false;document.addEventListener('securitypolicyviolation',()=>violation=true,{once:true});
   const s=document.createElement('script');s.textContent='window.INWESTAPP_ATTACKED=true';document.body.append(s);
   await new Promise(r=>setTimeout(r,100));s.remove();return violation&&!window.INWESTAPP_ATTACKED;
  });assert.equal(blocked,true);
  await page.click('[data-tab="automation"]');await page.waitForFunction(()=>document.querySelector('#security-state').textContent.includes('ZGODNE'));
  assert.match(await page.locator('#security-notice').textContent(),/Defender/);
  assert.equal(await page.locator('#contract-form option').count(),16);
  assert.equal(await page.locator('#demo-start').isDisabled(),true);
  const foreign=await browser.newPage();await foreign.goto('http://127.0.0.1:'+attacker.address().port);
  const attempts=await foreign.evaluate(async target=>{
   async function attempt(path,options){try{const r=await fetch(target+path,options);return {status:r.status,readable:r.ok};}catch{return {blocked:true};}}
   return Promise.all([attempt('/api/export',{}),attempt('/api/session',{headers:{'X-Inwestapp-Client':'browser'}}),attempt('/api/bot/start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),attempt('/api/alerts',{method:'POST',mode:'no-cors',headers:{'Content-Type':'text/plain'},body:'{}'})]);
  },base);
  assert.ok(attempts.every(r=>!r.readable));await foreign.close();
  const state=await page.evaluate(async()=>({alerts:await(await fetch('/api/alerts')).json(),bot:await(await fetch('/api/bot')).json()}));
  assert.equal(state.alerts.alerts.length,1);assert.equal(state.alerts.alerts[0].id,id);assert.equal(state.bot.state,null);
  const original=await page.request.post(base+'/api/bot/start',{data:{}});assert.equal(original.status(),403);
  await page.evaluate(async id=>{const r=await fetch('/api/alerts/'+id,{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('Cleanup failed');},id);
  await page.setViewportSize({width:390,height:844});await page.locator('#security-state').scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.locator('#security-state').screenshot({path:'/tmp/inwestapp-v210-security.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS: expanded assets, token-backed writes, foreign-page read/write rejection, hostile news stays text, browser CSP blocks inline execution, verified package, mobile security status.');
 }finally{await browser.close();await new Promise(resolve=>attacker.close(resolve));}
})().catch(e=>{console.error(e);process.exit(1)});
