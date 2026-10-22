'use strict';
const $ = (s) => document.querySelector(s);
const money = (n) => '$' + (n / 100).toFixed(2);
const api = async (path, options={}) => {
  const res = await fetch('/api' + path, {headers:{'Content-Type':'application/json'}, ...options});
  let data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
};
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusLabel = (status) => ({approved:'APPROVED',rejected:'REJECTED',settled:'DEMO SETTLED',uncertain:'UNCERTAIN',delivery_failed:'DELIVERY MISSING',not_settled:'DEMO NOT SETTLED'})[status] || status;
const notice = (text, error=false) => {const el=$('#notice');el.className='notice '+(error?'error':'ok');el.textContent=text;};
async function reload(){
 try{
  const [rows, stats] = await Promise.all([api('/intents'),api('/stats')]);
  $('#m-count').textContent=String(stats.intents).padStart(2,'0');
  $('#m-spend').textContent=money(stats.simulated_settled_cents);
  $('#m-rejected').textContent=money(stats.rejected_requested_cents);
  $('#m-uncertain').textContent=String(stats.uncertain).padStart(2,'0');
  if (!rows.length) return;
  $('#ledger').innerHTML=rows.map(x=>`<button class="entry" data-id="${escapeHtml(x.id)}" type="button" aria-label="Open receipt for ${escapeHtml(x.task_id)}"><span class="entry-main"><span class="entry-task">${escapeHtml(x.task_id)}</span><span class="entry-vendor">${escapeHtml(x.service)} · ${escapeHtml(x.merchant)}</span></span><span class="entry-right"><span class="entry-amount">${money(x.amount_cents)}</span><span class="entry-badge ${escapeHtml(x.status)}">${statusLabel(x.status)}</span></span></button>`).join('');
  document.querySelectorAll('.entry').forEach(button=>button.addEventListener('click',()=>showDetail(button.dataset.id)));
 }catch(e){notice('Cannot load the demo ledger: '+e.message,true)}
}
async function createIntent(e){
 e.preventDefault();
 const value=Math.round(Number($('#amount').value)*100);
 if (!Number.isInteger(value)||value<1){notice('Enter a valid positive amount',true);return}
 try{
  const request={task_id:$('#task').value,merchant:$('#merchant').value,service:$('#service').value,amount_cents:value,currency:'USD',idempotency_key:'demo-'+crypto.randomUUID()};
  const out=await api('/intents',{method:'POST',body:JSON.stringify(request)});
  notice(out.status==='approved'?'Policy approved this simulated request. Open its receipt to simulate delivery.':'Policy rejected this request: '+out.reason,out.status==='rejected');
  await reload();await showDetail(out.id);
 }catch(e){notice(e.message,true)}
}
async function showDetail(id){
 try{
  const d=await api('/intents/'+encodeURIComponent(id));
  const fields=[['Task',d.task_id],['Service',d.service],['Provider',d.merchant],['Price',money(d.amount_cents)],['Status',statusLabel(d.status)],['Mode','SIMULATION ONLY'],['Reference',d.tx_hash||'None — no payment occurred'],['Delivery',d.delivery_status||'Not executed'],['Policy',d.reason]];
  $('#detail-title').textContent=d.task_id;
  $('#detail-body').innerHTML=fields.map(([key,v])=>`<div class="detail-row"><span>${escapeHtml(key)}</span><span>${escapeHtml(v)}</span></div>`).join('')+'<h3>Event history</h3>'+d.events.map(e=>`<div class="event"><strong>${escapeHtml(e.event_type)}</strong><div>${escapeHtml(e.details)}</div><small>${escapeHtml(e.occurred_at)}</small></div>`).join('');
  const actions=$('#detail-actions');actions.className='dialog-buttons';actions.innerHTML='';
  if(d.status==='approved'){
    for (const [label,outcome] of [['SIMULATE SUCCESSFUL DELIVERY','delivered'],['SIMULATE MISSING DELIVERY','missing_delivery'],['SIMULATE UNKNOWN SETTLEMENT','unknown_settlement']]){
      const b=document.createElement('button');b.textContent=label;b.addEventListener('click',async()=>{b.disabled=true;try{await api('/intents/'+encodeURIComponent(id)+'/simulate',{method:'POST',body:JSON.stringify({outcome})});await reload();await showDetail(id)}catch(e){notice(e.message,true);b.disabled=false}});actions.appendChild(b)
    }
  } else if(d.status==='uncertain'){
    const p=document.createElement('p');p.textContent='A real buyer must check chain/provider proof before retrying. This demonstration requires manually recorded evidence.';actions.appendChild(p);
    const text=document.createElement('input');text.placeholder='Demo reconciliation evidence';text.setAttribute('aria-label','Demo reconciliation evidence');actions.appendChild(text);
    for(const [label,status] of [['RECONCILE: DEMO SETTLED','settled'],['RECONCILE: DEMO NOT SETTLED','not_settled']]){
     const b=document.createElement('button');b.textContent=label;b.addEventListener('click',async()=>{try{await api('/intents/'+encodeURIComponent(id)+'/reconcile',{method:'POST',body:JSON.stringify({status,evidence:text.value})});await reload();await showDetail(id)}catch(e){notice(e.message,true)}});actions.appendChild(b)
    }
  }
  if(!$('#detail').open) $('#detail').showModal();
 }catch(e){notice(e.message,true)}
}
$('#intent-form').addEventListener('submit',createIntent);
$('#refresh').addEventListener('click',reload);
$('#close-detail').addEventListener('click',()=>$('#detail').close());
reload();

$('#demo-form').addEventListener('submit',async(e)=>{
 e.preventDefault();const panel=$('#demo-result');panel.textContent='Running safe local simulation…';
 try{
   const id='demo-brief-'+crypto.randomUUID();
   const res=await api('/demo/creator-brief',{method:'POST',body:JSON.stringify({task_id:id,creator_handle:$('#creator-handle').value,idempotency_key:id+'-call'})});
   if(!res.result){panel.textContent='Demo task '+res.status+'; inspect the ledger for the recorded decision.';await reload();return}
   const rows=res.result.channels.map(x=>'<div class="detail-row"><span>'+escapeHtml(x.channel)+'</span><span>'+x.demo_share_pct+'% (synthetic)</span></div>').join('');
   panel.innerHTML='<div class="sample-report"><strong>SYNTHETIC AGENT REPORT</strong><p>'+escapeHtml(res.result.data_provenance)+'</p>'+rows+'<p>'+escapeHtml(res.result.example_output)+'</p><small>Payment reference: '+escapeHtml(res.intent.tx_hash)+' — SIMULATED, NOT ONCHAIN</small></div>';
   await reload();
 }catch(e){panel.textContent='Demo error: '+e.message}
});
