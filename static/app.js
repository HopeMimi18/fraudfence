'use strict';
let csrf='', profile=null, suppliers=[], sales=[], changes=[];
const el=id=>document.getElementById(id);
const fmt=(cents)=>'R'+(cents/100).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
const money=v=>Math.round(Number(v)*100);
const e=s=>String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
async function api(path, opts={}){
  const headers={'Content-Type':'application/json',...(opts.method&&opts.method!=='GET'?{'X-CSRF-Token':csrf}: {})};
  const resp=await fetch(path,{credentials:'same-origin',...opts,headers:{...headers,...(opts.headers||{})}});
  let data;try{data=await resp.json()}catch{data={detail:'Unexpected server response'}}
  if(!resp.ok)throw Error(typeof data.detail==='string'?data.detail:'Request failed');
  return data;
}
function flash(message,bad=false){el('flash').textContent=message;el('flash').style.color=bad?'#a02c28':'#25633d';}
function error(err){flash(err.message||String(err),true)}
function show(id){el(id).classList.remove('hidden')}
function hide(id){el(id).classList.add('hidden')}
// Password is kept only in a local variable for the immediate request; never stored
// in browser storage or written to the DOM via innerHTML.
async function requestOwnerPassword(){
  const dialog=el('stepup-dialog'),form=el('stepup-form'),input=el('stepup-password');
  input.value='';
  return new Promise(resolve=>{
    const finish=(password)=>{form.removeEventListener('submit',onSubmit);el('stepup-cancel').removeEventListener('click',onCancel);dialog.removeEventListener('cancel',onCancel);input.value='';if(dialog.open)dialog.close();resolve(password)};
    const onSubmit=event=>{event.preventDefault();finish(input.value)};
    const onCancel=event=>{event.preventDefault();finish(null)};
    form.addEventListener('submit',onSubmit);el('stepup-cancel').addEventListener('click',onCancel);dialog.addEventListener('cancel',onCancel);
    dialog.showModal();input.focus();
  });
}
function display(){hide('login-panel');show('workspace');show('logout');el('identity').textContent=profile.name+' · '+profile.role;
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.tab-panel').forEach(x=>x.classList.add('hidden'));show('panel-'+b.dataset.tab);flash('');});
  el('pitch-link').hidden=profile.role!=='owner';
  const cashier=profile.role==='cashier';
  document.querySelector('[data-tab="suppliers"]').hidden=cashier;
  document.querySelector('[data-tab="invoices"]').hidden=cashier;
  document.querySelector('[data-tab="incident"]').hidden=cashier;
  document.querySelector('[data-tab="reports"]').hidden=cashier;
  document.querySelector('[data-tab="receipts"]').hidden=cashier;
  document.querySelector('[data-tab="payments"]').hidden=profile.role==='bookkeeper';
  document.querySelector('[data-tab="notifications"]').hidden=profile.role!=='owner';
  document.querySelector('[data-tab="ai"]').hidden=false;
  el('ai-type').querySelector('option[value="invoice"]').disabled=cashier;
  el('ai-type').querySelector('option[value="payment"]').disabled=profile.role==='bookkeeper';
  if(cashier){el('ai-type').value='payment';el('ai-type').dispatchEvent(new Event('change'));}
  el('mock-payment-form-wrap').hidden=profile.role!=='owner';
  if(cashier)document.querySelector('[data-tab="payments"]').click();
  else if(profile.role==='bookkeeper')document.querySelector('[data-tab="invoices"]').click();
  refreshAll();updateAIStatus();}
async function refreshAll(){
  const tasks=[];
  if(profile.role!=='cashier')tasks.push(loadSuppliers(),loadChanges(),loadReports());
  if(profile.role!=='bookkeeper')tasks.push(loadSales());
  if(profile.role==='owner')tasks.push(api('/api/audit/status').then(x=>el('stat-audit').textContent=x.chain_valid?'INTACT':'ALERT'), loadNotifications());
  else el('stat-audit').textContent='OWNER ONLY';
  await Promise.allSettled(tasks);
}
async function tryLogin(){try{const p=await api('/api/me');const t=await api('/api/auth/csrf');profile=p;csrf=t.csrf_token;display()}catch{}}
el('login-form').onsubmit=async ev=>{ev.preventDefault();el('login-error').textContent='';try{const d=await api('/api/auth/login',{method:'POST',body:JSON.stringify({email:el('email').value,password:el('password').value})});csrf=d.csrf_token;profile=await api('/api/me');display()}catch(err){el('login-error').textContent=err.message;}};
el('logout').onclick=async()=>{try{await api('/api/auth/logout',{method:'POST'});}catch{}location.reload()};

