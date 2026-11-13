/* Run in the generated synthetic fixture with preview_evaluate or a local browser.
   Intercepts downloads in memory so checks never write outside the workspace. */
(async()=>{
 const result=[];
 const check=(ok,name)=>{if(!ok)throw Error('Browser assertion failed: '+name);result.push(name);};
 const id=s=>document.getElementById(s);
 const nav=s=>document.querySelector(`[data-tab="${s}"]`).click();
 const rows=()=>[...document.querySelectorAll('#table tbody tr')];
 const fill=async(s,value)=>{id(s).value=value;id(s).dispatchEvent(new Event(id(s).tagName==='SELECT'||id(s).type==='time'?'change':'input',{bubbles:true}));await new Promise(r=>setTimeout(r,200));};
 nav('orders');check(document.querySelector('h1').textContent==='Requests & orders','visible section title updates');check(rows().length===50,'request pagination starts at 50 rows');
 id('next').click();check(id('page-number').value==='2','next page works');
 id('last').click();check(rows().length===26,'last page retains every request including reveal-only');
 id('first').click();
 await fill('search','Synthetic pickup note 124');check(rows().length===1,'request search finds original note');
 id('reset').click();await fill('order-filter','synthetic-000');check(rows().length===1,'request ID filter works');
 rows()[0].querySelector('button').click();check(id('detail').open,'request drilldown opens');
 check(id('detail-body').textContent.includes('Original request note'),'original notes available');
 check(id('detail-body').textContent.includes('Leg 1'),'leg history available');
 check(!globalThis.__xss && id('detail-body').querySelectorAll('img,script').length===0,'imported markup renders as inert text');
 id('close-detail').click();check(!id('detail').open,'dialog closes');
 id('reset').click();await fill('state','lost');check(id('row-count').textContent.startsWith('123 of'),'outcome filter includes all losses');
 nav('timeline');await fill('kind','future_kind');check(rows().length===1,'unknown event kinds are filterable');
 id('reset').click();await fill('order-filter','synthetic-000');check(rows().length>=3,'order reference filter works');
 id('reset').click();await fill('gig-filter','shared-gig');check(rows().length>=3,'gig reference filter works');
 id('reset').click();await fill('driver-filter','synthetic-driver');check(rows().length===3&&rows().some(r=>r.textContent.includes('roster')),'driver reference filter includes events and captured roster');
 id('reset').click();await fill('day','1');check(rows().length>0,'world day filter works');
 await fill('from','23:00');await fill('to','01:00');check(rows().every(row=>{const t=row.cells[0].textContent.split(' ').at(-1);return t>='23:00'||t<='01:00';}),'overnight clock filter works');
 nav('gigs');rows()[0].querySelector('button').click();check(id('detail-body').textContent.includes('Gig ledger net'),'gig accounting drilldown works');check(id('detail-body').textContent.includes('All schedule changes'),'fee schedule history available');id('close-detail').click();
 nav('drivers');check(rows().length===1,'observed drivers include captured profile');check(rows()[0].textContent.includes('4.8'),'roster facts shown only from capture');
 nav('incidents');check(rows().some(r=>r.textContent.includes('no show')),'incidents include no-show');
 nav('ledger');check(rows().length===2,'shared ledger charge counted once');check(rows().some(r=>r.textContent.includes('Not assigned')),'gig-only fee is not assigned to an order');
 document.querySelector('#table th:nth-child(3) button').click();check(rows()[0].textContent.includes('-€150.00'),'numeric sorting uses signed cents');
 nav('source');await fill('state','invalid or ambiguous');check(rows().length===1,'partial source line is inspectable');rows()[0].querySelector('button').click();check(id('detail-body').textContent.includes('incomplete'),'original partial text remains inspectable');id('close-detail').click();
 nav('captures');check(document.querySelectorAll('.map-svg circle').length===2,'captured coordinates render without external map tiles');
 const blobs=new Map(),downloads=[];const create=URL.createObjectURL,anchor=HTMLAnchorElement.prototype.click;
 URL.createObjectURL=function(blob){const url=create.call(URL,blob);blobs.set(url,blob);return url;};
 HTMLAnchorElement.prototype.click=function(){downloads.push({name:this.download,blob:blobs.get(this.href)});};
 try{
  id('export-source').click();check(downloads[0].name.endsWith('.jsonl'),'original source export uses download');
  const bytes=new Uint8Array(await downloads[0].blob.arrayBuffer()),original=Uint8Array.from(atob(JSON.parse(id('report-data').textContent).source.base64),c=>c.charCodeAt(0));
  check(bytes.length===original.length&&bytes.every((v,i)=>v===original[i]),'source download preserves every original byte');
  nav('timeline');await fill('kind','future_kind');id('export-filtered').click();const exported=JSON.parse(await downloads.at(-1).blob.text());check(exported.length===1&&exported[0].event.payload.unknown==='future-marker','filtered export preserves unknown nested fields');
  id('export-model').click();const model=JSON.parse(await downloads.at(-1).blob.text());check(model.records.length===JSON.parse(id('report-data').textContent).records.length,'complete JSON export retains every raw record');
 }finally{URL.createObjectURL=create;HTMLAnchorElement.prototype.click=anchor;for(const url of blobs.keys())URL.revokeObjectURL(url);}
 nav('overview');check(document.querySelectorAll('.chart').length===2,'financial and score charts render');
 check(!performance.getEntriesByType('resource').some(e=>/^https?:/.test(e.name)),'offline report loads no network resources');
 check(!globalThis.__xss,'script injection never executes');
 return {passed:result.length,checks:result};
})()
