/* CSRF material lives only in this page's memory, never in URLs or localStorage. */
(()=>{
 'use strict';
 const original=window.fetch.bind(window);
 let session=null;
 async function token(){
  if(!session)session=original('/api/session',{headers:{'X-Inwestapp-Client':'browser'},cache:'no-store',credentials:'same-origin',redirect:'error'})
   .then(async r=>{if(!r.ok)throw Error('Nie potwierdzono bezpiecznej sesji. Odśwież stronę przez Ctrl+F5.');const s=await r.json();if(typeof s.csrfToken!=='string'||s.csrfToken.length<32)throw Error('Nieprawidłowa sesja aplikacji.');return s.csrfToken;})
   .catch(e=>{session=null;throw e;});
  return session;
 }
 window.fetch=async(input,options={})=>{
  const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
  if(url.origin!==location.origin)throw Error('Aplikacja nie wysyła żądań przeglądarki do obcych serwerów.');
  const method=(options.method||(input instanceof Request?input.method:'GET')).toUpperCase();
  if(url.pathname.startsWith('/api/')&&!['GET','HEAD'].includes(method)){
   const headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));
   headers.set('X-Inwestapp-Token',await token());
   return original(input,{...options,headers,credentials:'same-origin',redirect:'error'});
  }
  return original(input,{...options,credentials:'same-origin',redirect:'error'});
 };
})();