async function loadSuppliers(){try{suppliers=await api('/api/suppliers');el('stat-suppliers').textContent=suppliers.length;el('invoice-supplier').innerHTML='<option value="" selected disabled>Choose saved supplier after upload</option>'+suppliers.map(x=>`<option value="${e(x.id)}">${e(x.name)} · ${e(x.verification)}</option>`).join('');
  el('supplier-list').innerHTML=suppliers.length?suppliers.map(x=>`<div class="list-row"><h4>${e(x.name)} <span class="pill">${e(x.verification)}</span></h4><p>Account •••• ${e(x.account_last4)} · ${e(x.registration)} · mock AVS ${e(x.avs_result)} · mock registry ${e(x.registry_result)}</p><p>Owner-asserted identity: ${e(x.identity_source)} · trusted phone source: ${e(x.phone_source)}</p><div class="row-buttons"><button class="secondary" data-action="registry" data-id="${e(x.id)}">Mock CIPC check</button><button class="secondary" data-action="bank" data-id="${e(x.id)}">Mock AVS check</button><button class="secondary" data-action="callback" data-id="${e(x.id)}">Owner call-back</button><button class="ghost" data-action="change" data-id="${e(x.id)}">Request account change</button></div></div>`).join(''):'<p class="muted">No suppliers yet. Create one to begin.</p>';
  el('supplier-list').querySelectorAll('button').forEach(b=>b.onclick=()=>supplierAction(b.dataset.action,b.dataset.id));
}catch(err){error(err)}}
async function loadChanges(){try{changes=await api('/api/changes');el('stat-pending').textContent=changes.filter(c=>c.status==='PENDING').length;
  el('change-list').innerHTML=changes.length?changes.map(c=>`<div class="list-row"><h4>${e(c.supplier)}</h4><p>Proposed account •••• ${e(c.account_last4)} · ${e(c.status)} · mock AVS ${e(c.avs_result)}</p>${c.status==='PENDING'?`<button class="secondary" data-change="${e(c.id)}">Owner approve after independent call</button>`:''}</div>`).join(''):'<p class="muted">No pending changes.</p>';
  el('change-list').querySelectorAll('button').forEach(b=>b.onclick=()=>approveChange(b.dataset.change));
}catch(err){error(err)}}
async function supplierAction(action,id){try{const s=suppliers.find(x=>x.id===id);if(!s)return;
  if(action==='registry'){const d=await api('/api/suppliers/'+id+'/registry-check',{method:'POST'});el('receipt-id').value=d.receipt_id;flash('Mock CIPC-style result: '+d.result+'. '+d.notice+' Receipt: '+d.receipt_id);}
  else if(action==='bank'){const account=prompt('Enter the full synthetic account to check (the system stores only an HMAC fingerprint).');if(!account)return;const d=await api('/api/suppliers/'+id+'/bank-check',{method:'POST',body:JSON.stringify({bank_account:account})});el('receipt-id').value=d.receipt_id;flash('Mock AVS: '+d.result+'. '+d.notice+' Receipt: '+d.receipt_id);}
  else if(action==='callback'){if(!confirm('Have you actually called the supplier using the PREVIOUSLY TRUSTED number, outside this invoice? Click OK only to record an owner attestation.'))return;const digits=prompt('Enter the last 4 account digits independently confirmed by the supplier:');if(!digits)return;const password=await requestOwnerPassword();if(password===null)return;const d=await api('/api/suppliers/'+id+'/callback',{method:'POST',body:JSON.stringify({last4_confirmed:digits,called_independently:true,owner_password:password})});el('receipt-id').value=d.receipt_id;flash(d.notice+' Receipt: '+d.receipt_id);}
  else if(action==='change'){const account=prompt('Enter the NEW synthetic bank account number:');if(!account)return;const d=await api('/api/suppliers/'+id+'/changes',{method:'POST',body:JSON.stringify({bank_account:account})});flash('Change PENDING. Mock AVS: '+d.mock_avs+'. '+d.message);if(profile.role==='owner')loadNotifications();}
  await loadSuppliers();await loadChanges();if(profile.role==='owner')await loadNotifications();
}catch(err){error(err)}}
async function approveChange(id){if(!confirm('Confirm you independently called the existing trusted supplier number and confirmed the NEW account.'))return;const digits=prompt('Last 4 digits of NEW account independently confirmed:');if(!digits)return;try{const password=await requestOwnerPassword();if(password===null)return;const d=await api('/api/changes/'+id+'/approve',{method:'POST',body:JSON.stringify({last4_confirmed:digits,called_independently:true,owner_password:password})});el('receipt-id').value=d.receipt_id;flash(d.notice+' Receipt: '+d.receipt_id);await loadSuppliers();await loadChanges()}catch(err){error(err)}}
el('refresh-suppliers').onclick=()=>{loadSuppliers();loadChanges()};
el('supplier-form').onsubmit=async ev=>{ev.preventDefault();try{const data=Object.fromEntries(new FormData(ev.target));const d=await api('/api/suppliers',{method:'POST',body:JSON.stringify(data)});flash('Supplier saved as '+d.verification+'. Complete mock registry check, mock AVS, then independent owner call-back.');loadSuppliers()}catch(err){error(err)}};
// Each invoice starts blank. Never preserve fields or previous AI/verdict results
// when a different file is selected or an extraction fails.
let fullInvoiceUploadToken=0;
let fullInvoiceUploaded=false;
function clearFullInvoice(){
  fullInvoiceUploaded=false;
  for(const id of ['invoice-reference','invoice-amount','invoice-account','invoice-text'])el(id).value='';
  el('invoice-supplier').value='';
  el('invoice-reviewed').checked=false;
  // Invalidate the last invoice receipt so an old AI report cannot be mistaken for this upload.
  el('ai-receipt').value='';
  el('invoice-result').innerHTML='<h3>Awaiting an invoice</h3><p class="muted">Upload a document and review all fields before checking.</p>';
}
el('invoice-upload-file').addEventListener('change',()=>{
  ++fullInvoiceUploadToken;
  clearFullInvoice();
  el('invoice-extract-result').textContent='New invoice selected. Click Extract invoice details to populate the fields.';
});
clearFullInvoice();
el('invoice-upload-form').onsubmit=async ev=>{ev.preventDefault();
  const token=++fullInvoiceUploadToken;
  clearFullInvoice();
  try{
    const file=el('invoice-upload-file').files[0];if(!file)throw Error('Choose an invoice PDF or image');
    const data=new FormData();data.append('file',file);
    const res=await fetch('/api/invoices/extract',{method:'POST',headers:{'X-CSRF-Token':csrf},body:data,credentials:'same-origin'});
    const parsed=await res.json();if(!res.ok)throw Error(parsed.detail||'Could not read invoice');
    if(token!==fullInvoiceUploadToken)return; // User selected another document mid-request.
    el('invoice-reference').value=parsed.invoice_reference||'';
    el('invoice-amount').value=parsed.amount_zar||'';
    el('invoice-account').value=parsed.bank_account||'';
    // Only SUGGEST a supplier when the untrusted document name exactly matches
    // a saved independently established name; the user still reviews it.
    if(parsed.legal_name){
      const norm=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
      const candidates=suppliers.filter(x=>norm(x.expected_legal_name)===norm(parsed.legal_name)||norm(x.name)===norm(parsed.legal_name));
      if(candidates.length===1)el('invoice-supplier').value=candidates[0].id;
    }
    fullInvoiceUploaded=true;
    el('invoice-reviewed').checked=false;
    el('invoice-extract-result').textContent='Extraction: '+parsed.extraction_method+'. Fields found: '+(parsed.fields_found.join(', ')||'none')+'. '+parsed.warnings.join(' ')+' Review the supplier selection independently.';
    flash('Invoice fields filled from the new document. Review and correct any missing details.');
  }catch(err){if(token===fullInvoiceUploadToken){clearFullInvoice();el('invoice-extract-result').textContent='Extraction failed. No invoice fields retained. '+err.message;error(err)}}
};
el('invoice-form').onsubmit=async ev=>{ev.preventDefault();try{if(!fullInvoiceUploaded)throw Error('Upload and extract an invoice before running verification');const d=await api('/api/checks/invoice',{method:'POST',body:JSON.stringify({supplier_id:el('invoice-supplier').value,invoice_reference:el('invoice-reference').value,amount_cents:money(el('invoice-amount').value),bank_account:el('invoice-account').value,sender_text:el('invoice-text').value,source:'web_form'})});
    const bad=d.decision.startsWith('STOP'),hold=d.decision.startsWith('HOLD');const klass=bad?'bad':hold?'hold':'good';el('invoice-result').innerHTML=`<div class="decision ${klass}"><div class="eyebrow">${bad?'STOP — ACCOUNT MISMATCH':hold?'ON HOLD — INVESTIGATE':'SAVED RECORD MATCH'}</div><div class="result-title">${e(d.decision)}</div><p>${e(d.explanation)}</p></div><p class="muted">Sender authentication: ${e(d.sender_authentication)} · Outside business reporters: ${e(d.external_reporters)}</p><p class="muted">${d.limitations.map(e).join(' · ')}</p>${d.warning_hints.length?`<div class="warn-box">${d.warning_hints.map(e).join('')}</div>`:''}<div class="row-buttons"><button class="secondary" id="copy-receipt">Copy receipt ID</button><button class="ghost" id="view-receipt">Open verification page</button><button class="primary" id="invoice-ai-now">★ AI report</button></div><p class="muted">Receipt ID: <code>${e(d.receipt_id)}</code></p>`;
    el('receipt-id').value=d.receipt_id;el('ai-receipt').value=d.receipt_id;el('copy-receipt').onclick=()=>{navigator.clipboard.writeText(d.receipt_id).then(()=>flash('Receipt ID copied')).catch(()=>flash('Copy unavailable — select receipt ID manually',true))};el('view-receipt').onclick=()=>window.open('/verify/'+encodeURIComponent(d.receipt_id),'_blank','noopener');el('invoice-ai-now').onclick=()=>document.querySelector('[data-tab="ai"]').click();flash('Invoice decision recorded; signed receipt generated.');
  }catch(err){error(err)}};
