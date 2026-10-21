/* Optional browser regression: start a server with a TEMPORARY
   INWESTAPP_DATA_DIR, then INWESTAPP_TEST_BASE=http://127.0.0.1:8018 node tests/chart_browser.cjs.
   Requires externally installed playwright and Chromium. No trading actions. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.INWESTAPP_TEST_BASE||'http://127.0.0.1:8018';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 async function demo(){await page.waitForFunction(()=>document.querySelectorAll('#tool-options input').length===14);await page.selectOption('#mode','demo');await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('DEMONSTRACJA')&&document.querySelector('#price-chart svg'));}
 async function chartPoint(index,price){await page.locator('#price-chart').scrollIntoViewIfNeeded();return page.evaluate(({index,price})=>{const f=marketChart.frame;const value=price??(marketChart.rows[index].high+marketChart.rows[index].low)/2;const point=new DOMPoint(f.x(index),f.y(value)).matrixTransform(f.svg.getScreenCTM());return{x:point.x,y:point.y,value,index,date:marketChart.rows[index].date};},{index,price});}
 async function painted(){await page.waitForFunction(()=>marketChart.rows?.length===marketChart.view.count&&marketChart.offset===marketChart.view.start);}
 async function clickChart(index,price){const point=await chartPoint(index,price);await page.mouse.click(point.x,point.y);return point;}
 try{
  await page.goto(base);await demo();
  const point=await chartPoint(50);await page.mouse.move(point.x,point.y);
  let actual=await page.evaluate(()=>({index:marketChart.cursor.index,value:marketChart.cursor.price,date:marketChart.rows[marketChart.cursor.index].date}));
  assert.equal(actual.index,50);assert.equal(actual.date,point.date);const tolerance=await page.evaluate(()=>(marketChart.frame.max-marketChart.frame.min)/marketChart.frame.plotH*.5);assert.ok(Math.abs(actual.value-point.value)<=tolerance,'Cursor must map within half a CSS pixel');
  assert.match(await page.locator('.chart-tooltip').textContent(),/Wolumen/);assert.match(await page.locator('#chart-readout').textContent(),/GMT/);
  const n=await page.evaluate(()=>marketChart.view.count);await page.mouse.wheel(0,-120);await page.waitForFunction(n=>marketChart.view.count<n,n);await painted();
  const panPoint=await chartPoint(20);const before=await page.evaluate(()=>marketChart.view.start);await page.mouse.move(panPoint.x,panPoint.y);await page.mouse.down();await page.mouse.move(panPoint.x+80,panPoint.y,{steps:8});await page.mouse.up();await page.waitForFunction(before=>marketChart.view.start<before,before);await painted();
  await page.click('[data-chart-mode="point"]');await clickChart(15);await clickChart(30);await page.waitForFunction(()=>document.querySelector('#chart-marker-count').textContent==='2');assert.match(await page.locator('#chart-measure').textContent(),/Ostatnie dwa punkty/);
  await page.click('[data-chart-mode="level"]');await clickChart(40);await page.waitForFunction(()=>document.querySelector('#chart-marker-count').textContent==='3');
  await page.click('[data-chart-mode="line"]');await clickChart(10);await clickChart(45);await page.waitForFunction(()=>document.querySelector('#chart-marker-count').textContent==='4');
  const saved=await page.evaluate(()=>JSON.stringify(marketChart.marks));await page.click('#chart-clear');await page.waitForFunction(()=>document.querySelector('#chart-marker-count').textContent==='0');await page.click('#chart-undo');await page.waitForFunction(()=>document.querySelector('#chart-marker-count').textContent==='4');assert.equal(await page.evaluate(()=>JSON.stringify(marketChart.marks)),saved);
  const checks=await page.locator('#tool-options input:checked').count();let analyzeRequests=0;const track=req=>{if(req.url().includes('/api/analyze'))analyzeRequests++;};page.on('request',track);
  for(const button of await page.locator('#tool-options .tool-help').all()){await button.click();assert.ok(await page.locator('#tool-help-dialog').evaluate(d=>d.open));assert.equal(await page.locator('#tool-help-content h3').count(),4);await page.keyboard.press('Escape');assert.equal(await page.locator('#tool-help-dialog').evaluate(d=>d.open),false);}
  assert.equal(await page.locator('#tool-options input:checked').count(),checks);assert.equal(analyzeRequests,0);page.off('request',track);
  await page.reload();await demo();assert.equal(await page.evaluate(()=>JSON.stringify(marketChart.marks)),saved);
  await page.locator('#instruments .instrument').nth(1).click();await page.waitForFunction(()=>data?.instrument.id==='XLM');assert.equal(await page.evaluate(()=>marketChart.marks.length),0);
  await page.locator('#instruments .instrument').first().click();await page.waitForFunction(()=>data?.instrument.id==='XRP');assert.equal(await page.evaluate(()=>JSON.stringify(marketChart.marks)),saved);
  await page.selectOption('#timeframe','1d');await page.waitForFunction(()=>data?.timeframe==='1d');await page.click('[data-range="1"]');await page.waitForFunction(()=>marketChart.view.count===1);await painted();
  assert.equal(await page.locator('#price-chart [data-candle]').count(),1);assert.equal(await page.evaluate(()=>marketChart.marks.length),0);
  const daily=await chartPoint(0);await page.mouse.move(daily.x,daily.y);assert.match(await page.locator('.chart-tooltip').textContent(),/Data świecy dziennej/);assert.doesNotMatch(await page.locator('.chart-tooltip').textContent(),/GMT/);
  await page.selectOption('#timeframe','1h');await page.waitForFunction(()=>data?.timeframe==='1h');await page.click('[data-range="7"]');await page.waitForFunction(()=>marketChart.view.count===168);await painted();
  await page.click('[data-chart-mode="pan"]');await page.locator('#price-chart').focus();await page.keyboard.press('ArrowLeft');assert.ok(await page.evaluate(()=>marketChart.cursor!==null));
  await page.keyboard.press('+');await page.waitForFunction(()=>marketChart.view.count<168);await painted();await page.click('#chart-reset');await page.waitForFunction(()=>marketChart.view.count===168);await painted();
  await page.click('[data-chart-mode="point"]');await page.locator('#price-chart').focus();await page.keyboard.press('ArrowLeft');const markCount=await page.evaluate(()=>marketChart.marks.length);await page.keyboard.press('Enter');await page.waitForFunction(n=>marketChart.marks.length===n+1,markCount);await page.click('[data-chart-mode="pan"]');
  await page.locator('.chart-card').screenshot({path:'/tmp/inwestapp-v17-chart.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#price-chart').scrollIntoViewIfNeeded();await page.waitForFunction(()=>marketChart.frame.width<400);
  const mobile=await chartPoint(80);await page.mouse.move(mobile.x,mobile.y);assert.equal(await page.evaluate(()=>marketChart.cursor.index),80);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.click('#tool-options [data-help-tool="ichimoku"]');assert.ok(await page.locator('#tool-help-dialog').evaluate(d=>d.open));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#tool-help-dialog').screenshot({path:'/tmp/inwestapp-v17-education.png'});await page.click('#tool-help-close');
  const client=await page.context().newCDPSession(page);await page.locator('#price-chart').scrollIntoViewIfNeeded();const box=await page.locator('#price-chart').boundingBox();const x=box.x+100,y=box.y+140;
  const beforePinch=await page.evaluate(()=>marketChart.view.count);
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:x-20,y,id:1},{x:x+20,y,id:2}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-40,y,id:1},{x:x+40,y,id:2}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForFunction(n=>marketChart.view.count<n,beforePinch);await painted();
  await page.evaluate(async()=>{document.querySelectorAll('#tool-options input').forEach(i=>i.checked=true);await load();});await page.waitForFunction(()=>data?.selectedTools.length===14);assert.equal(await page.locator('.indicator-card').count(),7);assert.ok(await page.locator('#price-chart [data-indicator="emaM3"]').count()>0);assert.ok(await page.locator('[data-bx-series="bxShort"]').count()>0);
  assert.deepEqual(errors,[]);console.log('PASS: precise hit, cursor time/OHLC, zoom/pan, annotations, undo, persistence/isolation, 14 lessons, D1, keyboard, mobile and two-finger pinch.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
