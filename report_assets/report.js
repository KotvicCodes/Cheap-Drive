'use strict';
const D = JSON.parse(document.getElementById('report-data').textContent);
const $ = id => document.getElementById(id);
const N = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined && text !== null) e.textContent = String(text); if (cls) e.className = cls; return e; };
const add = (parent, ...children) => { for (const child of children.flat()) if (child !== undefined && child !== null) parent.append(child instanceof Node ? child : document.createTextNode(String(child))); return parent; };
const clear = e => e.replaceChildren();
const arr = value => Array.isArray(value) ? value : [];
const fmt = n => Number.isFinite(n) ? new Intl.NumberFormat('en-IE', {style:'currency', currency:'EUR'}).format(n/100) : 'Unavailable';
const num = n => new Intl.NumberFormat('en-IE').format(n || 0);
const pct = n => Number.isFinite(n) ? (n*100).toFixed(1)+'%' : 'Unavailable';
const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const dayName = d => `Day ${d+1} · ${days[((d%7)+7)%7]}`;
const time = at => Number.isInteger(at) ? `${dayName(Math.floor(at/1440))} ${String(Math.floor(((at%1440)+1440)%1440/60)).padStart(2,'0')}:${String(((at%60)+60)%60).padStart(2,'0')}` : 'Time not captured';
const human = s => String(s || 'unknown').replaceAll('_',' ');
const badge = (text, tone='') => N('span', human(text), 'badge '+tone);
const button = (text, fn, cls='') => { const b=N('button',text,cls); b.type='button'; b.addEventListener('click', fn); return b; };
const pre = value => N('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2));
const details = (label, value, open=false) => { const d=N('details'); d.open=open; return add(d,N('summary',label),pre(value)); };
const lineButton = line => button('L'+line,()=>rawDetail(line),'link');
const getEntity = (kind,id) => D[{order:'orders',gig:'gigs',driver:'drivers'}[kind]].find(x=>x.id===id);
const entityButton = (kind,id) => button(id,()=>entityDetail(kind,id),'link');
const refCell = (kind,ids) => {const list=add(N('div',null,'cell-stack'),ids.length?ids.map(id=>entityButton(kind,id)):N('span','Not captured','muted'));if(ids.length<=4)return list;const group=N('details');add(group,N('summary',num(ids.length)+' '+kind+' references'),list);return group;};
const recorded = [...D.scores].reverse().find(s=>s.final)?.score || {};
const R = D.reconciliation;
let active='overview', filtered=[], page=0, size=50, sortKey='', direction=1, debounce;
let currentRows=[], columns=[];
const lookup={order:new Map(D.orders.map(x=>[x.id,x])),gig:new Map(D.gigs.map(x=>[x.id,x])),driver:new Map(D.drivers.map(x=>[x.id,x]))};
const activity = entity => entity.history.map(i=>D.timeline[i]);
const firstAt = entity => activity(entity).find(x=>Number.isInteger(x.at))?.at ?? null;
const eventOf = row => row.event || row.action || {};
const payload = row => row.event || (row.action ? {action:row.action,result:row.result} : D.records[row.line-1]?.value);
const eventSummary = row => {
 const v=eventOf(row);
 if(row.action) return row.status + (row.result?.reason ? ': '+row.result.reason : '') + (v.prices ? ' · '+Object.entries(v.prices).map(([k,n])=>human(k)+' '+fmt(n)).join(', ') : '');
 if(v.line) return fmt(v.line.cents)+' · '+human(v.line.kind)+' · '+(v.line.detail || '');
 return v.message?.text || v.reason || v.text || (v.leg !== undefined ? `Leg ${v.leg+1} · ${v.placeId || ''}` : '') || (v.feeCents !== undefined ? fmt(v.feeCents) : '') || v.request?.note?.text || v.order?.option || '';
};
function download(name, value, type='application/json'){
 const bytes = value instanceof Uint8Array ? value : typeof value === 'string' ? value : JSON.stringify(value,null,2);
 const url=URL.createObjectURL(new Blob([bytes],{type})); const a=N('a'); a.href=url; a.download=name; document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),30000);
}
let sourceBytes;
function source(){ if(!sourceBytes){const s=atob(D.source.base64); sourceBytes=Uint8Array.from(s,c=>c.charCodeAt(0));} return sourceBytes; }
$('export-source').onclick=()=>download('cheap-drive-original.jsonl',source(),'application/octet-stream');
$('export-model').onclick=()=>download('cheap-drive-analysis.json',D);
$('version').textContent=`Report v${D.version} · ${num(D.source.lines)} source records`;
$('run-label').textContent=`${D.run.level !== undefined ? 'Level '+D.run.level+' · ' : ''}Captured week · ${num(D.stats.price_request)} request events`;
$('mode').textContent=D.run.mode==='demo'?'SYNTHETIC DEMO':D.run.mode==='practice'?'PRACTICE TRACE':'IMPORTED TRACE';
$('mode').classList.add(D.run.mode==='demo'?'warn':'good');
const btext=N('span');
add(btext,N('strong','100% of supplied bytes retained'),` · ${num(D.source.bytes)} bytes · ${D.integrity.invalidLines ? num(D.integrity.invalidLines)+' invalid or ambiguous lines' : 'every source line inspectable'} · ${D.integrity.verifiedEnd?'end snapshot verified':'simulated-week completion unverified'}`);
add($('integrity-banner'),btext,button(`${num(D.diagnostics.length)} diagnostics →`,()=>navigate('source')));
const nav=[['overview','Overview',null],['orders','Requests & orders',D.orders.length],['timeline','Event timeline',D.timeline.length],['gigs','Gigs & stops',D.gigs.length],['drivers','Drivers',D.drivers.length],['incidents','Incidents',D.timeline.filter(x=>x.incident || x.status==='rejected' || x.conflict).length],['ledger','Financial ledger',D.ledger.length],['source','Source & integrity',D.source.lines],['captures','Captured context',null]];
for(const [id,label,count] of nav){const b=button('',()=>navigate(id));b.dataset.tab=id;add(b,N('span',label),count===null?null:N('span',num(count)));$('nav').append(b);}
function section(title,subtitle){const panel=N('section',null,'panel');const header=N('div',null,'panel-header');const t=N('div');add(t,N('h2',title),subtitle?N('p',subtitle):null);add(header,t);panel.append(header);return panel;}
function metric(label,value,note,cls=''){const e=N('div',null,'metric '+cls);add(e,N('div',label,'metric-label'),N('div',value,'metric-value '+(typeof value==='string'&&value.startsWith('-')?'negative':'')),N('small',note));return e;}
function svg(tag,attrs={}){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}
function chart(series, title){
 const chart=svg('svg',{viewBox:'0 0 800 244',class:'chart',role:'img','aria-label':title,preserveAspectRatio:'none'});add(chart,svg('title'));chart.firstChild.textContent=title;
 const points=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p[0])&&Number.isFinite(p[1]));
 if(!points.length){const t=svg('text',{x:70,y:100});t.textContent='No financial observations captured';chart.append(t);return chart;}
 let xmin=Math.min(0,...points.map(p=>p[0])), xmax=Math.max(1440,...points.map(p=>p[0]));
 const vals=points.map(p=>p[1]);let ymin=Math.min(0,...vals),ymax=Math.max(0,...vals);if(ymax===ymin)ymax=ymin+100;
 const x=n=>65+(n-xmin)/(xmax-xmin)*714,y=n=>204-(n-ymin)/(ymax-ymin)*184;
 for(let i=0;i<=4;i++){const value=ymin+(ymax-ymin)*i/4;chart.append(svg('line',{x1:65,x2:779,y1:y(value),y2:y(value)}));const t=svg('text',{x:57,y:y(value)+3,'text-anchor':'end'});t.textContent=(value/100/1000).toFixed(1)+'k €';chart.append(t);}
 const step=Math.max(1,Math.ceil((xmax/1440)/9));for(let d=0;d<=xmax/1440;d+=step){const t=svg('text',{x:x(d*1440),y:232,'text-anchor':d===0?'start':'middle'});t.textContent='D'+(d+1);chart.append(t);}
 for(const s of series){const pts=s.points.filter(p=>Number.isFinite(p[0])&&Number.isFinite(p[1]));if(!pts.length)continue;const path=pts.map((p,i)=>(i?'L':'M')+x(p[0]).toFixed(2)+','+y(p[1]).toFixed(2)).join(' ');const p=svg('path',{d:path,stroke:s.color});if(s.dashed)p.setAttribute('stroke-dasharray','5 5');chart.append(p);}
 return chart;
}
function bars(parent, entries, money=false){const max=Math.max(1,...entries.map(x=>Math.abs(x.value)));for(const item of entries){const track=N('div',null,'bar-track');const fill=N('div',null,'bar-fill');fill.style.width=(Math.abs(item.value)/max*100)+'%';fill.style.background=item.color;track.append(fill);add(parent,add(N('div',null,'bar-row'),N('span',item.label),track,N('span',money?fmt(item.value):num(item.value),'bar-value')));}}
function overview(){
 const root=$('overview');clear(root);
 if(D.run.mode==='demo')root.append(N('p','Synthetic scripted walkthrough. These values are not simulator performance.','notice'));
 const metrics=N('div',null,'metrics');
 add(metrics,metric('Recorded final margin',fmt(recorded.marginCents),'Ledger net '+fmt(R.ledgerMarginCents)+' · '+human(R.status),'accent'),metric('Recorded revenue',fmt(recorded.revenueCents),'Ledger revenue '+fmt(R.ledgerRevenueCents)),metric('On-time delivery',pct(recorded.onTimeShare),pct(recorded.undeliveredShare)+' undelivered · recorded score'),metric('Recorded won orders',recorded.wonOrders===undefined?'Unavailable':num(recorded.wonOrders),num(D.stats.order_won)+' win events · '+num(D.stats.order_cancelled)+' cancellations'));
 root.append(metrics);
 let net=0,rev=0,cost=0;const netPts=[[0,0]],revPts=[[0,0]],costPts=[[0,0]];
 for(const l of D.ledger){net+=l.cents;if(l.kind==='revenue')rev+=l.cents;else cost+=l.cents;if(Number.isInteger(l.at)){netPts.push([l.at,net]);revPts.push([l.at,rev]);costPts.push([l.at,cost]);}}
 const grid=N('div',null,'grid2'),finance=section('The financial week','Cumulative recorded ledger, in chronological world time. No estimated costs.');
 finance.append(chart([{points:revPts,color:'#66d7b5'},{points:costPts,color:'#ff7c85'},{points:netPts,color:'#8cb9ff'}],'Cumulative ledger revenue, other entries and net margin'));
 const legend=N('div',null,'legend');for(const [label,color] of [['Revenue','#66d7b5'],['Fees, refunds & other','#ff7c85'],['Net margin','#8cb9ff']]){const s=N('span',label);s.style.setProperty('--legend',color);legend.append(s);}finance.append(legend);
 const flow=section('Request funnel','Observed outcomes. Missing quotes are not inferred as unquoted.');bars(flow,[{label:'Requests',value:D.stats.price_request||0,color:'#8cb9ff'},{label:'Won',value:D.stats.order_won||0,color:'#66d7b5'},{label:'Lost',value:D.stats.order_lost||0,color:'#ff7c85'},{label:'Cancelled',value:D.stats.order_cancelled||0,color:'#f4c779'}]);
 const breakdown=N('div',null,'breakdown');add(breakdown,add(N('div'),N('strong',num(D.orders.filter(o=>(o.data.quotes||[]).length).length)),N('span','requests with captured quote results')),add(N('div'),N('strong',num(D.orders.filter(o=>o.data.reveal?.outcome==='unquoted').length)),N('span','confirmed unquoted in reveal')));add(flow,breakdown,button('Explore requests →',()=>navigate('orders'),'link'));add(grid,finance,flow);root.append(grid);
 const grid2=N('div',null,'grid2'),daily=section('Recorded score checkpoints','Daily and final observations, separate from reconstructed ledger totals.');
 const scorePoints=D.scores.filter(x=>Number.isInteger(x.at)).map(x=>[x.at,x.score.marginCents]);
 if(D.scores.some(x=>!Number.isInteger(x.at)))daily.append(N('p','Score records without a world minute are shown in metrics and raw source, without an invented time on this chart.','small'));
 daily.append(chart([{points:scorePoints,color:'#f4c779',dashed:true}], 'Recorded margin at score checkpoints'));
 const accounting=section('Where the money went','Signed ledger entries. All amounts are counted once.');bars(accounting,Object.entries(R.totals).map(([label,value])=>({label:human(label),value,color:value<0?'#ff7c85':'#66d7b5'})),true);add(accounting,button('Open complete ledger →',()=>navigate('ledger'),'link'));add(grid2,daily,accounting);root.append(grid2);
 const bottom=N('div',null,'grid2'),health=section('Reliability & exceptions','Event counts, not distinct orders or drivers.');bars(health,['deadline_close','gig_dropped','no_show','driver_late','visit_failed','gig_expired'].map(k=>({label:human(k),value:D.stats[k]||0,color:'#f4c779'})));health.append(button('Inspect incidents →',()=>navigate('incidents'),'link'));
 const check=section('Reconciliation','Recorded final score versus captured ledger.');const table=N('table',null,'mini-table');const head=N('tr');add(head,N('th','Metric'),N('th','Recorded / ledger / difference'));table.append(head);for(const [label,a,b,diff] of [['Margin',recorded.marginCents,R.ledgerMarginCents,R.marginDifferenceCents],['Revenue',recorded.revenueCents,R.ledgerRevenueCents,R.revenueDifferenceCents]])add(table,add(N('tr'),N('td',label),N('td',fmt(a)+' / '+fmt(b)+' / '+fmt(diff))));add(check,badge(R.status,R.status==='matches'?'good':'warn'),table,N('p','Direct order entries '+fmt(R.attribution.directOrderCents||0)+'. Gig-only entries '+fmt(R.attribution.gigOnlyCents||0)+'. Unattributed entries '+fmt(R.attribution.unattributedCents||0)+'. Gig-only costs remain separate from order net figures.','small'),N('p',recorded.ranked===true?'Recorded score: ranked.':recorded.ranked===false?'Recorded score: not ranked.':'Ranked status unavailable.','small'));add(bottom,health,check);root.append(bottom);
}
const entityRefs=(kind,e)=>({order:kind==='order'?[e.id]:(kind==='gig'?e.related:[]),gig:kind==='gig'?[e.id]:(kind==='order'?e.related:activity(e).flatMap(x=>x.refs.gig)),driver:kind==='driver'?[e.id]:activity(e).flatMap(x=>x.refs.driver)});
const cache=new Map();
function searchText(row){const key=active+':'+(row.id??row.line??row.sourceLine);if(cache.has(key))return cache.get(key);const data=active==='orders'||active==='gigs'||active==='drivers'?{entity:row,activity:activity(row).map(payload)}:active==='source'?{...row,original:new TextDecoder().decode(source().subarray(row.offset,row.offset+row.length))}:row;const s=JSON.stringify(data).toLowerCase();cache.set(key,s);return s;}
const col=(key,title,value,render,cls='')=>({key,title,value,render,cls});
const colsTimeline=[col('at','World time',x=>x.at,x=>time(x.at)),col('kind','Kind',x=>x.kind,x=>badge(x.kind,x.conflict?'bad':x.incident?'warn':'')),col('order','Order / request',x=>x.refs.order.join(),x=>refCell('order',x.refs.order)),col('gig','Gig',x=>x.refs.gig.join(),x=>refCell('gig',x.refs.gig)),col('driver','Driver',x=>x.refs.driver.join(),x=>refCell('driver',x.refs.driver)),col('detail','Captured detail',eventSummary,x=>N('span',eventSummary(x)),'wrap'),col('line','Source',x=>x.line,x=>lineButton(x.line))];
function configure(id){
 if(id==='timeline'||id==='incidents'){currentRows=id==='incidents'?D.timeline.filter(x=>x.incident||x.status==='rejected'||x.conflict):D.timeline;columns=colsTimeline;return;}
 if(id==='orders'){currentRows=D.orders;columns=[col('id','Request / order',x=>x.id,x=>entityButton('order',x.id)),col('at','First observed',firstAt,x=>time(firstAt(x))),col('dealer','Dealer',x=>(x.data.request||x.data.order)?.dealerId,x=>(x.data.request||x.data.order)?.dealerId||'Not captured'),col('route','Route',x=>route(x),x=>N('span',route(x)),'wrap'),col('outcome','Outcome',x=>x.data.outcome,x=>badge(x.data.outcome,x.data.outcome==='won'?'good':x.data.outcome==='lost'?'bad':'')),col('quote','Quote capture',x=>x.data.quoteStatus,x=>x.data.quoteStatus),col('price','Won price',x=>x.data.order?.priceCents,x=>fmt(x.data.order?.priceCents),'numeric'),col('net','Direct ledger net¹',x=>x.directNetCents,x=>N('span',fmt(x.directNetCents),x.directNetCents<0?'negative':''),'numeric')];return;}
 if(id==='gigs'){currentRows=D.gigs;columns=[col('id','Gig',x=>x.id,x=>entityButton('gig',x.id)),col('at','First observed',firstAt,x=>time(firstAt(x))),col('status','Last observed state',x=>x.data.lastObservedStatus,x=>badge(x.data.lastObservedStatus||x.data.snapshot?.status||'not captured')),col('orders','Orders',x=>x.related.join(),x=>refCell('order',x.related)),col('stops','Stops',x=>(x.data.post||x.data.snapshot)?.stops?.length||0,x=>num((x.data.post||x.data.snapshot)?.stops?.length||0),'numeric'),col('views','Views',x=>activity(x).filter(x=>x.kind==='gig_viewed').length,x=>num(activity(x).filter(x=>x.kind==='gig_viewed').length),'numeric'),col('net','Gig ledger net²',x=>x.ledger.reduce((s,i)=>s+D.ledger[i].cents,0),x=>fmt(x.ledger.reduce((s,i)=>s+D.ledger[i].cents,0)),'numeric')];return;}
 if(id==='drivers'){currentRows=D.drivers;columns=[col('id','Driver',x=>x.id,x=>entityButton('driver',x.id)),col('at','First observed',firstAt,x=>time(firstAt(x))),col('home','Home (roster)',x=>x.data.profile?.homePlaceId,x=>x.data.profile?.homePlaceId||'Unavailable'),col('rating','Rating (roster)',x=>x.data.profile?.rating,x=>x.data.profile?.rating??'Unavailable','numeric'),...['gig_viewed','gig_booked','gig_dropped','no_show'].map(k=>col(k,human(k),x=>activity(x).filter(e=>e.kind===k).length,x=>num(activity(x).filter(e=>e.kind===k).length),'numeric'))];return;}
 if(id==='ledger'){currentRows=D.ledger;columns=[col('at','World time',x=>x.at,x=>time(x.at)),col('kind','Entry kind',x=>x.kind,x=>badge(x.kind)),col('cents','Amount',x=>x.cents,x=>N('span',fmt(x.cents),x.cents<0?'negative':'positive'),'numeric'),col('order','Direct order',x=>x.orderId,x=>x.orderId?entityButton('order',x.orderId):'Not assigned'),col('gig','Gig',x=>x.gigId,x=>x.gigId?entityButton('gig',x.gigId):'Not captured'),col('detail','Detail',x=>x.detail,x=>N('span',x.detail||''),'wrap'),col('sourceLine','Source',x=>x.sourceLine,x=>lineButton(x.sourceLine))];return;}
 if(id==='source'){currentRows=D.records;columns=[col('line','Line',x=>x.line,x=>lineButton(x.line)),col('offset','Byte offset',x=>x.offset,x=>num(x.offset),'numeric'),col('length','Bytes',x=>x.length,x=>num(x.length),'numeric'),col('kind','Record type',x=>x.value?.type||'unknown',x=>badge(x.value?.type||'unknown')),col('error','Parse state',x=>x.error||'',x=>x.error?badge(x.error,'warn'):badge('parsed','good')),col('fields','Top-level fields',x=>JSON.stringify(Object.keys(x.value||{})),x=>N('span',x.value&&typeof x.value==='object'?Object.keys(x.value).join(', '):typeof x.value),'wrap')];return;}
}
function route(o){return arr((o.data.order||o.data.request)?.legs).map(l=>(l?.pickup?.placeId||'?')+' → '+(l?.delivery?.placeId||'?')).join(' · ')||'Route unavailable';}
function rowRefs(row){if(active==='orders')return entityRefs('order',row);if(active==='gigs')return entityRefs('gig',row);if(active==='drivers')return entityRefs('driver',row);if(active==='ledger')return {order:row.orderId?[row.orderId]:[],gig:row.gigId?[row.gigId]:[],driver:[]};return row.refs||{order:[],gig:[],driver:[]};}
function rowTimes(row){return ['orders','gigs','drivers'].includes(active)?activity(row).map(e=>e.at):[row.at??row.value?.at];}
function rowKind(row){return active==='source'?row.value?.type||'unknown':row.kind||'';}
function rowState(row){return active==='orders'?row.data.outcome:active==='gigs'?row.data.lastObservedStatus||row.data.snapshot?.status||'not captured':active==='source'?(row.error?'invalid or ambiguous':'parsed'):row.conflict?'conflicting sequence':row.status||'';}
const filterIds=['search','day','from','to','kind','state','order-filter','gig-filter','driver-filter'];
for(const kind of ['order','gig','driver']){const label=N('label',kind==='order'?'Order / request ID':human(kind)+' ID');const input=N('input');input.id=kind+'-filter';input.placeholder='Any';input.type='search';label.append(input);$('filters').insertBefore(label,$('reset'));}
function setupFilters(){
 for(const id of filterIds)$(id).value='';
 const allTimes=currentRows.flatMap(rowTimes).filter(Number.isInteger);const daySet=[...new Set(allTimes.map(x=>Math.floor(x/1440)))].sort((a,b)=>a-b);
 for(const [id,values,label] of [['day',daySet,dayName],['kind',[...new Set(currentRows.map(rowKind).filter(Boolean))].sort(),human],['state',[...new Set(currentRows.map(rowState).filter(Boolean))].sort(),human]]){clear($(id));add($(id),new Option('All '+(id==='day'?'days':id==='state'?'states':'kinds'),''));for(const v of values)$(id).append(new Option(label(v),String(v)));$(id).parentElement.hidden=values.length===0;}
 $('day').parentElement.hidden=allTimes.length===0;$('from').parentElement.hidden=allTimes.length===0;$('to').parentElement.hidden=allTimes.length===0;
 for(const kind of ['order','gig','driver'])$(kind+'-filter').parentElement.hidden=active==='source';
}
function clockValue(s){const p=s.split(':').map(Number);return p.length===2?p[0]*60+p[1]:null;}
function applyFilters(){
 const q=$('search').value.trim().toLowerCase(), day=$('day').value, from=clockValue($('from').value),to=clockValue($('to').value),kind=$('kind').value,state=$('state').value;
 filtered=currentRows.filter(row=>{
  if(kind&&rowKind(row)!==kind)return false;if(state&&rowState(row)!==state)return false;
  if(q&&!searchText(row).includes(q))return false;
  const refs=rowRefs(row);for(const type of ['order','gig','driver']){const v=$(type+'-filter').value.trim().toLowerCase();if(v&&!refs[type].some(id=>id.toLowerCase().includes(v)))return false;}
  if(day!==''||from!==null||to!==null){if(!rowTimes(row).some(at=>{if(!Number.isInteger(at))return false;if(day!==''&&Math.floor(at/1440)!==Number(day))return false;const clock=((at%1440)+1440)%1440;return from!==null&&to!==null&&from>to?clock>=from||clock<=to:(from===null||clock>=from)&&(to===null||clock<=to);}))return false;}
  return true;
 });
 if(sortKey){const c=columns.find(c=>c.key===sortKey);if(c)filtered.sort((a,b)=>{const av=c.value(a),bv=c.value(b);if(av==null)return bv==null?0:1;if(bv==null)return -1;return direction*(typeof av==='number'&&typeof bv==='number'?av-bv:String(av).localeCompare(String(bv),undefined,{numeric:true}));});}
 page=0;drawTable();
}
function drawTable(){
 const thead=$('table').querySelector('thead'),tbody=$('table').querySelector('tbody');clear(thead);clear(tbody);const hr=N('tr');
 for(const c of columns){const th=N('th',null,c.cls==='numeric'?'numeric':'');th.scope='col';th.setAttribute('aria-sort',sortKey===c.key?(direction===1?'ascending':'descending'):'none');th.append(button(c.title+(sortKey===c.key?(direction===1?' ↑':' ↓'):''),()=>{direction=sortKey===c.key?-direction:1;sortKey=c.key;applyFilters();}));hr.append(th);}thead.append(hr);
 const pages=Math.max(1,Math.ceil(filtered.length/size));page=Math.max(0,Math.min(page,pages-1));
 for(const row of filtered.slice(page*size,(page+1)*size)){const tr=N('tr');for(const c of columns){const td=N('td',null,c.cls);add(td,c.render(row));tr.append(td);}tbody.append(tr);}
 $('row-count').textContent=`${num(filtered.length)} of ${num(currentRows.length)} ${active==='source'?'source records':'rows'}`;
 $('page-info').textContent=filtered.length?`${num(page*size+1)}–${num(Math.min((page+1)*size,filtered.length))} of ${num(filtered.length)}`:'0 rows';
 $('page-number').value=page+1;$('page-number').max=pages;$('first').disabled=$('prev').disabled=page===0;$('last').disabled=$('next').disabled=page>=pages-1;$('empty').hidden=filtered.length!==0;$('table').hidden=filtered.length===0;
}
$('filters').onsubmit=e=>e.preventDefault();
for(const id of filterIds)$(id).addEventListener(id==='search'||id.endsWith('-filter')?'input':'change',()=>{clearTimeout(debounce);debounce=setTimeout(applyFilters,id==='search'?160:0);});
$('reset').onclick=()=>{for(const id of filterIds)$(id).value='';applyFilters();};
$('page-size').onchange=()=>{size=Number($('page-size').value);page=0;drawTable();};
$('first').onclick=()=>{page=0;drawTable();};$('prev').onclick=()=>{page--;drawTable();};$('next').onclick=()=>{page++;drawTable();};$('last').onclick=()=>{page=Math.ceil(filtered.length/size)-1;drawTable();};$('page-number').onchange=()=>{page=Number($('page-number').value)-1;drawTable();};
$('export-filtered').onclick=()=>download('cheap-drive-'+active+'-filtered.json',filtered);
function showDialog(label,title){$('detail-label').textContent=label;$('detail-title').textContent=title;clear($('detail-body'));if(!$('detail').open)$('detail').showModal();$('detail').scrollTop=0;return $('detail-body');}
$('close-detail').onclick=()=>$('detail').close();
$('detail').addEventListener('click',e=>{if(e.target===$('detail')){const r=$('detail').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('detail').close();}});
function rawDetail(line){const r=D.records[line-1];if(!r)return;const body=showDialog('Original source record','Line '+line);add(body,N('p',`Byte offset ${num(r.offset)}, length ${num(r.length)}. `+(r.error||'Parsed JSON. Exact original bytes remain available.'),'muted'),button('Download this line exactly',()=>download('cheap-drive-line-'+line+'.bin',source().slice(r.offset,r.offset+r.length),'application/octet-stream')),details('Parsed value',r.value,true),details('Original text (invalid UTF-8 displayed with replacement characters)',new TextDecoder().decode(source().subarray(r.offset,r.offset+r.length)),true));}
function facts(parent, values){const dl=N('dl');for(const [k,v] of values){add(dl,N('dt',k),N('dd',v));}parent.append(dl);}
function entityDetail(kind,id){
 const entity=lookup[kind].get(id);if(!entity)return;const body=showDialog(human(kind)+' history',id),data=entity.data,history=activity(entity);
 if(kind==='order'){
  const request=data.request||{},order=data.order||{},legs=arr(order.legs||request.legs);
  facts(body,[['Observed outcome',data.outcome],['Quote capture',data.quoteStatus],['Dealer',request.dealerId||order.dealerId||'Unavailable'],['Route',route(entity)],['Request deadline',time(request.respondBy)],['Selected option',order.option||'Unavailable'],['Delivery deadline',time(order.deadline)],['Last pickup deadline',time(order.lastPickupAt)],['Direct recorded net',fmt(entity.directNetCents)]]);
  body.append(N('p','Direct net includes only ledger lines explicitly naming this order. Gig-only or shared fees are not allocated here, so this is not a full order-profit estimate.','notice'));
  if(request.note)body.append(details('Original request note',request.note,true));
  if(request.options)body.append(details('Offered options and list prices',request.options,true));
  if(data.quotes?.length)body.append(details('All captured quotes and results',data.quotes.map(i=>payload(D.timeline[i])),true));
  const grid=N('div',null,'detail-grid');legs.forEach((value,i)=>{const leg=value||{};const p=section('Leg '+(i+1),(leg.pickup?.placeId||'?')+' → '+(leg.delivery?.placeId||'?'));const le=history.filter(x=>x.event?.leg===i);facts(p,[['Pickup window',time(leg.pickup?.window?.from)+' to '+time(leg.pickup?.window?.to)],['Delivery window',time(leg.delivery?.window?.from)+' to '+time(leg.delivery?.window?.to)],['Observed pickups',le.filter(e=>e.kind==='picked_up').map(e=>time(e.at)).join(', ')||'Not captured'],['Observed deliveries',le.filter(e=>e.kind==='delivered').map(e=>time(e.at)).join(', ')||'Not captured'],['Delivery in captured order',time(arr(order.deliveredAt)[i])]]);p.append(details('Car, places, original windows and opening hours',leg));grid.append(p);});body.append(grid);
  if(entity.related.length)add(body,N('h3','Related gigs'),refCell('gig',entity.related));
  if(data.reveal)body.append(details('Captured reveal request',data.reveal));if(data.truth)body.append(details('Captured revealed leg truth',data.truth));
 }else if(kind==='gig'){
  const post=data.post||data.snapshot||{};facts(body,[['Last observed state',data.lastObservedStatus||data.snapshot?.status||'Unavailable'],['Stop count',post.stops?.length??'Unavailable'],['Ledger entries',num(entity.ledger.length)],['Gig ledger net',fmt(entity.ledger.reduce((s,i)=>s+D.ledger[i].cents,0))]]);
  add(body,N('p','Gig ledger entries can also name an order. These totals overlap order-linked entries and must not be added to order totals. Posted or booked fees are commitments, not additional ledger charges.','notice'),N('h3','Orders carried'),refCell('order',entity.related),details('Stops, windows, audience and original fee schedule',post,true));
  const schedules=history.filter(x=>x.action?.schedule||x.event?.feeCents!==undefined);body.append(details('All schedule changes, offers and booking fees',schedules.map(payload),true));
 }else{facts(body,[['Captured activity',num(history.length)],['Roster profile',data.profile?'Captured':'Unavailable: no profile captured for this driver']]);if(data.profile)body.append(details('Captured driver profile',data.profile,true));const gigs=[...new Set(history.flatMap(x=>x.refs.gig))];add(body,N('h3','Observed gigs'),refCell('gig',gigs));}
 if(entity.ledger.length)body.append(details('Explicitly linked ledger entries',entity.ledger.map(i=>D.ledger[i]),true));
 body.append(details('All normalized entity fields',entity.data));
 add(body,N('h3','Complete captured activity'));
 const linked=kind==='order'?[...new Set([...entity.history,...entity.related.flatMap(g=>lookup.gig.get(g)?.history||[])])].sort((a,b)=>a-b).map(i=>D.timeline[i]):history;
 if(kind==='order'&&linked.length!==history.length)body.append(N('p','Includes activity on related gigs. A shared gig can also carry other orders.','muted'));
 historyList(body,linked);
}
function historyList(parent,items){
 const controls=N('div',null,'history-controls'),search=N('input');search.type='search';search.placeholder='Search this history';search.setAttribute('aria-label','Search entity history');const status=N('span'),list=N('div',null,'detail-history');let p=0,matched=items;
 const prev=button('Previous',()=>{p--;draw();}),next=button('Next',()=>{p++;draw();});add(controls,search,status,prev,next);add(parent,controls,list);
 function draw(){p=Math.max(0,Math.min(p,Math.max(0,Math.ceil(matched.length/30)-1)));clear(list);status.textContent=`${num(matched.length)} entries · page ${p+1}/${Math.max(1,Math.ceil(matched.length/30))}`;prev.disabled=p===0;next.disabled=(p+1)*30>=matched.length;for(const x of matched.slice(p*30,(p+1)*30)){const row=N('div',null,'history-row');add(row,N('span',time(x.at),'muted'),badge(x.kind,x.conflict?'bad':x.incident?'warn':''),N('span',eventSummary(x)),lineButton(x.line));list.append(row);}if(!matched.length)list.append(N('p','No captured activity matches.','muted'));}
 search.oninput=()=>{const q=search.value.toLowerCase();matched=items.filter(x=>JSON.stringify(payload(x)).toLowerCase().includes(q));p=0;draw();};draw();
}
function sourceIntro(){
 const panel=N('div');const grid=N('div',null,'integrity-grid');for(const [label,value,note] of [['Source ingestion','Complete',`${num(D.source.bytes)} original bytes retained, including invalid lines.`],['Source validity',D.integrity.invalidLines?'Needs inspection':'All lines parsed',`${num(D.integrity.duplicates)} duplicate event copies, ${num(D.integrity.conflicts)} conflicting sequences, ${num(D.integrity.gaps.length)} sequence gaps.`],['Simulated week',D.integrity.verifiedEnd?'End verified':'Unverified',D.integrity.finalScoreCaptured?'Final score captured.':'No final score captured.']]){const p=section(label);add(p,N('h2',value),N('p',note,'muted'));grid.append(p);}panel.append(grid);
 const integrity=section('Source provenance & limits');add(integrity,N('p','SHA-256 · '+D.source.sha256,'hash'),N('p','All original records, unknown fields, malformed bytes and payloads remain in the original JSONL download. The parsed view uses replacement characters only when displaying invalid UTF-8. Duplicate events are counted once. Conflicting sequence variants are visible but excluded from derived totals.','small'),N('p','A complete file import does not prove a complete simulated week. Legacy journals do not include outgoing intents, whole response batches, snapshots or hidden facts. Even durable capture cannot record a response that never reached the process, a partially received SDK response, or a crash before a successful write. An intent without a captured response has an unknown server outcome. No safe retry or automatic recovery is claimed.','small'));panel.append(integrity);
 const d=N('details');d.open=true;d.append(N('summary',`${num(D.diagnostics.length)} capture and integrity diagnostics`));const list=N('ul',null,'info-list');for(const x of D.diagnostics){const li=N('li');add(li,N('span',x.message),x.line?[' ',lineButton(x.line)]:[]);list.append(li);}if(!D.diagnostics.length)list.append(N('li','No detected integrity issues. This is not proof that every server-side fact was captured.'));d.append(list);panel.append(d);return panel;
}
function capturedContext(){
 const root=$('captures');clear(root);const intro=section('Only what was actually captured','No external map tiles, inferred driver profiles or invented simulator truth.');root.append(intro);
 for(const kind of ['snapshot','map','roster','reveal']){const lines=D.captures[kind]||[];const panel=section(human(kind),lines.length?`${num(lines.length)} captured payloads. Open any source record to inspect every field.`:'Unavailable: this source has no successful '+kind+' capture.');for(const line of lines){const rec=D.records[line-1].value;add(panel,add(N('div',null,'capture-row'),N('span',human(rec.phase||'captured')+' · '+time(rec.at)),button('Inspect full payload · L'+line,()=>rawDetail(line))));}if(kind==='map'&&lines.length){const map=D.records[lines[lines.length-1]-1].value.map;if(map&&Array.isArray(map.places))panel.append(mapView(map));}root.append(panel);}
}
function mapView(map){
 const places=map.places.filter(p=>p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon));if(!places.length)return N('p','No usable coordinates in captured map. The original payload is still inspectable.','muted');
 const minLat=Math.min(...places.map(p=>p.lat)),maxLat=Math.max(...places.map(p=>p.lat)),minLon=Math.min(...places.map(p=>p.lon)),maxLon=Math.max(...places.map(p=>p.lon));const x=p=>35+(p.lon-minLon)/(maxLon-minLon||1)*720,y=p=>330-(p.lat-minLat)/(maxLat-minLat||1)*300;const s=svg('svg',{viewBox:'0 0 800 360',class:'map-svg',role:'img','aria-label':'Captured places and road connections; schematic projection'}),byId=new Map(places.map(p=>[p.id,p]));
 for(const r of arr(map.roads).filter(Boolean)){const a=byId.get(r.from),b=byId.get(r.to);if(a&&b)s.append(svg('line',{x1:x(a),x2:x(b),y1:y(a),y2:y(b)}));}
 for(const p of places){const g=svg('g'),c=svg('circle',{cx:x(p),cy:y(p),r:4}),t=svg('title');t.textContent=`${p.name||p.id} (${p.lat}, ${p.lon})`;c.append(t);const text=svg('text',{x:x(p)+6,y:y(p)-5});text.textContent=p.name||p.id;add(g,c,text);s.append(g);}return s;
}
function navigate(id){
 active=nav.some(x=>x[0]===id)?id:'overview';sortKey='';direction=1;page=0;
 for(const b of $('nav').children){b.classList.toggle('active',b.dataset.tab===active);if(b.dataset.tab===active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
 const titles={overview:['Week overview','Financial performance, observed outcomes and capture confidence.'],orders:['Requests & orders','Every observed request, quote and outcome. Open an ID for its full history.'],timeline:['Event timeline','Complete chronological events and actions. Repeated identical events are counted once.'],gigs:['Gigs & stops','Posting history, schedules, bookings and driver activity.'],drivers:['Drivers','All observed drivers. Roster-only facts appear only when captured.'],incidents:['Incidents','Operational warnings, rejections and conflicting event payloads.'],ledger:['Financial ledger','Every valid non-conflicting ledger entry, reconciled to the recorded score.'],source:['Source & integrity','Exact bytes, raw records, provenance and completeness diagnostics.'],captures:['Captured context','Snapshots, map, roster and reveal from this source.']};
 $('title').textContent=titles[active][0];$('subtitle').textContent=titles[active][1];$('overview').hidden=active!=='overview';$('workspace').hidden=['overview','captures'].includes(active);$('captures').hidden=active!=='captures';
 if(active==='overview')overview();else if(active==='captures')capturedContext();else{configure(active);clear($('section-intro'));if(active==='source')$('section-intro').append(sourceIntro());else $('section-intro').append(N('p',active==='orders'?'¹ Direct ledger net excludes gig-only and unattributed costs. Missing accepted quotes are labeled as uncaptured; unquoted is confirmed only by a reveal.':active==='gigs'?'² Gig ledger totals overlap order-linked entries. Do not sum these with order totals. Posted/booked fees are not extra ledger costs. Last observed state is an event label, not an invented final state.':active==='ledger'?`Ledger net ${fmt(R.ledgerMarginCents)} · recorded final ${fmt(recorded.marginCents)} · difference ${fmt(R.marginDifferenceCents)} · ${human(R.status)}. Order assignment is shown only when explicitly present in the ledger.`:'Entity ID filters match captured references. Unknown payloads remain in raw records.'));
 setupFilters();$('filter-help').textContent=active==='source'?'Search includes every original line and parsed field. Source export always contains all original bytes.':'Entity tables match any related activity time. Timeline and ledger match entry time. Clock bounds are inclusive; a from time later than to time spans midnight. Overview always shows the whole source.';applyFilters();}
 history.replaceState(null,'','#'+active);
 window.scrollTo(0,0);
}
window.addEventListener('hashchange',()=>{if(location.hash!=='#main')navigate(location.hash.slice(1));});
navigate(location.hash.slice(1)||'overview');
