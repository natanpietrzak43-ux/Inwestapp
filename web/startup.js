/* Diagnostics must run before chart.js/app.js so failed loads remain visible. */
(()=>{
 const expected=document.documentElement.dataset.uiVersion;
 const files=new Set(['startup.js','security.js','instruments.js','chart.js','education.js','app.js','workspace.js','bot.js','automation.js','coingecko.js']);
 let ready=false,health=false,failed=false,started=false,timer;
 function fail(message){failed=true;const box=document.getElementById('update-status');if(!box)return;box.classList.add('warning');document.getElementById('startup-state').textContent=message+' Uruchom Uruchom.bat z nowego, w całości rozpakowanego folderu i odśwież stronę przez Ctrl+F5.';}
 function show(){if(!failed&&ready&&health){document.getElementById('startup-state').textContent='Nowy wykres i wyjaśnienia „?” są wczytane.';document.getElementById('update-status').classList.remove('warning');document.getElementById('show-chart').disabled=false;document.getElementById('demo-chart').disabled=false;}}
 window.addEventListener('error',event=>{
  if(event.target?.tagName==='SCRIPT'){
   const file=new URL(event.target.src,location.href).pathname.split('/').pop();
   if(files.has(file))fail('Nie udało się wczytać modułu '+file+'.');
  }else if(!ready)fail('Nie udało się uruchomić interfejsu aplikacji.');
 },true);
 window.addEventListener('inwestapp:ready',()=>{ready=true;clearTimeout(timer);show();});
 async function start(){
  if(started)return;started=true;
  if(location.protocol==='file:'){fail('To plik HTML otwarty bez serwera.');return;}
  const control=new AbortController(),timeout=setTimeout(()=>control.abort(),5000);
  try{
   const response=await fetch('/api/health',{cache:'no-store',signal:control.signal});
   if(!response.ok)throw Error();const status=await response.json();
   const version=typeof status.version==='string'&&/^[0-9.]{1,20}$/.test(status.version)?status.version:'nieznana';
   document.getElementById('server-version').textContent=version;
   if(version!==expected){fail('Wersja serwera ('+version+') różni się od interfejsu ('+expected+').');return;}
   if(!Array.isArray(status.features)||!['interactive-chart','indicator-education','local-api-security'].every(f=>status.features.includes(f))){fail('Serwer nie potwierdza nowych funkcji wykresu.');return;}
   health=true;show();
  }catch{fail('Nie udało się potwierdzić wersji działającego serwera.');}
  finally{clearTimeout(timeout);}
 }
 document.addEventListener('DOMContentLoaded',()=>{start();timer=setTimeout(()=>{if(!ready&&!failed)fail('Moduły interfejsu nie zakończyły uruchamiania.');},6000);});
})();
