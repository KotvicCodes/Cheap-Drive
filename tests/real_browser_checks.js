/* Run against a report generated from the user's completed local level-4 trace.
   No fixture data or trace content is sent or downloaded by these assertions. */
(async()=>{
 const check=(ok,name)=>{if(!ok)throw Error('Real trace assertion failed: '+name);};
 const data=JSON.parse(document.getElementById('report-data').textContent);
 check(data.records.length===17909,'every source record retained');
 check(data.stats.price_request===1000,'1000 requests retained');
 check(data.stats.order_won===275&&data.stats.order_lost===725,'all observed outcomes retained');
 check(data.ledger.length===570,'all ledger entries retained');
 check(data.reconciliation.marginDifferenceCents===0&&data.reconciliation.revenueDifferenceCents===0,'exact financial reconciliation');
 check(data.reconciliation.recordedMarginCents===-1803000,'recorded margin is unchanged');
 const results=[];
 for(const tab of ['overview','orders','timeline','gigs','drivers','incidents','ledger','source','captures']){
  document.querySelector(`[data-tab="${tab}"]`).click();
  check(document.getElementById('title').textContent.length>0,'section renders '+tab);
  if(!['overview','captures'].includes(tab)){
   check(document.querySelectorAll('#table tbody tr').length>0,'rows render '+tab);
   document.getElementById('last').click();
   check(document.querySelectorAll('#table tbody tr').length>0,'last page renders '+tab);
   document.getElementById('first').click();
  }
  check(document.documentElement.scrollWidth<=innerWidth+1,'no page overflow '+tab);
  results.push(tab);
 }
 for(const tab of ['orders','gigs','drivers']){
  document.querySelector(`[data-tab="${tab}"]`).click();
  document.querySelector('#table tbody tr button').click();
  check(document.getElementById('detail').open,'entity opens '+tab);
  check(document.getElementById('detail-body').textContent.includes('Complete captured activity'),'history renders '+tab);
  document.getElementById('close-detail').click();
 }
 document.querySelector('[data-tab="timeline"]').click();
 const input=document.getElementById('search');input.value='R00003';input.dispatchEvent(new Event('input',{bubbles:true}));
 await new Promise(r=>setTimeout(r,200));
 check(document.querySelectorAll('#table tbody tr').length>0,'real order search works');
 check(!performance.getEntriesByType('resource').some(e=>/^https?:/.test(e.name)),'no network resources');
 document.querySelector('[data-tab="overview"]').click();
 return {sections:results,sourceRecords:data.records.length,requests:data.orders.length,timeline:data.timeline.length,ledger:data.ledger.length,exactReconciliation:true,width:innerWidth,version:data.version};
})()
