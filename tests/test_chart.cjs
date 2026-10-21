// Run: node --test tests/test_chart.cjs. No third-party packages.
const {test}=require('node:test');const assert=require('node:assert/strict');
const {ChartViewport,validMark,fingerprint}=require('../web/chart.js');
const rows=(n,start=0,step=3600000)=>Array.from({length:n},(_,i)=>({date:new Date(Date.UTC(2026,0,1)+(start+i)*step).toISOString()}));
function view(n=1000){const v=new ChartViewport();v.setData(rows(n),'XRP/OKX/1h',7,3600);return v;}
test('range uses timestamps and a day of daily candles stays one candle',()=>{const v=new ChartViewport();v.setData(rows(400,0,86400000),'D1',1,86400);assert.equal(v.count,1);assert.equal(v.start,399);v.range(7,86400);assert.equal(v.count,7);});
test('zoom stays anchored at the cursor within rounding tolerance',()=>{const v=view();const anchor=v.start+v.count*.31;v.zoom(.6,.31);assert.ok(Math.abs(v.start+v.count*.31-anchor)<=.5);});
test('zoom clamps to available data and cannot produce an empty viewport',()=>{const v=view();v.zoom(100000);assert.equal(v.count,1000);assert.equal(v.start,0);v.zoom(.00001);assert.equal(v.count,8);assert.ok(v.start>=0&&v.start+v.count<=1000);});
test('pan clamps both ends and preserves candle count',()=>{const v=view();const n=v.count;v.pan(-1e6);assert.equal(v.start,0);assert.equal(v.count,n);v.pan(1e6);assert.equal(v.start,1000-n);});
test('single candle is safe when zooming and panning',()=>{const v=view(1);v.zoom(.1);v.pan(10);assert.deepEqual(v.slice(),{start:0,end:1});});
test('empty initial data has an empty safe viewport',()=>{const v=view(0);v.zoom(2);assert.deepEqual(v.slice(),{start:0,end:0});});
test('latest follows the right edge after appending candles',()=>{const v=view();const n=v.count;v.setData(rows(1005),'XRP/OKX/1h');assert.equal(v.start+v.count,1005);assert.equal(v.count,n);});
test('a historical viewport remains anchored when new candles arrive',()=>{const v=view();v.pan(-300);const d=v.bars[v.start].date;v.setData(rows(1005),'XRP/OKX/1h');assert.equal(v.bars[v.start].date,d);});
test('rolling cache does not shift an existing historical anchor',()=>{const v=view();v.pan(-300);const d=v.bars[v.start].date;v.setData(rows(1000,5),'XRP/OKX/1h');assert.equal(v.bars[v.start].date,d);});
test('switching source or interval resets to the requested range',()=>{const v=view();v.zoom(.1);assert.equal(v.setData(rows(1000),'XRP/Yahoo/1h',7,3600),true);assert.equal(v.count,168);});
test('base gesture uses the initial viewport, without compounding zoom',()=>{const v=view();const base={start:v.start,count:v.count};v.zoom(.8,.5,base);v.zoom(.7,.5,base);assert.equal(v.count,Math.round(base.count*.7));});
test('irregular sessions use actual candle dates, not invented weekend bars',()=>{const v=new ChartViewport();const bars=[{date:'2026-01-02'},{date:'2026-01-05'},{date:'2026-01-06'}];v.setData(bars,'GOLD',1,86400);assert.deepEqual(v.slice(),{start:2,end:3});});
test('annotation validation rejects non-finite, negative and malformed prices/dates',()=>{const m={id:'a',kind:'point',points:[{date:'2026-01-01T00:00:00Z',price:1.123456789}]};assert.ok(validMark(m));for(const price of [NaN,Infinity,-1,0,'1'])assert.equal(validMark({...m,points:[{...m.points[0],price}]}),false);assert.equal(validMark({...m,points:[{date:'wrong',price:1}]}),false);assert.equal(validMark({...m,kind:'line'}),false);assert.equal(validMark({...m,kind:'script'}),false);});

test('CSV annotation namespace changes when middle data changes, not just dates or boundaries',()=>{const a=rows(400).map(r=>({...r,open:1,high:2,low:.5,close:1.5,volume:100}));const b=structuredClone(a);assert.equal(fingerprint(a),fingerprint(b));b[200].close=1.6;assert.notEqual(fingerprint(a),fingerprint(b));});
