/* Run against a report generated from a completed local trace.
   No fixture data or trace content is sent or downloaded by these assertions. */
(async()=>{
 const check=(ok,name)=>{if(!ok)throw Error('Real trace assertion failed: '+name);};
 const data=JSON.parse(document.getElementById('report-data').textContent);
 check(data.records.length===data.source.lines&&data.records.length>0,'every source record retained');
 check(data.integrity.verifiedEnd&&data.integrity.finalScoreCaptured,'completed trace with a final score');
 const source=Uint8Array.from(atob(data.source.base64),c=>c.charCodeAt(0));
 check(source.length===data.source.bytes,'source byte count retained');
 const hash=await crypto.subtle.digest('SHA-256',source);
 check([...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('')===data.source.sha256,'source fingerprint retained');
 check(data.reconciliation.status==='matches'&&data.reconciliation.marginDifferenceCents===0&&data.reconciliation.revenueDifferenceCents===0,'exact financial reconciliation');
 const results=[];
 for(const tab of ['overview','orders','timeline','gigs','drivers','incidents','ledger','source','captures']){
  document.querySelector(`[data-tab="${tab}"]`).click();
  check(document.getElementById('title').textContent.length>0,'section renders '+tab);
  if(!['overview','captures'].includes(tab)){
   const count=document.querySelectorAll('#table tbody tr').length;
   check(count>0||!document.getElementById('empty').hidden,'rows or empty state render '+tab);
   document.getElementById('last').click();
   check(count===0||document.querySelectorAll('#table tbody tr').length>0,'last page renders '+tab);
   document.getElementById('first').click();
  }
  check(document.documentElement.scrollWidth<=innerWidth+1,'no page overflow '+tab);
  results.push(tab);
 }
 for(const tab of ['orders','gigs','drivers']){
  document.querySelector(`[data-tab="${tab}"]`).click();
  const first=document.querySelector('#table tbody tr button');
  if(!first)continue;
  first.click();
  check(document.getElementById('detail').open,'entity opens '+tab);
  check(document.getElementById('detail-body').textContent.includes('Complete captured activity'),'history renders '+tab);
  document.getElementById('close-detail').click();
 }
 document.querySelector('[data-tab="timeline"]').click();
 const order=data.orders.find(o=>o.history.length);
 const input=document.getElementById('search');input.value=order?.id||'';input.dispatchEvent(new Event('input',{bubbles:true}));
 await new Promise(r=>setTimeout(r,200));
 check(!order||document.querySelectorAll('#table tbody tr').length>0,'real order search works');
 check(!performance.getEntriesByType('resource').some(e=>/^https?:/.test(e.name)),'no network resources');
 document.querySelector('[data-tab="overview"]').click();
 return {sections:results,sourceRecords:data.records.length,requests:data.orders.length,timeline:data.timeline.length,ledger:data.ledger.length,exactReconciliation:true,width:innerWidth,version:data.version};
})()
