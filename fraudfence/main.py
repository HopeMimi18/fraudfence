"""FraudFence SA: runnable security-focused prototype with synthetic bank data.

All bank/AVS success states in this WEB application are MOCK results; no integrations.
"""
from __future__ import annotations
import datetime as dt
import hmac
import json
import re
import secrets
import sqlite3
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Response, Cookie, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import (DB_PATH, ROOT, DEMO_MODE, SECURE_COOKIES, ALLOWED_ORIGINS,
                   HASHER, utcnow, connection, init_db, verify_password, hash_token,
                   fingerprint, normal_account, audit, audit_chain_valid,
                   create_receipt, public_key_b64, verify_signature, canonical, sign)

app = FastAPI(title="FraudFence SA — Web Security Prototype", version="0.2.0",
              description="Browser-based demo using synthetic data. No real bank or AVS integration.",
              docs_url="/docs" if DEMO_MODE else None,
              redoc_url=None, openapi_url="/openapi.json" if DEMO_MODE else None)
app.mount('/static', StaticFiles(directory=str(ROOT / 'static')), name='static')

# Browser defence-in-depth. CSP is intentionally compatible with this demo's inline
# style attributes; remove 'unsafe-inline' after the UI styling is fully externalised.
@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
        "base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
    )
    # Private pages/API output and receipts must not linger in browser/shared caches.
    response.headers['Cache-Control'] = 'no-store'
    if SECURE_COOKIES:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Do not accidentally run a non-demo version with insecure HTTP session cookies.
if not DEMO_MODE and not SECURE_COOKIES:
    raise RuntimeError('Non-demo mode requires HTTPS and FF_SECURE_COOKIES=1')
init_db()

# The fixture is exclusively for a synthetic hackathon dataset. In production a
# provider adapter must authenticate a real API response and validate supplier identity.
MOCK_AVS_FIXTURES = {
    ('DEMO-REG-001', '0001112223'): 'BuildRite Demo Supplies Pty Ltd',
    ('DEMO-REG-001', '0001112234'): 'BuildRite Demo Supplies Pty Ltd',  # legitimate changed account
    ('DEMO-REG-002', '0002223334'): 'Ubuntu Office Demo Trading Pty Ltd',
}


def abort(status, message):
    raise HTTPException(status_code=status, detail=message)


def record(row):
    return dict(row) if row is not None else None


def only(user, *roles):
    if user['role'] not in roles:
        abort(403, f"Requires role: {', '.join(roles)}")


def current(session: str | None = Cookie(default=None)):
    if not session:
        abort(401, 'Log in first')
    with connection() as c:
        u = c.execute('''SELECT users.*, sessions.csrf_hash, sessions.expires
            FROM sessions JOIN users ON sessions.user_id=users.id WHERE token_hash=?''',
                      (hash_token(session),)).fetchone()
    if not u or u['expires'] < utcnow():
        abort(401, 'Your session has expired')
    return record(u)


def mutating(user=Depends(current), x_csrf_token: str | None = Header(default=None)):
    if not x_csrf_token or not hmac.compare_digest(hash_token(x_csrf_token),user['csrf_hash']):
        abort(403, 'CSRF token missing or invalid')
    return user


def get_supplier(c, business_id, sid):
    s=c.execute('SELECT * FROM suppliers WHERE business_id=? AND id=?',(business_id,sid)).fetchone()
    if not s:
        abort(404, 'Supplier not found')
    return record(s)


def public_supplier(s):
    return {k:s[k] for k in ('id','name','expected_legal_name','registration','identity_source',
           'trusted_phone','phone_source','account_last4','verification','avs_result',
           'callback_at','created_at','updated_at')}


def check_avs(supplier, account):
    if not DEMO_MODE:
        return 'UNAVAILABLE'  # No live banking integration exists in this repository.
    if supplier['identity_source'] != 'independent_record':
        return 'IDENTITY_NOT_ESTABLISHED'
    key=(supplier['registration'].strip().upper(),normal_account(account))
    expected=MOCK_AVS_FIXTURES.get(key)
    if expected is None:
        return 'NO_MATCH'
    if re.sub(r'\W','',expected).lower() != re.sub(r'\W','',supplier['expected_legal_name']).lower():
        return 'NO_MATCH'
    return 'MOCK_MATCH'


class Login(BaseModel):
    email: str
    password: str

