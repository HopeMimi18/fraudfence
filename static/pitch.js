"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let csrf='', seconds=300, timer=null, pitchInvoiceReceipt=null;
const guard=label=>`<div class="note">${esc(label)} · Synthetic demonstration only. No money, live registry, real phone call or WhatsApp delivery.</div>`;
const fmt=n=>'R'+(n/100).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
async function request(path,method='GET',body=null){
 const headers={'Content-Type':'application/json'}; if(method!=='GET')headers['X-CSRF-Token']=csrf;
 const r=await fetch(path,{method,headers,credentials:'same-origin',...(body?{body:JSON.stringify(body)}:{})});
 let d;try{d=await r.json()}catch{d={detail:'Unexpected server response'}}
 if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Request failed');return d;
}
function setScreen(html,type,status,proof,card){
 $('result').innerHTML=html;$('evidence-type').textContent=type;$('live-status').textContent=status;
 $('live-status').className='badge '+(/STOP|HOLD|DENIED|UNVERIFIED/.test(status)?'stop':/READY|UNTRUSTED/.test(status)?'pending':'good');
 $('meta-status').textContent=proof;$('evidence-proof').textContent=proof;
 document.querySelectorAll('.scenario').forEach(s=>s.classList.toggle('active',s.id===card));
}
const receipt=id=>`<div class="receipt">Real backend-signed receipt ID: ${esc(id)}</div>`;
const pass=ok=>ok?'<strong>PASS</strong>':'<strong class="fail">NOT PROVEN</strong>';
async function run(action){
 const button=document.querySelector(`[data-action="${action}"]`);if(button)button.disabled=true;
 $('message').textContent='Running local demo…';
 try{
  if(action==='problem'){
   const d=await request('/api/pitch/problem');const inv=d.invoice,p=d.payment_claim;
   setScreen(`<div class="result-label">SCENARIO 1 · WHAT A SHOP OWNER RECEIVES · ALL FICTIONAL</div><div class="huge stop">THE TRAP</div>
      <div class="artifact"><div class="arthead">✉ SUPPLIER INVOICE / UNTRUSTED EMAIL</div><b>${esc(d.supplier)}</b><p>${esc(inv.claimed_message)}</p><div class="proof"><span>Invoice ${esc(inv.reference)} · ${fmt(inv.amount_cents)}</span><strong class="fail">Pay ••••${esc(inv.submitted_last4)}</strong></div><small>Saved account in supplier file: ••••${esc(inv.previously_trusted_last4)}</small></div>
      <div class="artifact"><div class="arthead">▧ CUSTOMER PROOF-OF-PAYMENT CLAIM / UNTRUSTED</div><b>Sale ${esc(p.sale_reference)} · ${fmt(p.amount_cents)}</b><p>“${esc(p.customer_claim)}”</p><small>Actual internal payment evidence status: <b>${esc(p.system_status)}</b></small></div>
      <div class="statusline">Without verification, a business could pay the wrong account or release goods on a fake POP.</div>${guard('These are attacker-controlled claims, not verification results')}`,
     '01 · PROBLEM','UNTRUSTED CLAIMS','Fictional source data, not a provider verification','card-one');
  }else if(action==='stop'){
   const invoice=await request('/api/pitch/invoice','POST');
   pitchInvoiceReceipt=invoice.receipt_id;
   const d=await request('/api/pitch/three-sources','POST');
   setScreen(`<div class="result-label">SCENARIO 2 · REAL SERVER-SIDE RULES · MOCK EVIDENCE</div><div class="huge stop">STOP → HOLD</div><div class="alert"><strong>Invoice INV-2207 blocked</strong><p>Supplier saved account ••••5678 vs invoiced account ••••7890.<br><b>${esc(invoice.decision)}</b> — no bank-detail change made.</p></div><div class="gridchecks"><div class="check"><small>MOCK CIPC</small><strong>⚠ Recent change</strong><small>Director changed 6 days ago</small></div><div class="check"><small>MOCK AVS</small><strong>✕ Mismatch</strong><small>Account doesn't match supplier</small></div><div class="check"><small>PRELOADED CALLBACK</small><strong>✕ Supplier denies</strong><small>“We haven't changed banks.”</small></div></div><div class="statusline">${esc(d.decision)} · Existing supplier account remains unchanged.</div>${receipt(invoice.receipt_id)}${guard('Source checks simulated; STOP rule, HOLD, and signed receipt executed on the backend')}`,
    '02 · SUPPLIER DEFENCE','HOLD','Actual fingerprint check & HOLD; simulated provider evidence','card-two');
  }else if(action==='paid'){
   const d=await request('/api/pitch/payment-check','POST');
   setScreen(`<div class="result-label">SCENARIO 2 · CAN WE TRUST A PAYMENT SCREENSHOT?</div><div class="huge ${d.status==='UNVERIFIED'?'stop':'good'}">${esc(d.status)}</div><div class="artifact"><div class="arthead">CASHIER ASKS: PAID? FF-1058</div><b>R850 · Cement</b><p>${esc(d.message)}</p></div><div class="statusline">A screenshot does not create a provider-confirmed payment.</div>${guard('Local sale check. No actual Ozow, bank funds or goods release')}`,
    '02 · PAYMENT DEFENCE',d.status,'Business-scoped sale-status query; no trusted funds until authenticated provider event','card-two');
  }else if(action==='inject'){
   const d=await request('/api/pitch/mock-payment','POST');await run('paid');
   $('message').textContent='FICTIONAL event inserted: '+d.status+' · Do not release real goods.';return;
  }else if(action==='ai-invoice'||action==='ai-payment'){
   const isInvoice=action==='ai-invoice';
   if(isInvoice&&!pitchInvoiceReceipt){
     const invoice=await request('/api/pitch/invoice','POST');pitchInvoiceReceipt=invoice.receipt_id;
   }
   const d=await request(isInvoice?'/api/ai/reports/invoice':'/api/ai/reports/payment','POST',
     isInvoice?{receipt_id:pitchInvoiceReceipt}:{sale_id:'pitch-FF-1058'});
   const model=d.generation==='REAL_AI_MODEL';
   setScreen(`<div class="result-label">SCENARIO 2 · FRAUD ANALYST REPORT · ${model?'REAL MODEL':'RULES-ONLY FALLBACK'}</div>
     <div class="huge ${d.decision.includes('STOP')||d.decision.includes('UNVERIFIED')?'stop':'good'}">${model?'AI REPORT':'REPORT PREVIEW'}</div>
     <div class="statusline">System decision: ${esc(d.decision)} · AI cannot change it.</div>
     <div class="artifact"><div class="arthead">${model?'AI-ASSISTED INVESTIGATION':'NO AI MODEL CONNECTED'}</div>
     <pre style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:310px;overflow-y:auto">${esc(d.report_text)}</pre></div>
     <div class="receipt">Signed metadata receipt: ${esc(d.receipt_id)}</div>
     ${guard('Model sees limited status data only; no full account details, invoice text or payment screenshots')}`,
     '02 · AI FRAUD REPORT',d.decision,model?'REAL AI narrative; system verdict untouched':'Rules-only: connect Ollama/API to demonstrate actual AI','card-two');
  }else if(action==='insider'){
   const d=await request('/api/pitch/chat-attack','POST');
   setScreen(`<div class="result-label">SCENARIO 3 · SOCIAL ENGINEERING / UNAUTHORISED CHANNEL</div><div class="huge stop">NOT HERE</div><div class="artifact"><div class="arthead">INCOMING MALICIOUS COMMAND · SIMULATOR</div><p>${esc(d.request)}</p></div><div class="chat">${esc(d.response)}<small>LOCAL OUTBOX · NOT SENT ON WHATSAPP</small></div><div class="proof"><span>Was the supplier banking record changed?</span>${pass(!d.change_performed)}</div><div class="note">The real API also rejects bookkeeper approval requests with HTTP 403; see automated test results. This chat preview is not a live WhatsApp bot.</div>`,
    '03 · CHANNEL ABUSE','DENIED','Untrusted chat cannot perform sensitive approvals; HTTP 403 covered by tests','card-three');
  }else if(action==='probe'){
   const d=await request('/api/pitch/security');const p=d.account_storage,r=d.role_probe,t=d.tenant_probe,i=d.integrity_probe;
   setScreen(`<div class="result-label">SCENARIO 3 · LIVE BACKEND SECURITY PROBES</div><div class="huge good">ATTACK SURFACE TEST</div><div class="proof"><span>Stolen suppliers table: HMAC fingerprint + ••••${esc(p.last4)}, no full account column</span>${pass(p.account_hmac_present&&!p.supplier_account_number_column_present)}</div><div class="proof"><span>Privilege escalation: bookkeeper rejected by actual owner-role guard (403)</span>${pass(r.bookkeeper_approval_denied)}</div><div class="proof"><span>Cross-business supplier read blocked by tenant-scoped SQL</span>${pass(t.second_business_fixture_exists&&!t.cross_business_supplier_visible)}</div><div class="proof"><span>Tampered audit copy detected by hash-integrity verification</span>${pass(i.audit_chain_intact&&i.altered_record_detected_in_memory)}</div><div class="note"><b>Scope matters:</b> API access-control HTTP tests are in our test suite; this panel exercises the same backend guards. The audit alteration happens in memory, not on the live DB. Supplier contact fields still need encryption; production KMS, MFA, freeze switches and independent pentest remain future work.</div>`,
    '03 · PLATFORM ATTACK','PROBES COMPLETE','Backend role, tenant, storage & audit integrity checks; not a pentest certificate','card-three');
  }
  $('message').textContent='Scenario action completed · Fictional test records';
 }catch(err){
  $('message').textContent='Demo failed: '+err.message;
  setScreen(`<div class="alert"><strong>Action failed — no passing result claimed</strong><p>${esc(err.message)}</p></div><div class="note">Stop server and run <code>python -m scripts.seed_pitch</code> to restore demo fixtures before retrying.</div>`,'DEMO ERROR','CHECK SETUP','Please inspect the error and re-seed synthetic fixtures','card-one');
 }finally{if(button)button.disabled=false;}
}
function updateClock(){let v=seconds;$('clock').textContent=String(Math.floor(v/60)).padStart(2,'0')+':'+String(v%60).padStart(2,'0');$('clock').style.color=v<=30?'#ffa49a':'';}
$('start-timer').onclick=()=>{if(timer)return;timer=setInterval(()=>{if(seconds>0){seconds--;updateClock()}else{clearInterval(timer);timer=null;}},1000)};
$('reset-timer').onclick=()=>{if(timer){clearInterval(timer);timer=null}seconds=300;updateClock()};
$('fullscreen').onclick=()=>{document.documentElement.requestFullscreen?.().catch(()=>{})};
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>run(b.dataset.action));
(async()=>{try{const me=await request('/api/me');if(me.role!=='owner'){location.assign('/');return;}
 const token=await request('/api/auth/csrf');csrf=token.csrf_token;
 const state=await request('/api/pitch/state');
 $('meta-status').textContent='Fixtures ready · sale '+state.sale_status+' · audit '+(state.audit_integrity?'valid':'invalid');
 $('message').textContent='Ready · all records fictional · no live API calls';
 }catch(err){$('message').textContent='Sign in as demo owner before entering Pitch Mode. '+err.message}})();