let selectedOwnerReview=null;
async function loadSales(){try{sales=await api('/api/sales');el('stat-sales').textContent=sales.length;
 el('ai-sale').innerHTML=sales.length?sales.map(s=>`<option value="${e(s.id)}">${e(s.reference)} · ${e(s.status)}</option>`).join(''):'<option value="">Create a sale first</option>';
 el('sale-list').innerHTML=sales.length?sales.map(x=>{
   const pending=x.status==='PENDING_OWNER_REVIEW';
   const canRequest=['UNVERIFIED','AMBIGUOUS','OWNER_REPORTED_NOT_RECEIVED'].includes(x.status);
   const action=canRequest?`<button class="primary" data-review-request="${e(x.id)}">Request owner verification</button>`:'';
   const owner=pending&&profile.role==='owner'?`<button class="primary" data-owner-review="${e(x.id)}">Review bank payment</button>`:'';
   const waiting=pending?'<p class="muted">Awaiting owner. Do not release goods.</p>':'';
   const confirmed=x.status==='OWNER_ATTESTED_NOT_BANK_VERIFIED'?'<p class="muted">Owner manually confirmed checking their bank; FraudFence did not verify bank data.</p>':'';
   const demo=x.status==='SIMULATED_PAYMENT_MATCH'?'<p class="muted">Synthetic match only. Not real funds.</p>':'';
   const recon=!pending&&canRequest&&profile.role==='owner'?`<button class="ghost" data-sale="${e(x.id)}">Match demo payment</button>`:'';
   return `<div class="list-row"><h4>${e(x.reference)} · ${fmt(x.amount_cents)}</h4><p>Status: ${e(x.status)} · ${e(x.created_at)}</p>${waiting}${confirmed}${demo}<div class="row-buttons">${action}${owner}${recon}<button class="ghost" data-ai-sale="${e(x.id)}">★ AI report</button></div></div>`;
 }).join(''):'<p class="muted">No sales logged.</p>';
 el('sale-list').querySelectorAll('button[data-review-request]').forEach(b=>b.onclick=async()=>{try{
   const d=await api('/api/sales/'+encodeURIComponent(b.dataset.reviewRequest)+'/request-owner-review',{method:'POST'});
   flash(d.status+': Owner verification requested.');await loadSales();if(profile.role==='owner')await loadNotifications();
 }catch(err){error(err)}});
 el('sale-list').querySelectorAll('button[data-owner-review]').forEach(b=>b.onclick=()=>{
   selectedOwnerReview=sales.find(s=>s.id===b.dataset.ownerReview);el('owner-payment-summary').textContent='Review '+selectedOwnerReview.reference+' · '+fmt(selectedOwnerReview.amount_cents);
   el('owner-payment-checked').checked=false;el('owner-payment-password').value='';el('owner-payment-review-form').classList.remove('hidden');
   el('owner-payment-review-form').scrollIntoView({block:'nearest',behavior:'smooth'});
 });
 el('sale-list').querySelectorAll('button[data-sale]').forEach(b=>b.onclick=()=>reconcile(b.dataset.sale));
 el('sale-list').querySelectorAll('button[data-ai-sale]').forEach(b=>b.onclick=()=>{el('ai-type').value='payment';el('ai-type').dispatchEvent(new Event('change'));el('ai-sale').value=b.dataset.aiSale;document.querySelector('[data-tab="ai"]').click();});
}catch(err){error(err)}}
let ownerReviewDecision='CONFIRMED';
el('owner-payment-review-form').querySelectorAll('button[data-decision]').forEach(b=>b.addEventListener('click',()=>ownerReviewDecision=b.dataset.decision));
el('owner-payment-review-form').onsubmit=async ev=>{ev.preventDefault();try{
 if(profile.role!=='owner'||!selectedOwnerReview)throw Error('Only an owner can review a pending sale');
 const p={decision:ownerReviewDecision,checked_directly_in_bank_app:el('owner-payment-checked').checked,
     checked_reference:selectedOwnerReview.reference,checked_amount_cents:selectedOwnerReview.amount_cents,
     owner_password:el('owner-payment-password').value};
 const d=await api('/api/sales/'+encodeURIComponent(selectedOwnerReview.id)+'/owner-review',{method:'POST',body:JSON.stringify(p)});
 flash(d.status+': '+d.notice);selectedOwnerReview=null;el('owner-payment-review-form').classList.add('hidden');await loadSales();
}catch(err){error(err)}};
el('refresh-sales').onclick=loadSales;
async function reconcile(id){try{const d=await api('/api/sales/'+id+'/reconcile',{method:'POST'});flash(d.status+': '+d.notice);loadSales();if(profile.role==='owner')loadNotifications()}catch(err){error(err)}}
el('sale-form').onsubmit=async ev=>{ev.preventDefault();try{const d=await api('/api/sales',{method:'POST',body:JSON.stringify({reference:el('sale-reference').value,amount_cents:money(el('sale-amount').value)})});flash('Sale '+d.status+'. No bank confirmation.');loadSales();if(profile.role==='owner')loadNotifications()}catch(err){error(err)}};
el('mock-payment-form').onsubmit=async ev=>{ev.preventDefault();try{const d=await api('/api/demo/payments',{method:'POST',body:JSON.stringify({reference:el('payment-reference').value,amount_cents:money(el('payment-amount').value),state:el('payment-state').value})});flash('Simulated bank event added: '+d.state+'. '+d.notice)}catch(err){error(err)}};
el('incident-form').onsubmit=async ev=>{ev.preventDefault();try{const d=await api('/api/incidents',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(ev.target)))});el('incident-result').innerHTML=`<h3>Incident recorded</h3><p class="muted">Incident ID: ${e(d.id)}</p><ol>${d.steps.map(x=>'<li>'+e(x)+'</li>').join('')}</ol><p class="notice">${e(d.notice)}</p><button class="secondary" id="incident-verify">Verify incident receipt</button>`;el('incident-verify').onclick=()=>window.open('/verify/'+encodeURIComponent(d.receipt_id),'_blank','noopener');flash('Incident recorded, receipt '+d.receipt_id)}catch(err){error(err)}};
async function loadReports(){try{const reports=await api('/api/reports');el('report-list').innerHTML=reports.length?reports.map(x=>`<div class="list-row"><h4>Account •••• ${e(x.account_last4)}</h4><p>${e(x.category)} · ${e(x.status)}</p><p>${e(x.created_at)}</p></div>`).join(''):'<p class="muted">No reports filed.</p>';}catch(err){error(err)}}
el('report-form').onsubmit=async ev=>{ev.preventDefault();try{const d=await api('/api/reports',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(ev.target)))});flash('Report filed as '+d.status+'. Not confirmed fraud.');loadReports()}catch(err){error(err)}};
el('receipt-check').onclick=async()=>{try{const id=el('receipt-id').value.trim();if(!id)throw Error('Enter receipt ID');const d=await api('/api/receipts/'+encodeURIComponent(id));el('receipt-result').innerHTML=`<div class="${d.signature_valid&&d.log_chain_valid&&d.audit_hash_match?'success-box':'danger-box'}">Signature valid: ${d.signature_valid}<br>Hash matches audit record: ${d.audit_hash_match}<br>Audit chain intact: ${d.log_chain_valid}</div><p><a href="${e(d.verify_path)}" target="_blank" rel="noopener">Open privacy-preserving public verification</a></p><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px">${e(JSON.stringify(d.details,null,2))}</pre>`;}catch(err){error(err)}};
el('export-checkpoint').onclick=async()=>{try{if(profile.role!=='owner')throw Error('Only an owner can export checkpoints.');const data=await api('/api/audit/checkpoint');const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='fraudfence-signed-checkpoint.json';document.body.append(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);flash('Signed checkpoint exported. Store it OFF THIS SERVER and protect the trusted public-key fingerprint.');}catch(err){error(err)}};
// The display is deliberately a local WhatsApp-style PREVIEW. Nothing leaves this server.
async function loadNotifications(){
  if(!profile||profile.role!=='owner')return;
  try{
    const data=await api('/api/notifications');
    el('notification-count').textContent=data.unread;
    el('notification-list').innerHTML=data.items.length?data.items.map(n=>
      `<div class="notification-item ${n.read_at?'':'notification-unread'}">`+
      `<div class="notification-meta"><span>FraudFence SA · WhatsApp-style preview</span><span>${n.read_at?'READ':'NEW'}</span></div>`+
      `<h4>${e(n.title)}</h4><p>${e(n.preview)}</p>`+
      `<p class="muted">${e(n.created_at)} · ${e(n.delivery_status.replaceAll('_',' '))}</p>`+
      (n.read_at?'':`<button class="secondary" data-notification-id="${e(n.id)}">Mark as read</button>`)+
      `</div>`).join(''):'<p class="muted">No alerts yet. Log a demo sale or request a supplier change to generate one.</p>';
    el('notification-list').querySelectorAll('button').forEach(b=>b.onclick=async()=>{
      try{await api('/api/notifications/'+encodeURIComponent(b.dataset.notificationId)+'/read',{method:'POST'});await loadNotifications();}
      catch(err){error(err)}
    });
  }catch(err){error(err)}
}
el('refresh-notifications').onclick=loadNotifications;
tryLogin();