@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/health')
def health():
    return {'status':'ok','interface':'web','demo_mode':DEMO_MODE,'live_bank_connected':False,'live_avs_connected':False,'live_payment_provider_connected':False}

@app.post('/api/auth/login')
def login(payload: Login, response: Response):
    email=payload.email.lower().strip()
    error_after_commit=False
    with connection(write=True) as c:
        attempts=c.execute('SELECT * FROM login_attempts WHERE email=?',(email,)).fetchone()
        if attempts and attempts['locked_until'] and attempts['locked_until'] > utcnow():
            abort(429, 'Login temporarily locked after multiple failed attempts')
        user=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        # Mitigate timing difference between unknown and known accounts.
        fake_hash='$argon2id$v=19$m=65536,t=3,p=2$tbNt/J09Sck3zdNcAjzo2w$+WPbrIHXMrg8ZarQmYvST0fThRH/eYbgCXMRtTSPOcw'
        password_hash=user['password_hash'] if user else fake_hash
        valid=verify_password(password_hash,payload.password)
        if not user or not valid:
            count=(attempts['failures'] if attempts else 0)+1
            locked=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=15)).isoformat(timespec='seconds') if count>=5 else None
            c.execute('''INSERT INTO login_attempts(email,failures,locked_until) VALUES(?,?,?)
                ON CONFLICT(email) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until''',
                (email,count,locked))
            error_after_commit=True
        if not error_after_commit:
            c.execute('DELETE FROM login_attempts WHERE email=?',(email,))
            token=secrets.token_urlsafe(32)
            csrf=secrets.token_urlsafe(32)
            expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).isoformat(timespec='seconds')
            c.execute('INSERT INTO sessions(token_hash,user_id,csrf_hash,expires) VALUES(?,?,?,?)',
                     (hash_token(token),user['id'],hash_token(csrf),expiry))
            audit(c,user['business_id'],user['id'],'LOGIN',{'role':user['role']})
    if error_after_commit:
        abort(401, 'Invalid email or password')
    response.set_cookie('session',token,httponly=True,secure=SECURE_COOKIES,samesite='strict',max_age=28800,path='/')
    return {'csrf_token':csrf,'name':user['name'],'role':user['role'],'demo_mode':DEMO_MODE}

@app.get('/api/me')
def me(user=Depends(current)):
    return {'id':user['id'],'name':user['name'],'email':user['email'],'role':user['role'],
            'business_id':user['business_id'],'demo_mode':DEMO_MODE}

@app.get('/api/auth/csrf')
def refresh_csrf(session:str|None=Cookie(None), user=Depends(current)):
    csrf=secrets.token_urlsafe(32)
    with connection(write=True) as c:
        c.execute('UPDATE sessions SET csrf_hash=? WHERE token_hash=?',
                  (hash_token(csrf),hash_token(session)))
    return {'csrf_token':csrf}

@app.post('/api/auth/logout')
def logout(response:Response,session:str|None=Cookie(None),user=Depends(mutating)):
    with connection(write=True) as c:
        c.execute('DELETE FROM sessions WHERE token_hash=?',(hash_token(session),))
    response.delete_cookie('session',path='/')
    return {'ok':True}

