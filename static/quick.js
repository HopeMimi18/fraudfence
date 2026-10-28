'use strict';
let csrf='', role='', lastReceipt='', lastSale='', checkoutActive=false, lastReport='', ozowReady=false;
let quickSuppliers=[], quickInvoiceUploadToken=0, quickInvoiceUploaded=false;
const byId=id=>document.getElementById(id);
const safe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cents=x=>Math.round(Number(x)*100);
function setResult(id, title, body, mood=''){const e=byId(id);e.className='result '+mood;e.innerHTML='<strong>'+safe(title)+'</strong><div>'+safe(body)+'</div>';}
function message(s,bad=false){let x=byId('alert');x.textContent=s;x.classList.toggle('error',bad)}
async function api(url,opts={}){const h={'Content-Type':'application/json',...(opts.method&&opts.method!=='GET'?{'X-CSRF-Token':csrf}:{})};const r=await fetch(url,{credentials:'same-origin',...opts,headers:{...h,...(opts.headers||{})}});let d;try{d=await r.json()}catch{d={detail:'Unexpected response'}}if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Request failed');return d}
const post=(path,data)=>api(path,{method:'POST',...(data===undefined?{}:{body:JSON.stringify(data)})});
async function init(){try{let me=await api('/api/me');role=me.role;csrf=(await api('/api/auth/csrf')).csrf_token;byId('who').textContent=me.name+' · '+role;
const canSupplier=role!=='cashier';for(let id of ['company-form','invoice-form'])byId(id).querySelectorAll('input,select,button').forEach(b=>b.disabled=!canSupplier);
const canPayment=role!=='bookkeeper';byId('sale-form').querySelectorAll('input,button').forEach(b=>b.disabled=!canPayment);
if(canSupplier){const suppliers=await api('/api/suppliers');quickSuppliers=suppliers;const sel=byId('supplier-select');sel.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='Select saved supplier after upload';blank.disabled=true;blank.selected=true;sel.appendChild(blank);for(const s of suppliers){const o=document.createElement('option');o.value=s.id;o.textContent=s.name+' · '+s.verification+' · account ••••'+s.account_last4;sel.appendChild(o)}if(!suppliers.length)setResult('invoice-result','No saved supplier','Add a verified demo supplier in the full workspace before checking an invoice.','warn')}
byId('quick-upload-form').querySelectorAll('input,button').forEach(b=>b.disabled=!canSupplier);
await refreshOwnerQueue();
let health=await api('/health');ozowReady=Boolean(health.ozow_staging_configured);byId('ozow-info').textContent=health.ozow_staging_configured?'Ozow staging credentials configured. You can initiate a TEST transaction; no production money is involved.':'Ozow staging not configured. You can demonstrate the safe UNVERIFIED state and fictional payment matching.';
if(!ozowReady)byId('ozow-start').title='Connect Ozow staging credentials first';
const ai=await api('/api/ai/status');byId('ai-status').textContent=!ai.configured?'AI model not connected: reports will be marked rules-only.':'AI provider configuration: '+ai.provider+'. Reports must identify whether the model actually responded.';
byId('sale-reference').value='FF'+String(Date.now()).slice(-9);message('Ready. No CIPC, AVS or Ozow result is considered live unless obtained from the actual provider.');}catch(e){message('Sign in from the main page first. '+e.message,true);}}
byId('company-form').addEventListener('submit',async e=>{e.preventDefault();try{const p=Object.fromEntries(new FormData(e.target));const d=await post('/api/quick/company',p);const good=d.source==='CIPC_AUTHENTICATED_API'&&d.verified_real_company;const simulated=d.source==='SIMULATED_CIPC_FIXTURE';setResult('company-result',d.decision+(simulated?' · SIMULATED':''),`Source: ${d.source}. Company status: ${d.status}. ${d.next_step}`,good?'good':simulated?'warn':'bad');message('Registry evidence completed. A registered company is not automatically an approved supplier.');}catch(x){message(x.message,true)}});
// The invoice and optional company lookup are blank until a document is read.
function clearQuickInvoice(){
 quickInvoiceUploaded=false;
 for(const id of ['invoice-amount'])byId(id).value='';
 const invoice=byId('invoice-form');
 invoice.querySelector('[name="invoice_reference"]').value='';
 invoice.querySelector('[name="bank_account"]').value='';
 byId('supplier-select').value='';
 for(const name of ['registration','legal_name'])byId('company-form').querySelector('[name="'+name+'"]').value='';
 byId('quick-invoice-reviewed').checked=false;
 lastReceipt='';byId('invoice-report').disabled=true;
 setResult('company-result','Not checked','The invoice does not prove company registration.','');
 setResult('invoice-result','Awaiting invoice','Upload a document, review values and run the account comparison.','');
}
byId('quick-upload-file').addEventListener('change',()=>{
 ++quickInvoiceUploadToken;
 clearQuickInvoice();
 setResult('quick-upload-result','New file selected','Click Extract invoice details. All old invoice values have been cleared.','');
});
clearQuickInvoice();
byId('quick-upload-form').addEventListener('submit',async e=>{e.preventDefault();
 const token=++quickInvoiceUploadToken;
 clearQuickInvoice();
 try{
  const file=byId('quick-upload-file').files[0];if(!file)throw Error('Choose an invoice PDF or image first');
  const f=new FormData();f.append('file',file);
  const res=await fetch('/api/invoices/extract',{method:'POST',headers:{'X-CSRF-Token':csrf},body:f,credentials:'same-origin'});
  const d=await res.json();if(!res.ok)throw Error(d.detail||'Extraction failed');
  if(token!==quickInvoiceUploadToken)return; // Ignore stale extraction response.
  byId('invoice-form').querySelector('[name="invoice_reference"]').value=d.invoice_reference||'';
  byId('invoice-amount').value=d.amount_zar||'';
  byId('invoice-form').querySelector('[name="bank_account"]').value=d.bank_account||'';
  byId('company-form').querySelector('[name="registration"]').value=d.registration||'';
  byId('company-form').querySelector('[name="legal_name"]').value=d.legal_name||'';
  // Supplier name from a document is only a suggestion; matching a stored name
  // does NOT authenticate identity or establish the bank account is genuine.
  if(d.legal_name){
    const norm=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
    const matched=quickSuppliers.filter(s=>norm(s.expected_legal_name)===norm(d.legal_name)||norm(s.name)===norm(d.legal_name));
    if(matched.length===1)byId('supplier-select').value=matched[0].id;
  }
  quickInvoiceUploaded=true;
  byId('quick-invoice-reviewed').checked=false;
  setResult('quick-upload-result','Review extracted data',d.extraction_method+' · Found: '+(d.fields_found.join(', ')||'none')+'. '+d.warnings.join(' ')+'. Check the supplier choice.','warn');
  message('Document processed. Blank or uncertain values require review; nothing was verified automatically.');
 }catch(x){if(token===quickInvoiceUploadToken){clearQuickInvoice();setResult('quick-upload-result','Extraction failed','Fields remain empty. '+x.message,'bad');message(x.message,true)}}
});
byId('invoice-form').addEventListener('submit',async e=>{e.preventDefault();try{if(!quickInvoiceUploaded)throw Error('Upload and extract an invoice before running verification');const form=Object.fromEntries(new FormData(e.target));const d=await post('/api/checks/invoice',{supplier_id:byId('supplier-select').value,invoice_reference:form.invoice_reference,amount_cents:cents(byId('invoice-amount').value),bank_account:form.bank_account,source:'web_form'});lastReceipt=d.receipt_id;byId('invoice-report').disabled=false;setResult('invoice-result',d.decision,d.explanation,d.decision.startsWith('STOP')?'bad':d.decision.startsWith('HOLD')?'warn':'good');message('Invoice checked against saved supplier. Generate an AI risk report in step 3.');}catch(x){message(x.message,true)}});
byId('sale-form').addEventListener('submit',async e=>{e.preventDefault();try{const p={reference:byId('sale-reference').value,amount_cents:cents(byId('sale-amount').value)};const d=await post('/api/sales',p);lastSale=d.id;checkoutActive=false;byId('ozow-start').disabled=!ozowReady;byId('ozow-check').disabled=true;byId('demo-payment').disabled=role!=='owner';byId('reconcile').disabled=false;byId('quick-request-owner').disabled=false;byId('payment-report').disabled=false;byId('checkout-wrap').replaceChildren();setResult('sale-result','UNVERIFIED','Sale '+p.reference+' created. Do not release goods until trusted payment confirmation exists.','warn');message('Sale logged. If Ozow staging is configured, select Create Ozow staging checkout.');}catch(x){message(x.message,true)}});
byId('ozow-start').onclick=async()=>{if(!lastSale)return;try{const d=await post('/api/sales/'+encodeURIComponent(lastSale)+'/ozow-staging/start');checkoutActive=true;byId('ozow-check').disabled=false;byId('demo-payment').disabled=true;byId('reconcile').disabled=true;const url=new URL(d.checkout_url);if(url.protocol!=='https:')throw Error('Unrecognised checkout URL');const a=document.createElement('a');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open Ozow staging checkout ↗';const wrap=byId('checkout-wrap');wrap.replaceChildren(a);setResult('sale-result','OZOW STAGING PENDING','Checkout created, NOT payment confirmation. Complete the test checkout and check the authenticated provider status.','warn');message('Staging payment created. This does not mean the customer has paid.');}catch(x){message(x.message,true)}};
byId('ozow-check').onclick=async()=>{if(!lastSale||!checkoutActive)return;try{let d=await post('/api/sales/'+encodeURIComponent(lastSale)+'/ozow-staging/check');setResult('sale-result',d.status,d.notice||'Verified using Ozow staging transaction evidence.',d.status==='OZOW_STAGING_PROVIDER_CONFIRMED'?'good':'warn');message('Authenticated staging transaction check complete. This is not real bank settlement.');}catch(x){message(x.message,true)}};
byId('demo-payment').onclick=async()=>{try{if(!lastSale||role!=='owner'||checkoutActive)return;let p={reference:byId('sale-reference').value,amount_cents:cents(byId('sale-amount').value),state:'SETTLED'};await post('/api/demo/payments',p);setResult('sale-result','FICTIONAL EVENT CREATED','A simulated bank event was added. This is NOT actual funds received. Click Match fictional payment.','warn');message('Fictional event injected. No live bank or Ozow transaction was checked.');}catch(x){message(x.message,true)}};
byId('reconcile').onclick=async()=>{try{if(!lastSale||checkoutActive)return;const d=await post('/api/sales/'+encodeURIComponent(lastSale)+'/reconcile');setResult('sale-result',d.status,d.notice,d.status==='SIMULATED_PAYMENT_MATCH'?'warn':'bad');message('Sale decision updated. A simulated match must never authorise release of real goods.');}catch(x){message(x.message,true)}};
async function report(caseType,source){if(!source)return;try{let d=await post('/api/ai/reports/'+caseType,caseType==='invoice'?{receipt_id:source}:{sale_id:source});lastReport=d.report_text;byId('report-content').textContent=d.report_text;byId('download-report').disabled=false;setResult('ai-status',d.generation,d.generation==='REAL_AI_MODEL'?'A configured AI model generated the explanation; security decision is unchanged.':'No model response: evidence-based rules-only explanation.','warn');message('Report generated. Its security verdict remains controlled by the Trust Engine.');}catch(x){message(x.message,true)}}
byId('invoice-report').onclick=()=>report('invoice',lastReceipt);byId('payment-report').onclick=()=>report('payment',lastSale);
byId('download-report').onclick=()=>{if(!lastReport)return;const blob=new Blob([lastReport],{type:'text/plain'});const url=URL.createObjectURL(blob);let a=document.createElement('a');a.href=url;a.download='fraudfence-investigation-report.txt';a.click();URL.revokeObjectURL(url)};
let quickSelectedReview=null;let quickDecision='CONFIRMED';
async function refreshOwnerQueue(){if(role==='bookkeeper')return;
 try{const sales=await api('/api/sales');const pending=sales.filter(s=>s.status==='PENDING_OWNER_REVIEW');
 const recent=sales.slice(0,6).map(s=>s.reference+': '+s.status).join(' | ');
 byId('quick-review-queue').replaceChildren();
 const line=document.createElement('div');line.textContent='Recent sales: '+(recent||'None')+'. Pending owner reviews: '+pending.length;byId('quick-review-queue').append(line);
 if(role==='owner')for(const s of pending){const b=document.createElement('button');b.className='secondary';b.type='button';b.textContent='Review '+s.reference+' · R'+(s.amount_cents/100).toFixed(2);b.onclick=()=>{
   quickSelectedReview=s;byId('quick-review-summary').textContent=s.reference+' · R'+(s.amount_cents/100).toFixed(2);
   byId('quick-owner-review-form').hidden=false;byId('quick-owner-checked').checked=false;byId('quick-owner-password').value='';
 };byId('quick-review-queue').append(b)}
 }catch(x){message(x.message,true)}}
byId('quick-request-owner').onclick=async()=>{if(!lastSale)return;try{
 const d=await post('/api/sales/'+encodeURIComponent(lastSale)+'/request-owner-review');
 byId('quick-request-owner').disabled=true;byId('ozow-start').disabled=true;byId('demo-payment').disabled=true;byId('reconcile').disabled=true;
 setResult('sale-result',d.status,d.notice,'warn');await refreshOwnerQueue();message('Request sent to the owner inside FraudFence. No external message was sent.');
 }catch(x){message(x.message,true)}};
byId('quick-refresh-sales').onclick=refreshOwnerQueue;
byId('quick-owner-review-form').querySelectorAll('[data-review-decision]').forEach(b=>b.onclick=()=>quickDecision=b.dataset.reviewDecision);
byId('quick-owner-review-form').onsubmit=async e=>{e.preventDefault();try{
 if(role!=='owner'||!quickSelectedReview)throw Error('Choose a pending owner review');
 const s=quickSelectedReview;const d=await post('/api/sales/'+encodeURIComponent(s.id)+'/owner-review',{
    decision:quickDecision,checked_directly_in_bank_app:byId('quick-owner-checked').checked,
    checked_reference:s.reference,checked_amount_cents:s.amount_cents,owner_password:byId('quick-owner-password').value});
 setResult('sale-result',d.status,d.notice,'warn');byId('quick-owner-review-form').hidden=true;quickSelectedReview=null;
 await refreshOwnerQueue();message('Manual owner review recorded. Cashier can refresh to see the result.');
 }catch(x){message(x.message,true)}};
init();