// Narrative explanations from an optional real model. System decisions stay immutable.
let latestAIReport=null;
async function updateAIStatus(){
 try{const d=await api('/api/ai/status');
   el('ai-connection').textContent=d.configured
     ? `AI provider configured: ${d.provider} / ${d.model}. This may require network access or a running local model.`
     : 'No AI model connected. Reports will be RULES ONLY; configure Ollama or an API key to enable actual AI.';
 }catch(err){el('ai-connection').textContent='AI status unavailable: '+err.message;}
}
el('ai-type').onchange=()=>{
 const inv=el('ai-type').value==='invoice';
 el('ai-invoice-fields').classList.toggle('hidden',!inv);
 el('ai-payment-fields').classList.toggle('hidden',inv);
};
el('ai-report-form').onsubmit=async ev=>{
 ev.preventDefault();el('ai-report-status').textContent='Checking backend evidence and preparing report…';
 el('ai-report-content').textContent='Generating report…';
 try{
   const isInvoice=el('ai-type').value==='invoice';
   const path=isInvoice?'/api/ai/reports/invoice':'/api/ai/reports/payment';
   const payload=isInvoice?{receipt_id:el('ai-receipt').value.trim()}:{sale_id:el('ai-sale').value};
   const d=await api(path,{method:'POST',body:JSON.stringify(payload)});
   latestAIReport=d.report_text;
   el('ai-report-content').textContent=d.report_text;
   el('ai-report-status').textContent=d.generation==='REAL_AI_MODEL'
      ? `REAL AI REPORT · ${d.model} · Verdict remains ${d.decision}`
      : 'EVIDENCE-ONLY REPORT · NO AI MODEL CONNECTED';
   el('ai-report-proof').textContent=`Signed report receipt: ${d.receipt_id}. SHA-256: ${d.report_sha256}. ${d.model_error||''}`;
   el('ai-download').disabled=false;el('ai-copy').disabled=false;
 }catch(err){latestAIReport=null;el('ai-report-content').textContent='Failed to generate a report.';
    el('ai-report-status').textContent=err.message;el('ai-download').disabled=true;el('ai-copy').disabled=true;}
};
el('ai-download').onclick=()=>{
 if(!latestAIReport)return;
 const blob=new Blob([latestAIReport],{type:'text/plain;charset=utf-8'});
 const url=URL.createObjectURL(blob);const a=document.createElement('a');
 a.href=url;a.download='fraudfence-investigation-report.txt';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
};
el('ai-copy').onclick=()=>{if(latestAIReport)navigator.clipboard.writeText(latestAIReport).then(()=>flash('Report copied')).catch(()=>flash('Copy unavailable',true));};