class SupplierCreate(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    expected_legal_name:str=Field(min_length=2,max_length=130)
    registration:str=Field(min_length=4,max_length=40)
    identity_source:str=Field(pattern='^(invoice_only|independent_record)$')
    trusted_phone:str=Field(min_length=8,max_length=30)
    phone_source:str=Field(pattern='^(invoice_only|existing_contact|prior_record|official_verified)$')
    bank_account:str=Field(min_length=8,max_length=30)

@app.get('/api/suppliers')
def suppliers(user=Depends(current)):
    only(user,'owner','bookkeeper')
    with connection() as c:
        rows=c.execute('SELECT * FROM suppliers WHERE business_id=? ORDER BY created_at DESC',(user['business_id'],)).fetchall()
    return [public_supplier(record(x)) for x in rows]

@app.post('/api/suppliers')
def add_supplier(p:SupplierCreate,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    try: account=normal_account(p.bank_account)
    except ValueError as e: abort(422,str(e))
    sid=secrets.token_urlsafe(14)
    now=utcnow()
    with connection(write=True) as c:
        c.execute('''INSERT INTO suppliers(id,business_id,name,expected_legal_name,registration,identity_source,
            trusted_phone,phone_source,account_hmac,account_last4,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (sid,user['business_id'],p.name,p.expected_legal_name,p.registration,p.identity_source,
            p.trusted_phone,p.phone_source,fingerprint(account),account[-4:],now,now))
        audit(c,user['business_id'],user['id'],'SUPPLIER_CREATED',{'supplier_id':sid,'verification':'UNVERIFIED','last4':account[-4:]})
    return {'id':sid,'verification':'UNVERIFIED','message':'A saved record is NOT a verified supplier.'}

class BankCheck(BaseModel):
    bank_account:str

@app.post('/api/suppliers/{sid}/bank-check')
def supplier_bankcheck(sid:str,p:BankCheck,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    with connection(write=True) as c:
        s=get_supplier(c,user['business_id'],sid)
        try:
            if not hmac.compare_digest(fingerprint(p.bank_account),s['account_hmac']):
                abort(409,'Submitted account differs from the saved supplier account')
            result=check_avs(s,p.bank_account)
        except ValueError as e: abort(422,str(e))
        state='MOCK_BANK_CHECKED' if result=='MOCK_MATCH' else 'UNVERIFIED'
        # A previously verified supplier cannot be downgraded by a new random check; but
        # negative checks are blockers and must not be ignored.
        if s['verification']=='DEMO_VERIFIED' and result!='MOCK_MATCH':
            state='UNVERIFIED'
        elif s['verification']=='DEMO_VERIFIED' and result=='MOCK_MATCH':
            state='DEMO_VERIFIED'
        c.execute('UPDATE suppliers SET avs_result=?,verification=?,updated_at=? WHERE id=?',
                  (result,state,utcnow(),sid))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'MOCK_AVS_CHECK',{'supplier_id':sid,'result':result,'decision':state})
    return {'result':result,'verification':state,'receipt_id':receipt_id,'notice':'SIMULATED AVS result — NOT bank verification.'}

class Callback(BaseModel):
    last4_confirmed:str=Field(min_length=4,max_length=4)
    called_independently:bool
    owner_password:str=Field(min_length=1,max_length=200)


def require_owner_stepup(user, password):
    # Fresh password check for sensitive approvals in this local demo.
    # Production MUST replace/augment this with phishing-resistant MFA/passkeys.
    if not verify_password(user['password_hash'], password):
        abort(403, 'Owner re-authentication failed')

@app.post('/api/suppliers/{sid}/callback')
def verify_callback(sid:str,p:Callback,user=Depends(mutating)):
    only(user,'owner')
    require_owner_stepup(user,p.owner_password)
    with connection(write=True) as c:
        s=get_supplier(c,user['business_id'],sid)
        if not p.called_independently or s['phone_source']=='invoice_only':
            abort(409,'Independent call to previously trusted contact is required')
        if s['identity_source']!='independent_record' or s['avs_result']!='MOCK_MATCH':
            abort(409,'Trusted independent supplier identity and matching mock AVS check required')
        if not hmac.compare_digest(s['account_last4'],p.last4_confirmed):
            abort(409,'Phone-confirmed account digits do not match')
        now=utcnow()
        c.execute('UPDATE suppliers SET verification=?,callback_by=?,callback_at=?,updated_at=? WHERE id=?',
                  ('DEMO_VERIFIED',user['id'],now,now,sid))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'INDEPENDENT_CALLBACK_ATTESTED',{
            'supplier_id':sid,'last4':s['account_last4'],'manual_attestation':True,'bank_feed':'MOCK',
            'decision':'DEMO_VERIFIED'})
    return {'verification':'DEMO_VERIFIED','receipt_id':receipt_id,'notice':'Owner attested a call. Demo verified workflow; NOT independently certified.'}

class ChangeCreate(BaseModel):
    bank_account:str

@app.post('/api/suppliers/{sid}/changes')
def propose_change(sid:str,p:ChangeCreate,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    with connection(write=True) as c:
        s=get_supplier(c,user['business_id'],sid)
        try:
            normalized=normal_account(p.bank_account)
            key=fingerprint(normalized)
            result=check_avs(s,normalized)
        except ValueError as e: abort(422,str(e))
        if hmac.compare_digest(key,s['account_hmac']):
            abort(409,'This is already the saved supplier account')
        cid=secrets.token_urlsafe(14)
        c.execute('''INSERT INTO changes(id,supplier_id,business_id,account_hmac,account_last4,avs_result,
            initiated_by,created_at) VALUES(?,?,?,?,?,?,?,?)''',
            (cid,sid,user['business_id'],key,normalized[-4:],result,user['id'],utcnow()))
        audit(c,user['business_id'],user['id'],'SUPPLIER_CHANGE_PROPOSED',{
            'supplier_id':sid,'change_id':cid,'new_last4':normalized[-4:],'mock_avs':result})
    return {'change_id':cid,'status':'PENDING','mock_avs':result,
            'message':'No bank details were changed. Owner must independently call supplier and approve.'}

@app.get('/api/changes')
def changes(user=Depends(current)):
    only(user,'owner','bookkeeper')
    with connection() as c:
        r=c.execute('''SELECT changes.id,changes.supplier_id,changes.account_last4,changes.avs_result,
               changes.status,changes.created_at,suppliers.name AS supplier
               FROM changes JOIN suppliers ON suppliers.id=changes.supplier_id
               WHERE changes.business_id=? ORDER BY changes.created_at DESC''',(user['business_id'],)).fetchall()
    return [record(x) for x in r]

@app.post('/api/changes/{cid}/approve')
def approve_change(cid:str,p:Callback,user=Depends(mutating)):
    only(user,'owner')
    require_owner_stepup(user,p.owner_password)
    with connection(write=True) as c:
        change=c.execute('SELECT * FROM changes WHERE business_id=? AND id=?',(user['business_id'],cid)).fetchone()
        if not change: abort(404,'Change not found')
        if change['status']!='PENDING': abort(409,'Change is not pending')
        s=get_supplier(c,user['business_id'],change['supplier_id'])
        if s['verification']!='DEMO_VERIFIED':abort(409,'Current supplier not independently verified')
        if change['avs_result']!='MOCK_MATCH':abort(409,'AVS mismatch or unavailable: change denied')
        if not p.called_independently or s['phone_source']=='invoice_only':
            abort(409,'Call-back on an independently sourced supplier number required')
        if not hmac.compare_digest(change['account_last4'],p.last4_confirmed):
            abort(409,'Confirmed account last four digits do not match proposed account')
        now=utcnow()
        c.execute('''UPDATE suppliers SET account_hmac=?, account_last4=?, avs_result='MOCK_MATCH',
            verification='DEMO_VERIFIED',callback_by=?,callback_at=?,updated_at=? WHERE id=?''',
            (change['account_hmac'],change['account_last4'],user['id'],now,now,s['id']))
        c.execute('''UPDATE changes SET status='APPROVED',approved_by=?,approved_at=? WHERE id=?''',(user['id'],now,cid))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'SUPPLIER_CHANGE_APPROVED',{
            'supplier_id':s['id'],'change_id':cid,'last4':change['account_last4'],
            'manual_call_attestation':True,'avs':'MOCK_MATCH','decision':'APPROVED_CHANGE_DEMO'})
    return {'status':'APPROVED','receipt_id':receipt_id,'notice':'Demo account change approved through an authenticated owner session.'}

class InvoiceCheck(BaseModel):
    supplier_id:str
    invoice_reference:str=Field(min_length=2,max_length=80)
    amount_cents:int=Field(ge=1,le=100_000_000_000)
    bank_account:str
    sender_text:str=Field(default='',max_length=4000)
    source:str=Field(default='web_form',pattern='^web_form$')

@app.post('/api/checks/invoice')
def invoice_check(p:InvoiceCheck,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    with connection(write=True) as c:
        s=get_supplier(c,user['business_id'],p.supplier_id)
        try: h=fingerprint(p.bank_account)
        except ValueError as e: abort(422,str(e))
        count=c.execute('''SELECT COUNT(DISTINCT business_id) AS n FROM reports WHERE account_hmac=?
            AND business_id != ?''',(h,user['business_id'])).fetchone()['n']
        if not hmac.compare_digest(h,s['account_hmac']):
            decision='STOP_CHANGED_ACCOUNT'
            explanation='Account differs from your saved supplier record. Do not pay. Call the trusted supplier number.'
        elif s['verification']!='DEMO_VERIFIED':
            decision='HOLD_UNVERIFIED_SUPPLIER'
            explanation='Account matches a SAVED record, but supplier onboarding is not fully verified.'
        else:
            decision='MATCHES_VERIFIED_DEMO_RECORD'
            explanation='Account matches the locally verified demo supplier record; this does not authenticate the sender or guarantee safety.'
        if count >= 2 and decision != 'STOP_CHANGED_ACCOUNT':
            decision='HOLD_CORROBORATED_REPORTS'
            explanation='Two or more other businesses reported this account. Reports are allegations, not a fraud determination; investigate independently.'
        elif count >= 2:
            explanation += ' Multiple independent account reports also exist; treat them as unverified allegations.'
        # Never let untrusted invoice text influence a decision (including LLM prompt instructions).
        hints=[]
        if re.search(r'urgent|new bank|change[d]? (our|the) bank|act now',p.sender_text,re.I):
            hints.append('Pressure/change wording detected in untrusted content')
        payload=dict(supplier_id=s['id'],reference=p.invoice_reference,amount_cents=p.amount_cents,
                     submitted_last4=normal_account(p.bank_account)[-4:],decision=decision,
                     supplier_record_verification=s['verification'],external_reporters=count,
                     source=p.source,sender_authentication='NOT_CHECKED',warning_hints=hints)
        receipt_id=create_receipt(c,user['business_id'],user['id'],'INVOICE_CHECK',payload)
    return {'decision':decision,'explanation':explanation,'receipt_id':receipt_id,
            'sender_authentication':'NOT_CHECKED','warning_hints':hints,'external_reporters':count,
            'limitations':['Original email headers not available','Bank AVS is simulated',
                           'Supplier call-back is a human attestation']}

@app.get('/api/receipts/{receipt_id}')
def receipt_private(receipt_id:str,user=Depends(current)):
    only(user,'owner','bookkeeper')
    with connection() as c:
        r=c.execute('''SELECT receipts.*,audit_events.action,audit_events.payload_json FROM receipts
            JOIN audit_events ON audit_events.id=receipts.audit_id WHERE receipts.id=? AND receipts.business_id=?''',
            (receipt_id,user['business_id'])).fetchone()
        if not r:abort(404,'Receipt not found')
        whole=audit_chain_valid(c)
        rec=json.loads(r['record_json'])
        sig_valid=verify_signature(rec,r['signature'])
        ev=c.execute('SELECT entry_hash FROM audit_events WHERE id=?',(rec['audit_id'],)).fetchone()
    return {'record':rec,'action':r['action'],'details':json.loads(r['payload_json']),
            'signature_valid':sig_valid,'audit_hash_match':bool(ev and ev[0]==rec['audit_hash']),
            'log_chain_valid':whole,'verify_path':f'/verify/{receipt_id}'}

@app.get('/api/public/verify/{receipt_id}')
def verify_receipt(receipt_id:str):
    with connection() as c:
        r=c.execute('SELECT * FROM receipts WHERE id=?',(receipt_id,)).fetchone()
        if not r:abort(404,'Receipt not found')
        rec=json.loads(r['record_json'])
        e=c.execute('SELECT entry_hash FROM audit_events WHERE id=?',(rec['audit_id'],)).fetchone()
        valid=verify_signature(rec,r['signature']) and bool(e and e['entry_hash']==rec['audit_hash']) and audit_chain_valid(c)
    # Minimal disclosure; no identity, name, account, amount or invoice ID exposed.
    return {'receipt_id':receipt_id,'signature_and_log_valid':bool(valid),
            'timestamp':rec['recorded_at'],'demo_mode':rec['demo'],
            'notice':'Integrity verification only; not proof of payment, account ownership or legal compliance.'}

@app.get('/verify/{receipt_id}')
def verification_page(receipt_id:str):
    # UI fetches only minimal verification result.
    return FileResponse(ROOT / 'static' / 'verify.html')

@app.get('/api/audit/checkpoint')
def export_signed_checkpoint(user=Depends(current)):
    only(user,'owner')
    with connection() as c:
        if not audit_chain_valid(c):
            abort(409,'Audit log integrity check failed; checkpoint refused')
        latest=c.execute('SELECT id,entry_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
        if not latest:abort(409,'No audit events yet')
        # Export this to an OFF-SYSTEM location. In-process checkpoints cannot
        # protect against a DB + signing-key compromise.
        checkpoint={'version':1,'audit_id':latest['id'],'audit_hash':latest['entry_hash'],
                    'created_at':utcnow(),'demo':DEMO_MODE}
    return {'checkpoint':checkpoint,'signature':sign(checkpoint),'public_key':public_key_b64(),
            'instruction':'Store offline or with independent retention; this server does not anchor it externally.'}

@app.get('/api/audit/status')
def audit_status(user=Depends(current)):
    only(user,'owner')
    with connection() as c:
        valid=audit_chain_valid(c)
        latest=c.execute('SELECT id,entry_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
    return {'chain_valid':valid,'latest_id':latest['id'] if latest else None,
            'latest_hash':latest['entry_hash'] if latest else None,
            'public_verification_key':public_key_b64(),
            'limitation':'Without an independently retained checkpoint, a DB plus signing-key compromise can rewrite history.'}

class ReportCreate(BaseModel):
    account:str
    category:str=Field(pattern='^(suspected_invoice_diversion|fake_payment|other)$')
    details:str=Field(min_length=12,max_length=500)

@app.post('/api/reports')
def report_suspected(p:ReportCreate,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    try: bank=fingerprint(p.account)
    except ValueError as e:abort(422,str(e))
    id=secrets.token_urlsafe(14)
    with connection(write=True) as c:
        try:
            c.execute('''INSERT INTO reports(id,business_id,account_hmac,account_last4,category,details,created_at)
                VALUES(?,?,?,?,?,?,?)''',
                (id,user['business_id'],bank,normal_account(p.account)[-4:],p.category,p.details,utcnow()))
        except sqlite3.IntegrityError:
            abort(409,'This business already reported this account; duplicate reports do not increase the count')
        audit(c,user['business_id'],user['id'],'SUSPECTED_ACCOUNT_REPORTED',{
            'report_id':id,'account_last4':normal_account(p.account)[-4:],'classification':'ALLEGATION_ONLY'})
    return {'id':id,'status':'UNVERIFIED_REPORT','notice':'This report is an unverified allegation, not confirmed fraud.'}

@app.get('/api/reports')
def list_reports(user=Depends(current)):
    only(user,'owner','bookkeeper')
    with connection() as c:
        rows=c.execute('''SELECT account_last4,category,created_at,status FROM reports
            WHERE business_id=? ORDER BY created_at DESC''',(user['business_id'],)).fetchall()
    return [record(x) for x in rows]

class IncidentCreate(BaseModel):
    category:str=Field(pattern='^(invoice_diversion|fake_payment|account_compromise|phishing|other)$')
    description:str=Field(min_length=10,max_length=1000)

@app.post('/api/incidents')
def create_incident(p:IncidentCreate,user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    iid=secrets.token_urlsafe(14)
    now=utcnow()
    with connection(write=True) as c:
        c.execute('INSERT INTO incidents(id,business_id,created_by,category,description,created_at) VALUES(?,?,?,?,?,?)',
                  (iid,user['business_id'],user['id'],p.category,p.description,now))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'INCIDENT_REPORTED',{
            'incident_id':iid,'category':p.category,'decision':'INCIDENT_RECORDED','timestamp':now})
    return {'id':iid,'receipt_id':receipt_id,'steps':[
        'Immediately contact your bank using the number in its official app/card; request a fraud case/reference.',
        'Do not delete chats, email messages, invoices or transaction records; preserve originals securely.',
        'If an account was compromised, change credentials and revoke suspicious sessions using trusted channels.',
        'Record your incident timeline and consider reporting to SAPS and relevant fraud-support channels.'
    ],'notice':'Advice only. FraudFence cannot freeze, reverse or trace funds.'}

class SaleCreate(BaseModel):
    reference:str=Field(min_length=3,max_length=60,pattern='^[A-Za-z0-9_-]+$')
    amount_cents:int=Field(ge=1,le=100_000_000_000)

@app.post('/api/sales')
def add_sale(p:SaleCreate,user=Depends(mutating)):
    only(user,'owner','cashier')
    sid=secrets.token_urlsafe(14)
    with connection(write=True) as c:
        try:
            c.execute('INSERT INTO sales(id,business_id,amount_cents,reference,created_by,created_at) VALUES(?,?,?,?,?,?)',
                      (sid,user['business_id'],p.amount_cents,p.reference,user['id'],utcnow()))
        except sqlite3.IntegrityError:
            abort(409,'Reference already in use at this business; use a unique reference for each sale')
        audit(c,user['business_id'],user['id'],'SALE_LOGGED',{'sale_id':sid,'reference':p.reference,'amount_cents':p.amount_cents})
    return {'id':sid,'status':'UNVERIFIED','message':'No payment received or confirmed yet.'}

@app.get('/api/sales')
def list_sales(user=Depends(current)):
    only(user,'owner','cashier')
    with connection() as c:
        rows=c.execute('SELECT id,amount_cents,reference,status,created_at FROM sales WHERE business_id=? ORDER BY created_at DESC',(user['business_id'],)).fetchall()
    return [record(x) for x in rows]

class PaymentCreate(SaleCreate):
    state:str=Field(default='SETTLED',pattern='^(SETTLED|PENDING)$')

@app.post('/api/demo/payments')
def inject_payment(p:PaymentCreate,user=Depends(mutating)):
    only(user,'owner')
    if not DEMO_MODE:abort(403,'Demo payment injection disabled outside demo mode')
    pid=secrets.token_urlsafe(14)
    with connection(write=True) as c:
        c.execute('INSERT INTO payments(id,business_id,amount_cents,reference,state,source,received_at) VALUES(?,?,?,?,?,?,?)',
                  (pid,user['business_id'],p.amount_cents,p.reference,p.state,'MOCK_FEED',utcnow()))
        audit(c,user['business_id'],user['id'],'MOCK_PAYMENT_INJECTED',{'payment_id':pid,'reference':p.reference,'state':p.state})
    return {'payment_id':pid,'state':p.state,'notice':'FAKE transaction. No bank is connected.'}

@app.post('/api/sales/{sale_id}/reconcile')
def reconcile(sale_id:str,user=Depends(mutating)):
    only(user,'owner','cashier')
    with connection(write=True) as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',(sale_id,user['business_id'])).fetchone()
        if not sale:abort(404,'Sale not found')
        if sale['payment_id']:
            return {'status':sale['status'],'notice':'This sale was already matched; no second payment can be consumed'}
        matches=c.execute('''SELECT * FROM payments WHERE business_id=? AND reference=? AND amount_cents=?
            AND state='SETTLED' AND used_by_sale IS NULL''',
            (user['business_id'],sale['reference'],sale['amount_cents'])).fetchall()
        if len(matches)!=1:
            status='UNVERIFIED' if not matches else 'AMBIGUOUS'
            c.execute('UPDATE sales SET status=? WHERE id=?',(status,sale_id))
            audit(c,user['business_id'],user['id'],'PAYMENT_CHECK',{'sale_id':sale_id,'decision':status,'matches':len(matches)})
            return {'status':status,'notice':'Do not release goods. No unique settled transaction matched.'}
        payment=matches[0]
        c.execute('UPDATE payments SET used_by_sale=? WHERE id=? AND used_by_sale IS NULL',(sale_id,payment['id']))
        c.execute("UPDATE sales SET status='SIMULATED_PAYMENT_MATCH',payment_id=? WHERE id=?",(payment['id'],sale_id))
        audit(c,user['business_id'],user['id'],'MOCK_PAYMENT_RECONCILED',{'sale_id':sale_id,'payment_id':payment['id'],'decision':'SIMULATED_PAYMENT_MATCH'})
    return {'status':'SIMULATED_PAYMENT_MATCH','notice':'Demo payment matched; NOT confirmation of real funds.'}

class OwnerAttestation(BaseModel):
    checked_directly_in_bank_app:bool

@app.post('/api/sales/{sale_id}/owner-attest')
def attest(sale_id:str,p:OwnerAttestation,user=Depends(mutating)):
    only(user,'owner')
    if not p.checked_directly_in_bank_app:abort(409,'Owner must personally check the bank account')
    with connection(write=True) as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',(sale_id,user['business_id'])).fetchone()
        if not sale:abort(404,'Sale not found')
        if sale['payment_id']:abort(409,'Sale already matched to a simulated payment')
        c.execute("UPDATE sales SET status='OWNER_ATTESTED_NOT_BANK_VERIFIED' WHERE id=?",(sale_id,))
        audit(c,user['business_id'],user['id'],'OWNER_PAYMENT_ATTESTATION',{'sale_id':sale_id,'decision':'OWNER_ATTESTED_NOT_BANK_VERIFIED'})
    return {'status':'OWNER_ATTESTED_NOT_BANK_VERIFIED','notice':'Owner attestation only, NOT independent bank verification.'}

@app.middleware('http')
async def safe_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response
