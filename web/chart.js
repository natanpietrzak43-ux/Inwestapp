/* Local chart navigation and annotations. No market data or signal changes. */
(()=>{
 'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 // Stable namespace for CSV annotations; no raw imported file in storage keys.
 function fingerprint(rows){let a=2166136261,b=0x9e3779b9;for(const row of rows){const text=JSON.stringify([row.date,row.open,row.high,row.low,row.close,row.volume]);for(let i=0;i<text.length;i++){a=Math.imul(a^text.charCodeAt(i),16777619);b=Math.imul(b^text.charCodeAt(i),2246822519);}}return (a>>>0).toString(16)+'-'+(b>>>0).toString(16);}
 class ChartViewport{
  constructor(){this.key=null;this.bars=[];this.start=0;this.count=0;}
  setData(bars,key,days=7,seconds=3600){
   const previous=this.bars,oldDate=previous[this.start]?.date,atEnd=this.start+this.count>=previous.length;
   if(key===this.key&&bars===previous)return false;
   this.bars=bars;const changed=key!==this.key;this.key=key;
   if(changed||!previous.length)this.range(days,seconds);
   else{this.count=Math.min(bars.length,this.count);this.start=atEnd?bars.length-this.count:Math.max(0,bars.findIndex(b=>b.date>=oldDate));this.set(this.start,this.count);}
   return changed;
  }
  set(start,count){const n=this.bars.length;this.count=clamp(Math.round(count),Math.min(1,n),n);this.start=clamp(Math.round(start),0,n-this.count);}
  range(days,seconds){const n=this.bars.length;if(!n)return;const cut=Date.parse(this.bars[n-1].date)+seconds*1000-days*86400000;let first=this.bars.findIndex(b=>Date.parse(b.date)>=cut);if(first<0)first=n-1;this.set(first,n-first);}
  zoom(factor,anchor=.5,base=null){const v=base||this;const count=clamp(Math.round(v.count*factor),Math.min(8,this.bars.length,v.count),this.bars.length);const center=v.start+clamp(anchor,0,1)*v.count;this.set(center-clamp(anchor,0,1)*count,count);}
  pan(bars,base=null){const v=base||this;this.set(v.start+bars,v.count);}
  latest(){this.set(this.bars.length-this.count,this.count);}
  slice(){return {start:this.start,end:this.start+this.count};}
 }
 const precise=v=>Number.isFinite(v)?v.toLocaleString('pl-PL',{minimumFractionDigits:2,maximumFractionDigits:10}):'—';
 const when=date=>date.includes('T')?new Date(date).toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'shortOffset'}):new Date(date).toLocaleDateString('pl-PL',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit'})+' · D1';
 const node=(tag,attrs={},text)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;};
 const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function validMark(m){return m&&['point','level','line'].includes(m.kind)&&typeof m.id==='string'&&Array.isArray(m.points)&&m.points.length===(m.kind==='line'?2:1)&&m.points.every(p=>typeof p.date==='string'&&Number.isFinite(Date.parse(p.date))&&Number.isFinite(p.price)&&p.price>0);}
 class MarketChart{
  constructor({container,redraw}){
   this.container=container;this.redraw=redraw;this.view=new ChartViewport();this.marks=[];this.undoStack=[];this.mode='pan';this.pointers=new Map();this.cursor=null;this.pendingPoint=null;this.raf=0;
   this.tooltip=element('div',undefined,'chart-tooltip');this.tooltip.hidden=true;this.tooltip.setAttribute('role','tooltip');
   container.addEventListener('wheel',e=>this.wheel(e),{passive:false});
   container.addEventListener('pointerdown',e=>this.down(e));container.addEventListener('pointermove',e=>this.move(e));
   container.addEventListener('pointerup',e=>this.up(e));container.addEventListener('pointercancel',e=>this.up(e,true));
   container.addEventListener('pointerleave',()=>{if(!this.pointers.size)this.hideCursor();});
   container.addEventListener('lostpointercapture',e=>this.pointers.delete(e.pointerId));
   container.addEventListener('keydown',e=>this.keyboard(e));container.addEventListener('dblclick',()=>{if(this.mode==='pan')this.reset();});
   container.tabIndex=0;container.setAttribute('role','group');container.setAttribute('aria-describedby','chart-readout chart-message');container.setAttribute('aria-label','Interaktywny wykres. Strzałki: świece i przesuwanie. Plus/minus: zoom. Home: najnowsze. Escape: anuluj.');
   document.querySelectorAll('[data-chart-mode]').forEach(b=>b.onclick=()=>this.setMode(b.dataset.chartMode));
   document.getElementById('chart-zoom-in').onclick=()=>this.zoom(.7);
   document.getElementById('chart-zoom-out').onclick=()=>this.zoom(1/.7);
   document.getElementById('chart-reset').onclick=()=>this.reset();
   document.getElementById('chart-latest').onclick=()=>{this.view.latest();this.changed();};
   document.getElementById('chart-undo').onclick=()=>{if(this.undoStack.length){this.marks=this.undoStack.pop();this.save();this.changed();}};
   document.getElementById('chart-clear').onclick=()=>{if(this.marks.length){this.remember();this.marks=[];this.save();this.changed();}};
   let oldWidth=0,oldHeight=0;this.observer=new ResizeObserver(([entry])=>{const {width,height}=entry.contentRect;if(width>0&&height>0&&(Math.abs(width-oldWidth)>.5||Math.abs(height-oldHeight)>.5)){oldWidth=width;oldHeight=height;this.schedule();}});this.observer.observe(container);
  }
  setData(data,days,seconds){
   this.data=data;this.days=days;this.seconds=seconds;
   const csv=data.mode==='csv'?fingerprint(data.bars):null;
   const key=JSON.stringify([data.instrument.id,data.source,data.mode,data.currency,data.timeframe,csv]);
   if(this.view.setData(data.bars,key,days,seconds)){
    this.custom=false;this.storageKey='inwestapp.chart.marks.v1.'+key;this.marks=[];this.undoStack=[];this.pendingPoint=null;this.cursor=null;this.hideCursor();
    try{const saved=JSON.parse(localStorage.getItem(this.storageKey)||'[]');if(Array.isArray(saved))this.marks=saved.filter(validMark).slice(0,50);}catch{}
   }
  }
  range(days){this.custom=false;this.days=days;this.view.range(days,this.seconds);this.cursor=null;this.changed();}
  setMode(mode){this.mode=mode;this.pendingPoint=null;document.querySelectorAll('[data-chart-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.chartMode===mode)));this.container.dataset.mode=mode;this.message(mode==='line'?'Kliknij początek, a potem koniec linii.':mode==='pan'?'Przeciągnij wykres, aby zobaczyć starsze świece.':'Kliknij wykres, aby zaznaczyć cenę i czas.');this.schedule();}
  message(text){document.getElementById('chart-message').textContent=text;}
  schedule(){if(!this.raf)this.raf=requestAnimationFrame(()=>{this.raf=0;if(this.data)this.redraw();});}
  changed(){this.cursor=null;this.hideCursor();this.schedule();}
  reset(){if(!this.data)return;this.custom=false;this.view.range(this.days,this.seconds);this.changed();}
  zoom(factor,anchor=.5,base=null){if(!this.data)return;this.custom=true;this.view.zoom(factor,anchor,base);this.changed();}
  remember(){this.undoStack.push(JSON.parse(JSON.stringify(this.marks)));if(this.undoStack.length>20)this.undoStack.shift();}
  save(){try{localStorage.setItem(this.storageKey,JSON.stringify(this.marks));this.message('Oznaczenia zapisane w tej przeglądarce.');}catch{this.message('Brak dostępu do pamięci przeglądarki — oznaczenia działają tylko w tej sesji.');}}
  attach(frame,rows,inds,offset){
   this.frame=frame;this.rows=rows;this.inds=inds;this.offset=offset;
   const {svg}=frame;this.layer=node('g',{'pointer-events':'none','data-chart-overlay':'true'});svg.append(this.layer);this.drawMarks();
   this.cross=node('g',{visibility:'hidden','pointer-events':'none'});this.v=node('line',{class:'crosshair-line'});this.h=node('line',{class:'crosshair-line'});
   this.tag=node('g');this.tagBox=node('rect',{class:'crosshair-label',rx:3});this.tagText=node('text',{class:'crosshair-text'});this.tag.append(this.tagBox,this.tagText);
   this.timeTag=node('g');this.timeBox=node('rect',{class:'crosshair-label',rx:3});this.timeText=node('text',{class:'crosshair-text','text-anchor':'middle'});this.timeTag.append(this.timeBox,this.timeText);
   this.cross.append(this.v,this.h,this.tag,this.timeTag);svg.append(this.cross);this.container.append(this.tooltip);
   if(this.cursor)this.showCursor(this.cursor.index,this.cursor.price);
   document.querySelectorAll('[data-range]').forEach(b=>b.classList.toggle('selected',!this.custom&&Number(b.dataset.range)===this.days));this.renderMarks();const n=this.view.bars.length;document.getElementById('chart-zoom-in').disabled=this.view.count<=Math.min(8,n);document.getElementById('chart-zoom-out').disabled=this.view.count>=n;
   document.getElementById('chart-undo').disabled=!this.undoStack.length;document.getElementById('chart-clear').disabled=!this.marks.length;
  }
  coords(e){
   if(!this.frame)return null;const matrix=this.frame.svg.getScreenCTM();if(!matrix)return null;
   const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse()),f=this.frame;
   const inside=p.x>=f.pad.l&&p.x<=f.width-f.pad.r&&p.y>=f.pad.t&&p.y<=f.height-f.pad.b;
   const ratio=clamp((p.x-f.pad.l)/f.plotW,0,1),index=clamp(Math.floor(ratio*this.rows.length),0,this.rows.length-1);
   return {...p,x:p.x,y:p.y,inside,ratio,index,price:f.max-(clamp(p.y,f.pad.t,f.height-f.pad.b)-f.pad.t)/f.plotH*(f.max-f.min)};
  }
  wheel(e){const p=this.coords(e);if(!p?.inside)return;e.preventDefault();this.zoom(Math.exp(clamp(e.deltaY,-150,150)*.003),p.ratio);}
  down(e){
   if(e.button!==0)return;const p=this.coords(e);if(!p?.inside)return;this.container.focus({preventScroll:true});this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});this.container.setPointerCapture(e.pointerId);
   if(this.pointers.size===2){const [a,b]=[...this.pointers.values()];this.gesture={distance:Math.hypot(a.x-b.x,a.y-b.y),base:{start:this.view.start,count:this.view.count},anchor:this.coords({clientX:(a.x+b.x)/2,clientY:(a.y+b.y)/2}).ratio};this.drag=null;}
   else if(this.pointers.size===1)this.drag={id:e.pointerId,x:e.clientX,y:e.clientY,base:{start:this.view.start,count:this.view.count},point:p,moved:false};
   this.showCursor(p.index,p.price);
  }
  move(e){
   document.getElementById('chart-readout').setAttribute('aria-live','off');
   const p=this.coords(e);if(!p)return;
   if(this.pointers.has(e.pointerId))this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
   if(this.pointers.size>=2&&this.gesture){const [a,b]=[...this.pointers.values()];const dist=Math.hypot(a.x-b.x,a.y-b.y);if(dist>0&&this.gesture.distance>0)this.zoom(this.gesture.distance/dist,this.gesture.anchor,this.gesture.base);return;}
   if(this.drag&&this.drag.id===e.pointerId){const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;if(Math.hypot(dx,dy)>4)this.drag.moved=true;if(this.mode==='pan'&&this.drag.moved){const matrix=this.frame.svg.getScreenCTM();this.custom=true;this.view.pan(-dx/(this.frame.plotW*matrix.a)*this.drag.base.count,this.drag.base);this.changed();return;}}
   if(p.inside)this.showCursor(p.index,p.price);else if(!this.pointers.size)this.hideCursor();
  }
  up(e,cancel=false){
   const p=this.coords(e),drag=this.drag;
   if(!cancel&&drag&&drag.id===e.pointerId&&!drag.moved&&this.pointers.size===1&&p?.inside&&this.mode!=='pan')this.addPoint(p);
   this.pointers.delete(e.pointerId);if(this.container.hasPointerCapture(e.pointerId))this.container.releasePointerCapture(e.pointerId);
   this.drag=null;this.gesture=null;
  }
  addPoint(p){
   if(p.price<=0){this.message('Punkt odniesienia wymaga dodatniej ceny.');return;}
   if(this.marks.length>=50){this.message('Limit 50 oznaczeń. Usuń niepotrzebne punkty.');return;}
   const point={date:this.rows[p.index].date,price:p.price};
   if(this.mode==='line'&&!this.pendingPoint){this.pendingPoint=point;this.message('Początek zaznaczony. Kliknij koniec linii. Escape anuluje.');this.schedule();return;}
   this.remember();this.marks.push({id:crypto.randomUUID(),kind:this.mode,points:this.mode==='line'?[this.pendingPoint,point]:[point]});this.pendingPoint=null;this.save();this.schedule();
  }
  pointPosition(point){const index=this.rows.findIndex(r=>r.date===point.date);return index<0?null:{x:this.frame.x(index),y:this.frame.y(point.price)};}
  drawMarks(){
   const f=this.frame;
   const clipId='chart-mark-clip';const defs=node('defs'),clip=node('clipPath',{id:clipId});clip.append(node('rect',{x:f.pad.l,y:f.pad.t,width:f.plotW,height:f.plotH}));defs.append(clip);this.layer.append(defs);const plot=node('g',{'clip-path':`url(#${clipId})`});this.layer.append(plot);
   this.marks.forEach((m,i)=>{
    if(m.kind==='level'){const yy=f.y(m.points[0].price);plot.append(node('line',{x1:f.pad.l,x2:f.width-f.pad.r,y1:yy,y2:yy,class:'reference-line'}),node('text',{x:f.pad.l+5,y:yy-5,class:'reference-text'},`#${i+1} · ${precise(m.points[0].price)}`));}
    else if(m.kind==='line'){
     // Find global indices so a segment remains visible if either end is offscreen.
     const points=m.points.map(p=>{const index=this.view.bars.findIndex(r=>r.date===p.date);return index<0?null:{x:f.x(index-this.offset),y:f.y(p.price)};});
     if(points.every(Boolean))plot.append(node('line',{x1:points[0].x,x2:points[1].x,y1:points[0].y,y2:points[1].y,class:'reference-line'}));
    }else{const p=this.pointPosition(m.points[0]);if(p)plot.append(node('circle',{cx:p.x,cy:p.y,r:5,class:'reference-point'}),node('text',{x:p.x+8,y:p.y-8,class:'reference-text'},`#${i+1}`));}
   });
   if(this.pendingPoint){const p=this.pointPosition(this.pendingPoint);if(p)plot.append(node('circle',{cx:p.x,cy:p.y,r:6,class:'reference-point'}));}
  }
  renderMarks(){
   const list=document.getElementById('chart-markers');list.replaceChildren();document.getElementById('chart-marker-count').textContent=String(this.marks.length);
   this.marks.forEach((m,i)=>{const row=element('div',undefined,'reference-row');const description=m.points.map(p=>precise(p.price)+' '+this.data.currency+' · '+when(p.date)).join(' → ');row.append(element('span',`#${i+1} · ${{point:'Punkt',level:'Poziom',line:'Linia'}[m.kind]} · ${description}`));const go=element('button','Pokaż','button secondary');go.type='button';go.onclick=()=>{const index=this.view.bars.findIndex(b=>b.date===m.points[0].date);if(index<0){this.message('Punkt jest poza aktualnie pobraną historią.');return;}this.custom=true;this.view.set(index-this.view.count/2,this.view.count);this.changed();};const remove=element('button','Usuń','button secondary');remove.type='button';remove.setAttribute('aria-label','Usuń oznaczenie '+(i+1));remove.onclick=()=>{this.remember();this.marks=this.marks.filter(r=>r.id!==m.id);this.save();this.changed();};row.append(go,remove);list.append(row);});
   if(!this.marks.length)list.append(element('p','Nie ma jeszcze punktów ani linii. Wybierz narzędzie nad wykresem i kliknij wykres.','fine'));
   const points=this.marks.flatMap(m=>m.kind==='point'?m.points:[]).slice(-2);const measure=document.getElementById('chart-measure');
   if(points.length===2){const delta=points[1].price-points[0].price,minutes=Math.abs(Date.parse(points[1].date)-Date.parse(points[0].date))/60000;measure.textContent=`Ostatnie dwa punkty: ${delta>=0?'+':''}${precise(delta)} ${this.data.currency} (${(delta/points[0].price*100).toLocaleString('pl-PL',{maximumFractionDigits:4})}%) · odstęp ${minutes.toLocaleString('pl-PL')} min. To pomiar między wskazanymi cenami.`;}else measure.textContent='Dodaj dwa punkty, aby zmierzyć zmianę ceny i odstęp czasu.';
  }
  hideCursor(){this.cursor=null;if(this.cross)this.cross.setAttribute('visibility','hidden');this.tooltip.hidden=true;document.getElementById('chart-readout').textContent='Najedź na wykres lub dotknij go, aby odczytać cenę i czas świecy.';}
  showCursor(index,value){
   if(!this.frame||!this.rows.length)return;const f=this.frame;index=clamp(index,0,this.rows.length-1);const row=this.rows[index];const yy=clamp(f.y(value),f.pad.t,f.height-f.pad.b),xx=f.x(index);this.cursor={index,price:value};
   this.cross.setAttribute('visibility','visible');for(const[k,v]of Object.entries({x1:xx,x2:xx,y1:f.pad.t,y2:f.height-f.pad.b}))this.v.setAttribute(k,v);for(const[k,v]of Object.entries({x1:f.pad.l,x2:f.width-f.pad.r,y1:yy,y2:yy}))this.h.setAttribute(k,v);
   const label=precise(value);this.tagBox.setAttribute('x',f.width-f.pad.r+2);this.tagBox.setAttribute('y',yy-11);this.tagBox.setAttribute('width',f.pad.r-3);this.tagBox.setAttribute('height',22);this.tagText.setAttribute('x',f.width-f.pad.r+7);this.tagText.setAttribute('y',yy+4);this.tagText.textContent=label;
   const time=when(row.date),tw=Math.min(f.plotW,245),tx=clamp(xx,f.pad.l+tw/2,f.width-f.pad.r-tw/2);this.timeBox.setAttribute('x',tx-tw/2);this.timeBox.setAttribute('y',f.height-f.pad.b+5);this.timeBox.setAttribute('width',tw);this.timeBox.setAttribute('height',24);this.timeText.setAttribute('x',tx);this.timeText.setAttribute('y',f.height-f.pad.b+21);this.timeText.textContent=time;
   const readout=document.getElementById('chart-readout');readout.textContent=`Kursor: ${label} ${this.data.currency} · świeca ${time} · O ${precise(row.open)} · H ${precise(row.high)} · L ${precise(row.low)} · C ${precise(row.close)}`;
   this.tooltip.replaceChildren(element('strong',`Cena kursora: ${label} ${this.data.currency}`),element('span',(row.date.includes('T')?'Otwarcie świecy: ':'Data świecy dziennej: ')+time),element('span',`O ${precise(row.open)} · H ${precise(row.high)}`),element('span',`L ${precise(row.low)} · C ${precise(row.close)}`),element('span','Wolumen: '+precise(row.volume)));
   const ind=this.inds[index];for(const key of this.data.selectedTools){const values={ema:[['EMA20','ema20'],['EMA50','ema50'],['EMA200','ema200']],ema_mercado:[['M1','emaM1'],['M2','emaM2'],['M3','emaM3']],rsi:[['RSI14','rsi']],adx:[['ADX14','adx']],bxtrender:[['B-X krótki','bxShort'],['B-X długi','bxLong']]}[key];if(values)this.tooltip.append(element('span',values.map(([name,k])=>name+' '+precise(ind[k])).join(' · ')));}
   this.tooltip.hidden=false;const box=this.tooltip.getBoundingClientRect(),rect=this.container.getBoundingClientRect(),client=new DOMPoint(xx,yy).matrixTransform(f.svg.getScreenCTM()),px=client.x-rect.left,py=client.y-rect.top;const x=px+15+box.width>rect.width?px-box.width-15:px+15;this.tooltip.style.left=clamp(x,5,Math.max(5,rect.width-box.width-5))+'px';this.tooltip.style.top=clamp(py+15,5,Math.max(5,rect.height-box.height-5))+'px';
  }
  keyboard(e){
   if(!this.rows?.length)return;const f=this.frame;let index=this.cursor?.index??this.rows.length-1;let value=this.cursor?.price??this.rows[index].close;
   if((e.key==='Enter'||e.key===' ')&&this.mode!=='pan'){e.preventDefault();this.addPoint({index,price:value});return;}
   document.getElementById('chart-readout').setAttribute('aria-live','polite');
   if(['+','=','-','Home','Escape','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();else return;
   if(e.key==='+'||e.key==='=')return this.zoom(.7);if(e.key==='-')return this.zoom(1/.7);if(e.key==='Home'){this.view.latest();return this.changed();}
   if(e.key==='Escape'){this.pendingPoint=null;this.setMode('pan');this.hideCursor();return;}
   if(e.key==='ArrowUp')value+=(f.max-f.min)/f.plotH;if(e.key==='ArrowDown')value-=(f.max-f.min)/f.plotH;
   if(e.key==='ArrowLeft'||e.key==='ArrowRight'){const d=e.key==='ArrowLeft'?-1:1;index+=d;if(index<0||index>=this.rows.length){const global=clamp(this.offset+index,0,this.view.bars.length-1);this.custom=true;this.view.pan(d);this.cursor=null;this.redraw();index=clamp(global-this.offset,0,this.rows.length-1);}value=this.rows[index].close;}
   this.showCursor(index,clamp(value,this.frame.min,this.frame.max));
  }
 }
 if(typeof module!=='undefined')module.exports={ChartViewport,validMark,fingerprint};
 if(typeof window!=='undefined'){window.ChartViewport=ChartViewport;window.MarketChart=MarketChart;MarketChart.precise=precise;}
})();
