"""FraudFence SA: runnable security-focused prototype with synthetic bank data.

All bank/AVS success states in this WEB application are MOCK results; no integrations.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Response, Cookie, Depends, Request, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .registry import check_registry
from . import external, ai_reports, invoice_extraction
from .notifications import enqueue_demo_notification
from .core import (DB_PATH, ROOT, DEMO_MODE, SECURE_COOKIES, ALLOWED_ORIGINS,
                   HASHER, utcnow, connection, init_db, verify_password, hash_token,
                   fingerprint, normal_account, audit, audit_chain_valid,
                   create_receipt, public_key_b64, verify_signature, canonical, sign)

app = FastAPI(title="FraudFence SA — Web Security Prototype", version="0.3.0",
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
           'callback_at','registry_result','registry_checked_at','created_at','updated_at')}


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


@app.get('/quick')
def quick_page(user=Depends(current)):
    """Minimal authenticated workflow for the three hackathon core features."""
    return FileResponse(ROOT / 'static' / 'quick.html')

class QuickCompanyCheck(BaseModel):
    registration: str = Field(min_length=4, max_length=40, pattern=r'^[A-Za-z0-9/-]+$')
    legal_name: str = Field(min_length=2, max_length=130)

@app.post('/api/quick/company')
def quick_company_check(p: QuickCompanyCheck, user=Depends(mutating)):
    """Registry evidence only; no supplier trust can be granted by this check.

    Mock records are accepted only when explicitly prefixed DEMO. Real companies
    fail closed without an authorised API subscription. The endpoint never
    turns a company name match into a supplier or payment approval.
    """
    only(user, 'owner', 'bookkeeper')
    number = p.registration.strip().upper()
    if number.startswith('DEMO-'):
        if not DEMO_MODE:
            abort(403, 'Synthetic registry fixtures disabled outside demo mode')
        result = check_registry(number, p.legal_name, 'independent_record', True)
        return {'source': 'SIMULATED_CIPC_FIXTURE', 'registration': number,
                'decision': result['result'], 'status': result['company_status'],
                'recent_director_change': result['recent_director_change'],
                'next_step': 'Simulation only. AVS and trusted callback are still required.',
                'verified_real_company': False}
    if not external.cipc_configured():
        return {'source': 'NOT_CONNECTED', 'registration': number,
                'decision': 'HOLD_CIPC_NOT_CHECKED', 'status': 'UNKNOWN',
                'recent_director_change': None, 'verified_real_company': False,
                'next_step': 'Open CIPC BizProfile as an authorised user and review the official record. No automated registry check occurred.'}
    try:
        checked = external.cipc_company_lookup(number, p.legal_name)
    except external.ConnectorError as exc:
        abort(503, str(exc))
    return {'source': checked['source'], 'registration': number,
            'decision': checked['verdict'], 'status': checked['company_status'],
            'recent_director_change': None,
            'verified_real_company': checked['verdict'] == 'CIPC_COMPANY_DETAILS_MATCH_ONLY',
            'next_step': 'This only checks company registration evidence. Verify bank account ownership and independently contact the supplier before trusting any payment instruction.'}

@app.get('/health')
def health():
    return {'status':'ok','interface':'web','demo_mode':DEMO_MODE,'live_bank_connected':False,'live_avs_connected':False,'live_payment_provider_connected':False,'live_cipc_connected':False,
            'ozow_staging_configured':external.ozow_configured(),
            'cipc_api_configured':external.cipc_configured()}

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

@app.get('/api/notifications')
def list_notifications(user=Depends(current)):
    """Owner-only notification previews, never proof of message delivery."""
    only(user,'owner')
    with connection() as c:
        items=c.execute("""SELECT id,kind,title,preview,created_at,read_at,delivery_status
            FROM notification_outbox WHERE business_id=? AND recipient_role='owner'
            ORDER BY created_at DESC, rowid DESC LIMIT 100""", (user['business_id'],)).fetchall()
        unread=c.execute("""SELECT COUNT(*) FROM notification_outbox
            WHERE business_id=? AND recipient_role='owner' AND read_at IS NULL""",
            (user['business_id'],)).fetchone()[0]
    return {'items':[record(x) for x in items], 'unread':unread,
            'channel':'WHATSAPP_STYLE_PREVIEW', 'real_messages_sent':False,
            'notice':'Local preview only. No Meta/WhatsApp API credentials or real delivery.'}


@app.post('/api/notifications/{notification_id}/read')
def mark_notification_read(notification_id:str,user=Depends(mutating)):
    only(user,'owner')
    with connection(write=True) as c:
        cur=c.execute("""UPDATE notification_outbox SET read_at=COALESCE(read_at,?)
            WHERE id=? AND business_id=? AND recipient_role='owner' """,
            (utcnow(), notification_id, user['business_id']))
        if cur.rowcount!=1:
            abort(404,'Notification not found')
    return {'ok':True,'notice':'Marked as read. No message was sent.'}


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

@app.post('/api/suppliers/{sid}/registry-check')
def supplier_registry_check(sid: str, user=Depends(mutating)):
    """Independent fictional company data, never a real CIPC result."""
    only(user, 'owner', 'bookkeeper')
    with connection(write=True) as c:
        s = get_supplier(c, user['business_id'], sid)
        evidence = check_registry(s['registration'], s['expected_legal_name'],
                                  s['identity_source'], DEMO_MODE)
        result = evidence['result']
        # Registry failures revoke prior demo verification. Even when a bank
        # account matches, an uncorroborated company is not trusted.
        if result != 'MOCK_MATCH':
            new_status = 'UNVERIFIED'
        elif s['verification'] == 'DEMO_VERIFIED' and s['avs_result'] == 'MOCK_MATCH':
            new_status = 'DEMO_VERIFIED'
        elif s['avs_result'] == 'MOCK_MATCH':
            new_status = 'MOCK_BANK_CHECKED'
        else:
            new_status = 'UNVERIFIED'
        now = utcnow()
        c.execute('''UPDATE suppliers SET registry_result=?,registry_checked_at=?,
                     verification=?,updated_at=? WHERE id=?''',
                  (result, now, new_status, now, sid))
        receipt_id = create_receipt(c, user['business_id'], user['id'], 'MOCK_REGISTRY_CHECK', {
            'supplier_id': sid, 'registry_result': result, 'company_status': evidence['company_status'],
            'recent_director_change': evidence['recent_director_change'],
            'decision': new_status, 'data_source': 'FICTIONAL_FIXTURE_ONLY'})
    return {**evidence, 'verification': new_status, 'receipt_id': receipt_id,
            'notice': 'SIMULATED company registry evidence. No CIPC connection or legal identity verification.'}


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
        if s['verification']=='DEMO_VERIFIED' and (result!='MOCK_MATCH' or s['registry_result']!='MOCK_MATCH'):
            state='UNVERIFIED'
        elif s['verification']=='DEMO_VERIFIED' and result=='MOCK_MATCH' and s['registry_result']=='MOCK_MATCH':
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
        if (s['identity_source']!='independent_record' or s['avs_result']!='MOCK_MATCH'
            or s['registry_result']!='MOCK_MATCH'):
            abort(409,'Independent company registry, mock AVS and trusted identity evidence must all match')
        if not hmac.compare_digest(s['account_last4'],p.last4_confirmed):
            abort(409,'Phone-confirmed account digits do not match')
        now=utcnow()
        c.execute('UPDATE suppliers SET verification=?,callback_by=?,callback_at=?,updated_at=? WHERE id=?',
                  ('DEMO_VERIFIED',user['id'],now,now,sid))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'INDEPENDENT_CALLBACK_ATTESTED',{
            'supplier_id':sid,'last4':s['account_last4'],'manual_attestation':True,'bank_feed':'MOCK','registry':'MOCK_MATCH',
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
        enqueue_demo_notification(c,user['business_id'],'SUPPLIER_CHANGE_PENDING','supplier-change:'+cid)
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
        if change['initiated_by']==user['id']:
            abort(409,'Maker-checker required: the proposer cannot approve their own change')
        s=get_supplier(c,user['business_id'],change['supplier_id'])
        if s['verification']!='DEMO_VERIFIED' or s['registry_result']!='MOCK_MATCH':
            abort(409,'Current supplier is not fully registry-checked and verified')
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
            'manual_call_attestation':True,'avs':'MOCK_MATCH','registry':'MOCK_MATCH','decision':'APPROVED_CHANGE_DEMO'})
    return {'status':'APPROVED','receipt_id':receipt_id,'notice':'Demo account change approved through an authenticated owner session.'}

@app.post('/api/invoices/extract')
async def extract_invoice(file:UploadFile=File(...),user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    if not file.filename or len(file.filename)>180:
        abort(422,'Provide a short invoice filename')
    # Even with a misleading MIME/extension, magic bytes and the parser check the file.
    if file.content_type not in ('application/pdf','image/png','image/jpeg','application/octet-stream'):
        abort(415,'Only PDF, PNG and JPEG invoices are supported')
    data=await file.read(invoice_extraction.MAX_BYTES+1)
    await file.close()
    if len(data)>invoice_extraction.MAX_BYTES:
        abort(413,'Invoice exceeds the 4 MB upload limit')
    try:
        txt,method=invoice_extraction.extract_text(data,file.filename)
        if not txt.strip():
            abort(422,'No readable invoice text found')
        result=invoice_extraction.parse_invoice(txt,method)
    except ValueError as exc:
        abort(422,str(exc))
    # The original file and its raw text are never saved. Only a minimal audit event.
    with connection(write=True) as c:
        audit(c,user['business_id'],user['id'],'INVOICE_EXTRACTED_FOR_REVIEW',
              {'extraction_method':method,'fields_found':result['fields_found'],
               'review_required':True})
    return result

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
        elif s['verification']!='DEMO_VERIFIED' or s['registry_result']!='MOCK_MATCH':
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
                     supplier_record_verification=s['verification'],registry_result=s['registry_result'],external_reporters=count,
                     source=p.source,sender_authentication='NOT_CHECKED',warning_hints=hints)
        receipt_id=create_receipt(c,user['business_id'],user['id'],'INVOICE_CHECK',payload)
    return {'decision':decision,'explanation':explanation,'receipt_id':receipt_id,
            'sender_authentication':'NOT_CHECKED','warning_hints':hints,'external_reporters':count,
            'limitations':['Original email headers not available','Bank AVS is simulated',
                           'Company registry evidence is simulated',
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
        enqueue_demo_notification(c,user['business_id'],'SALE_REVIEW_REQUIRED','sale:'+sid)
    return {'id':sid,'status':'UNVERIFIED','message':'No payment received or confirmed yet.'}

@app.get('/api/sales')
def list_sales(user=Depends(current)):
    only(user,'owner','cashier')
    with connection() as c:
        rows=c.execute('SELECT id,amount_cents,reference,status,created_at FROM sales WHERE business_id=? ORDER BY created_at DESC',(user['business_id'],)).fetchall()
    return [record(x) for x in rows]

@app.post('/api/sales/{sale_id}/request-owner-review')
def request_owner_review(sale_id:str,user=Depends(mutating)):
    only(user,'owner','cashier')
    with connection(write=True) as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',
                       (sale_id,user['business_id'])).fetchone()
        if not sale:abort(404,'Sale not found')
        if sale['status'] not in ('UNVERIFIED','AMBIGUOUS','OWNER_REPORTED_NOT_RECEIVED','PENDING_OWNER_REVIEW'):
            abort(409,'This payment status cannot be sent to manual review')
        if c.execute('SELECT 1 FROM ozow_payment_requests WHERE sale_id=? AND business_id=?',
                     (sale_id,user['business_id'])).fetchone():
            abort(409,'A provider payment exists; review the provider result instead')
        if sale['status']=='PENDING_OWNER_REVIEW':
            return {'status':'PENDING_OWNER_REVIEW','notice':'An owner-review request is already pending'}
        now=utcnow()
        c.execute('''INSERT INTO owner_payment_reviews(sale_id,business_id,requested_by,requested_at,review_status)
                     VALUES(?,?,?,?,?) ON CONFLICT(sale_id) DO UPDATE SET
                     requested_by=excluded.requested_by,requested_at=excluded.requested_at,
                     review_status='PENDING',reviewed_by=NULL,reviewed_at=NULL,evidence_source=NULL''',
                  (sale_id,user['business_id'],user['id'],now,'PENDING'))
        c.execute("UPDATE sales SET status='PENDING_OWNER_REVIEW' WHERE id=? AND business_id=?",
                  (sale_id,user['business_id']))
        audit(c,user['business_id'],user['id'],'OWNER_PAYMENT_REVIEW_REQUESTED',
              {'sale_id':sale_id,'reference':sale['reference'],'amount_cents':sale['amount_cents']})
        enqueue_demo_notification(c,user['business_id'],'SALE_REVIEW_REQUIRED','owner-review:'+sale_id+':'+now)
    return {'status':'PENDING_OWNER_REVIEW','notice':'Cashier must hold goods until the owner checks the receiving bank app.'}


class OwnerReviewDecision(BaseModel):
    decision:str=Field(pattern='^(CONFIRMED|NOT_RECEIVED)$')
    checked_directly_in_bank_app:bool
    checked_reference:str=Field(min_length=3,max_length=60)
    checked_amount_cents:int=Field(ge=1,le=100_000_000_000)
    owner_password:str=Field(min_length=1,max_length=200)


@app.post('/api/sales/{sale_id}/owner-review')
def owner_review(sale_id:str,p:OwnerReviewDecision,user=Depends(mutating)):
    only(user,'owner')
    if not verify_password(user['password_hash'],p.owner_password):
        abort(403,'Owner reauthentication failed')
    if not p.checked_directly_in_bank_app:
        abort(409,'Personally inspect the receiving bank app before recording a decision')
    with connection(write=True) as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',
                       (sale_id,user['business_id'])).fetchone()
        if not sale:abort(404,'Sale not found')
        check=c.execute('SELECT * FROM owner_payment_reviews WHERE sale_id=? AND business_id=?',
                        (sale_id,user['business_id'])).fetchone()
        if not check or check['review_status']!='PENDING' or sale['status']!='PENDING_OWNER_REVIEW':
            abort(409,'A pending owner-review request is required')
        if c.execute('SELECT 1 FROM ozow_payment_requests WHERE sale_id=? AND business_id=?',
                     (sale_id,user['business_id'])).fetchone():
            abort(409,'Manual review cannot override an external provider payment')
        if not hmac.compare_digest(sale['reference'],p.checked_reference) or sale['amount_cents']!=p.checked_amount_cents:
            abort(409,'Entered reference or amount does not match this sale')
        status='OWNER_ATTESTED_NOT_BANK_VERIFIED' if p.decision=='CONFIRMED' else 'OWNER_REPORTED_NOT_RECEIVED'
        now=utcnow()
        c.execute('''UPDATE owner_payment_reviews SET review_status=?, reviewed_by=?,
                     reviewed_at=?,evidence_source=? WHERE sale_id=? AND business_id=?''',
                  ('OWNER_CONFIRMED' if p.decision=='CONFIRMED' else 'NOT_RECEIVED',user['id'],now,
                   'OWNER_BANK_APP_ATTESTATION',sale_id,user['business_id']))
        c.execute('UPDATE sales SET status=? WHERE id=? AND business_id=?',
                  (status,sale_id,user['business_id']))
        audit(c,user['business_id'],user['id'],'OWNER_PAYMENT_REVIEW_DECISION',
              {'sale_id':sale_id,'decision':status,'method':'OWNER_BANK_APP_ATTESTATION'})
    return {'status':status,'source':'OWNER_MANUAL_ATTESTATION',
            'notice':'Owner recorded a manual banking-app review. FraudFence did NOT access or verify bank transactions independently.'}


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
        if c.execute('SELECT 1 FROM ozow_payment_requests WHERE sale_id=?',(sale_id,)).fetchone():
            return {'status':sale['status'],'notice':'Ozow payment is pending or being checked; use the Ozow verification endpoint'}
        if sale['status'] in ('PENDING_OWNER_REVIEW','OWNER_ATTESTED_NOT_BANK_VERIFIED','OWNER_REPORTED_NOT_RECEIVED'):
            return {'status':sale['status'],'notice':'Manual owner-review workflow controls this sale; simulated matching cannot override it'}
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
        enqueue_demo_notification(c,user['business_id'],'DEMO_PAYMENT_MATCHED','demo-payment:'+sale_id)
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
        if sale['status'] not in ('UNVERIFIED','AMBIGUOUS'):
            abort(409,'A pending or completed review cannot be overridden by legacy attestation')
        if c.execute('SELECT 1 FROM ozow_payment_requests WHERE sale_id=?',(sale_id,)).fetchone():
            abort(409,'External provider payment exists; manual attestation cannot replace it')
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


# Real API connectors. In this build Ozow is STAGING ONLY; we poll authenticated
# transaction data rather than accepting untrusted webhooks or redirect parameters.

@app.post('/api/suppliers/{sid}/cipc-api-check')
def cipc_api_check(sid:str, user=Depends(mutating)):
    only(user,'owner','bookkeeper')
    with connection() as c:
        s=get_supplier(c,user['business_id'],sid)
    if s['identity_source']!='independent_record':
        abort(409,'Expected supplier identity must be established independently before CIPC lookup')
    try:
        evidence=external.cipc_company_lookup(s['registration'],s['expected_legal_name'])
    except external.ConnectorError as exc:
        abort(503,str(exc))
    # Live CIPC evidence NEVER upgrades a supplier through mock bank verification.
    with connection(write=True) as c:
        c.execute('''INSERT INTO cipc_api_checks(supplier_id,business_id,result,checked_at)
                     VALUES(?,?,?,?) ON CONFLICT(supplier_id) DO UPDATE SET
                     result=excluded.result,checked_at=excluded.checked_at''',
                  (sid,user['business_id'],evidence['verdict'],utcnow()))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'LIVE_CIPC_CHECK',{
            'supplier_id':sid,'verdict':evidence['verdict'],
            'note':'This does not independently verify account ownership or invoice sender'})
    return {**evidence,'receipt_id':receipt_id,
            'supplier_live_verified':False,
            'note':'Requires authorised real AVS and callback before a LIVE supplier verification state is possible'}

@app.post('/api/sales/{sale_id}/ozow-staging/start')
def ozow_staging_start(sale_id:str,user=Depends(mutating)):
    only(user,'owner','cashier')
    with connection() as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',(sale_id,user['business_id'])).fetchone()
        if not sale: abort(404,'Sale not found')
        if sale['status'] in ('PENDING_OWNER_REVIEW','OWNER_ATTESTED_NOT_BANK_VERIFIED','OWNER_REPORTED_NOT_RECEIVED'):
            abort(409,'Manual owner review is active or completed; use a new sale for provider checkout')
        if sale['payment_id']:abort(409,'Sale already reconciled to another payment')
        if c.execute('SELECT 1 FROM ozow_payment_requests WHERE sale_id=?',(sale_id,)).fetchone():
            abort(409,'An Ozow staging request already exists for this sale')
    try:
        info=external.ozow_create_payment(sale['reference'],sale['amount_cents'],sale_id)
    except external.ConnectorError as exc:
        abort(503,str(exc))
    with connection(write=True) as c:
        c.execute('''INSERT INTO ozow_payment_requests(sale_id,business_id,provider_payment_id,status,created_at,updated_at)
                  VALUES(?,?,?,?,?,?)''',(sale_id,user['business_id'],info['payment_id'],
                      'OZOW_STAGING_PENDING',utcnow(),utcnow()))
        c.execute("UPDATE sales SET status='OZOW_STAGING_PENDING' WHERE id=?",(sale_id,))
        audit(c,user['business_id'],user['id'],'OZOW_STAGING_REQUEST_CREATED',{
              'sale_id':sale_id,'payment_id':info['payment_id'],'source':'OZOW_STAGING'})
    return {'status':'OZOW_STAGING_PENDING',**info,
            'notice':'Staging only; checkout is NOT proof of successful payment. Poll status after checkout.'}

@app.post('/api/sales/{sale_id}/ozow-staging/check')
def ozow_staging_check(sale_id:str,user=Depends(mutating)):
    only(user,'owner','cashier')
    with connection() as c:
        sale=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',(sale_id,user['business_id'])).fetchone()
        if not sale: abort(404,'Sale not found')
        payment=c.execute('''SELECT * FROM ozow_payment_requests WHERE sale_id=? AND business_id=?''',
                          (sale_id,user['business_id'])).fetchone()
        if not payment:abort(404,'No Ozow payment started for this sale')
    try:
        transactions=external.ozow_list_transactions(payment['provider_payment_id'])
        decision,transaction_id=external.assess_ozow_transactions(
            transactions,sale['reference'],sale['amount_cents'],external.os.environ['FF_OZOW_SITE_CODE'])
    except external.ConnectorError as exc:
        abort(503,str(exc))
    with connection(write=True) as c:
        # Never downgrade a previously confirmed result through an unrelated poll.
        old=c.execute('SELECT * FROM ozow_payment_requests WHERE sale_id=?',(sale_id,)).fetchone()
        if old['status']=='OZOW_STAGING_PROVIDER_CONFIRMED' and decision!='OZOW_STAGING_PROVIDER_CONFIRMED':
            decision='HOLD_PROVIDER_STATUS_CHANGED'
        try:
            c.execute('''UPDATE ozow_payment_requests SET status=?,transaction_id=?,updated_at=? WHERE sale_id=?''',
                      (decision,transaction_id,utcnow(),sale_id))
        except sqlite3.IntegrityError:
            abort(409,'This provider transaction is already associated with another sale')
        c.execute('UPDATE sales SET status=? WHERE id=?',(decision,sale_id))
        receipt_id=create_receipt(c,user['business_id'],user['id'],'OZOW_STAGING_TRANSACTION_CHECK',{
            'sale_id':sale_id,'provider_payment_id':payment['provider_payment_id'],
            'transaction_id':transaction_id,'decision':decision,'source':'OZOW_STAGING_SERVER_API'})
        enqueue_demo_notification(c,user['business_id'],'OZOW_STAGING_RESULT',
                                  'ozow:'+sale_id+':'+decision)
    return {'status':decision,'transaction_id':transaction_id,'receipt_id':receipt_id,
            'notice':'Ozow STAGING transaction result; not evidence of actual bank deposit or a third-party EFT.'}

# ==============================================================
# HACKSECURE STAGE MODE. All providers and messages are SYNTHETIC.
# Dedicated scripted probes reuse production route guards and workflow
# functions but cannot be used outside local demo mode.
# ==============================================================
PITCH_SUPPLIER = 'pitch-buildrite'
PITCH_CHANGE = 'pitch-CH-031'
PITCH_SALE = 'pitch-FF-1058'
PITCH_FRAUD_ACCOUNT = '1234567890'  # fixed FICTIONAL test input; never persists in full


def pitch_gate(user):
    if not DEMO_MODE:
        abort(404, 'Pitch mode is disabled outside demo mode')
    only(user, 'owner')
    if user['business_id'] != 'demo-shop':
        abort(403, 'Only the fictional pitch-demo business may use Pitch Mode')
    with connection() as c:
        if not c.execute('SELECT 1 FROM suppliers WHERE id=? AND business_id=?',
                         (PITCH_SUPPLIER,user['business_id'])).fetchone():
            abort(409,'Pitch fixtures missing: run python -m scripts.seed_pitch')


@app.get('/pitch')
def pitch_page(user=Depends(current)):
    pitch_gate(user)
    return FileResponse(ROOT / 'static' / 'pitch.html')


@app.get('/api/pitch/state')
def pitch_state(user=Depends(current)):
    pitch_gate(user)
    with connection() as c:
        supplier=get_supplier(c,user['business_id'],PITCH_SUPPLIER)
        change=c.execute('SELECT status FROM changes WHERE id=? AND business_id=?',
                         (PITCH_CHANGE,user['business_id'])).fetchone()
        sale=c.execute('SELECT status FROM sales WHERE id=? AND business_id=?',
                       (PITCH_SALE,user['business_id'])).fetchone()
        integrity=audit_chain_valid(c)
    return {'business':'Mokoena Hardware (FICTIONAL)',
            'supplier':'BuildRite Supplies (FICTIONAL)',
            'invoice':'INV-2207','amount_cents':1840000,
            'saved_last4':supplier['account_last4'],'submitted_last4':'7890',
            'change':'CH-031','change_status':change['status'] if change else 'NOT_SEEDED',
            'sale':'FF-1058','sale_amount_cents':85000,
            'sale_status':sale['status'] if sale else 'NOT_SEEDED',
            'audit_integrity':integrity,
            'providers':'SIMULATED CIPC, AVS, callback and payment; no real WhatsApp delivery'}


@app.get('/api/pitch/problem')
def pitch_problem(user=Depends(current)):
    """Present an attacker-controlled invoice and fake POP without treating either as proof.

    Read-only story data, drawn from the current fictional fixtures; NO live
    registry/payment lookup and NO verification decision is executed here.
    """
    pitch_gate(user)
    with connection() as c:
        supplier=get_supplier(c,user['business_id'],PITCH_SUPPLIER)
        sale=c.execute('SELECT reference,amount_cents,status FROM sales WHERE id=? AND business_id=?',
                       (PITCH_SALE,user['business_id'])).fetchone()
        if not sale:
            abort(409,'Pitch sale fixture missing')
    return {'type':'FICTIONAL_ATTACK_EXAMPLE',
            'business':'Mokoena Hardware (fictional)',
            'supplier':'BuildRite Supplies (fictional)',
            'invoice':{'reference':'INV-2207','amount_cents':1840000,
                       'claimed_sender':'accounts@buildrite-supplies.co',
                       'claimed_message':'URGENT: We have changed banks. Please pay today.',
                       'submitted_last4':'7890',
                       'previously_trusted_last4':supplier['account_last4']},
            'payment_claim':{'sale_reference':sale['reference'],
                             'amount_cents':sale['amount_cents'],
                             'customer_claim':'Here is my proof of payment. Please release the cement.',
                             'system_status':sale['status']},
            'warning':'These are fictional attacker-controlled claims, NOT verified company data or actual bank funds.'}


@app.post('/api/pitch/invoice')
def pitch_invoice(user=Depends(mutating)):
    pitch_gate(user)
    # REUSES the actual invoice decision logic and creates a signed receipt.
    outcome=invoice_check(InvoiceCheck(supplier_id=PITCH_SUPPLIER,
        invoice_reference='INV-2207',amount_cents=1840000,
        bank_account=PITCH_FRAUD_ACCOUNT,
        sender_text='URGENT: new bank details. Pay today.',source='web_form'),user=user)
    if outcome['decision']!='STOP_CHANGED_ACCOUNT':
        abort(409,'Expected STOP not reached; reset pitch fixtures')
    return {'decision':outcome['decision'],'receipt_id':outcome['receipt_id'],
            'channel':'WHATSAPP-STYLE PREVIEW · NOT SENT',
            'message':("STOP. Don't pay INV-2207.\n"
                       "Invoice account ••••7890 is NOT BuildRite's saved account ••••5678.\n"
                       "Call BuildRite using the previously trusted supplier number, not the invoice.\n"
                       "Security word: Marula"),
            'evidence':'Actual account-fingerprint comparison + signed receipt; fictional accounts.'}


@app.post('/api/pitch/three-sources')
def pitch_three_sources(user=Depends(mutating)):
    pitch_gate(user)
    # Registry check is the EXISTING server-side function. The mock adapter
    # reports a recent director change and automatically revokes old demo trust.
    registry=supplier_registry_check(PITCH_SUPPLIER,user=user)
    with connection(write=True) as c:
        s=get_supplier(c,user['business_id'],PITCH_SUPPLIER)
        change=c.execute('SELECT * FROM changes WHERE id=? AND business_id=?',
                         (PITCH_CHANGE,user['business_id'])).fetchone()
        if not change:abort(409,'Pitch change fixture missing')
        avs=check_avs(s,PITCH_FRAUD_ACCOUNT)
        # The callback is a *scripted fictitious answer*, not a real phone call.
        # NO phone callback is silently attested or auto-approved.
        decision='HOLD' if registry['result']!='MOCK_MATCH' or avs!='MOCK_MATCH' else 'REVIEW_REQUIRED'
        if decision=='HOLD':
            c.execute("UPDATE changes SET status='HOLD' WHERE id=? AND business_id=?",(PITCH_CHANGE,user['business_id']))
        receipt=create_receipt(c,user['business_id'],user['id'],'PITCH_MULTISOURCE_ASSESSMENT',{
          'supplier_id':PITCH_SUPPLIER,'registry':registry['result'],'bank_avs':avs,
          'callback':'SIMULATED_SUPPLIER_DENIES_CHANGE','decision':decision,
          'source':'ALL_SYNTHETIC'})
        # A real event-driven template is created; no WhatsApp message is sent.
        enqueue_demo_notification(c,user['business_id'],'SUPPLIER_CHANGE_PENDING',
                                  'pitch:hold:'+PITCH_CHANGE)
    return {'decision':decision,'registry':{
              'result':registry['result'],'director_changed_days_ago':6,
              'source':'MOCK_CIPC'},'bank':{'result':avs,'source':'MOCK_AVS'},
            'callback':{'result':'DENIED_CHANGE','text':"We haven't changed banks.",
                        'source':'PRELOADED FICTIONAL SCRIPT — NOT A LIVE CALL'},
            'change_status':decision,'saved_last4':'5678',
            'receipt_id':receipt,
            'message':'No banking details changed. Owner notification stored as unsent preview.'}


@app.post('/api/pitch/chat-attack')
def pitch_chat_attack(user=Depends(mutating)):
    pitch_gate(user)
    with connection(write=True) as c:
        # A chat request is never passed to any trust-changing API.
        enqueue_demo_notification(c,user['business_id'],'SUPPLIER_CHANGE_PENDING',
                                  'pitch:chat-refusal')
    return {'decision':'NOT_HERE',
            'channel':'WHATSAPP-STYLE SIMULATOR — NOT A REAL WHATSAPP BOT',
            'request':'approve new account BuildRite 1234567890',
            'response':('Not here.\nBank details cannot be changed via WhatsApp. '
                        'Only the authenticated web app permits owner approval.\n'
                        'Owner notified in local outbox.\nSecurity word: Marula'),
            'change_performed':False}


@app.post('/api/pitch/payment-check')
def pitch_payment_check(user=Depends(mutating)):
    pitch_gate(user)
    # Same business-scoped sale status used by the normal cashier endpoint.
    with connection() as c:
        sale=c.execute('SELECT status,reference,amount_cents FROM sales WHERE id=? AND business_id=?',
                       (PITCH_SALE,user['business_id'])).fetchone()
    if not sale:abort(409,'Pitch sale missing')
    response=('Not yet. FF-1058 · R850 · no verified payment evidence. '
              'Do NOT release the goods.')
    if sale['status']=='SIMULATED_PAYMENT_MATCH':
        response=('FICTIONAL payment matched for FF-1058 · R850. '
                  'SIMULATED TEST DATA: not real funds. DO NOT release actual goods.')
    return {'status':sale['status'],'message':response,
            'channel':'CASHIER-STYLE SIMULATOR · NOT WHATSAPP DELIVERY',
            'amount_cents':sale['amount_cents']}


@app.post('/api/pitch/mock-payment')
def pitch_mock_payment(user=Depends(mutating)):
    pitch_gate(user)
    with connection() as c:
        sale=c.execute('SELECT status FROM sales WHERE id=? AND business_id=?',
                       (PITCH_SALE,user['business_id'])).fetchone()
    if not sale:abort(409,'Pitch sale missing')
    if sale['status']=='SIMULATED_PAYMENT_MATCH':
        return {'status':'SIMULATED_PAYMENT_MATCH','message':'Already matched; repeat is idempotent. No real money.'}
    inject_payment(PaymentCreate(reference='FF-1058',amount_cents=85000,state='SETTLED'),user=user)
    result=reconcile(PITCH_SALE,user=user)
    return {'status':result['status'],'message':'Synthetic bank feed only; NOT a live Ozow or bank confirmation.'}


@app.get('/api/pitch/security')
def pitch_security(user=Depends(current)):
    pitch_gate(user)
    with connection() as c:
        s=get_supplier(c,user['business_id'],PITCH_SUPPLIER)
        cols={r['name'] for r in c.execute('PRAGMA table_info(suppliers)')}
        foreign=c.execute('SELECT * FROM suppliers WHERE id=? AND business_id=?',
                          ('pitch-dube-supplier',user['business_id'])).fetchone()
        other_exists=c.execute('SELECT 1 FROM suppliers WHERE id=? AND business_id=?',
                              ('pitch-dube-supplier','other-shop')).fetchone()
        bk=c.execute("SELECT * FROM users WHERE business_id=? AND role='bookkeeper' LIMIT 1",
                     (user['business_id'],)).fetchone()
        chain=audit_chain_valid(c)
        last=c.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
        # Verify that altering the last event's contents WITHOUT recomputing its
        # stored hash would fail. Do NOT mutate the actual database.
        altered=dict(business_id=last['business_id'],actor=last['actor'],action=last['action'],
                     payload={'forged':'changed'},recorded_at=last['recorded_at'],prev_hash=last['prev_hash'])
        import hashlib
        altered_digest=hashlib.sha256(canonical(altered).encode()).hexdigest()
        altered_detected=not hmac.compare_digest(altered_digest,last['entry_hash'])
    try:
        only(record(bk),'owner')
        bookkeeper_denied=False
    except HTTPException as exc:
        bookkeeper_denied=exc.status_code==403
    return {'account_storage':{'supplier_account_number_column_present':'bank_account' in cols,
             'account_hmac_present':bool(s['account_hmac']),'last4':s['account_last4'],
             'note':'HMAC fingerprints are not encryption. Supplier phone numbers currently remain plaintext.'},
            'role_probe':{'bookkeeper_approval_denied':bookkeeper_denied,'http_status_equivalent':403 if bookkeeper_denied else 200,
                          'note':'Uses the same role guard; see tests for an actual HTTP 403 response.'},
            'tenant_probe':{'second_business_fixture_exists':bool(other_exists),
                           'cross_business_supplier_visible':bool(foreign),
                           'expected_http_behavior':'404 NOT FOUND'},
            'integrity_probe':{'audit_chain_intact':chain,'altered_record_detected_in_memory':altered_detected,
                               'note':'No database row was modified. External immutable checkpoints are not implemented.'},
            'not_implemented':['Real CIPC/AVS/Ozow confirmation','WhatsApp delivery',
              'Full sensitive-field encryption','Passkeys/MFA','Cooling-off workflow',
              'Emergency approval freeze','Automated regulator notices or recovery']}

# AI REPORTS — model output is analysis only, never an authorisation or payment decision.
class AIInvoiceReportRequest(BaseModel):
    receipt_id: str = Field(min_length=8, max_length=100)

class AIPaymentReportRequest(BaseModel):
    sale_id: str = Field(min_length=4, max_length=100)

@app.get('/api/ai/status')
def ai_status(user=Depends(current)):
    conf = ai_reports.configuration()
    return {'provider': conf['provider'], 'model': conf['model'],
            'configured': conf['configured'],
            'status': 'MODEL_CONFIGURED' if conf['configured'] else 'RULES_ONLY_NO_AI_MODEL',
            'privacy': 'Demo only: send only allowlisted statuses; no names, bank details, raw invoices or screenshots.',
            'guarantee': 'AI writes an explanation, never changes payment or supplier verification status.'}


def _make_ai_report(user, case_type, facts, result, actions, source_id):
    if not DEMO_MODE:
        abort(403, 'AI report feature restricted to fictional demo data pending privacy/security review')
    narrative = None
    model_error = None
    conf = ai_reports.configuration()
    if conf['configured']:
        try:
            narrative = ai_reports.generate(facts)
        except RuntimeError:
            model_error = 'Model unavailable: evidence-only report returned, NOT AI-generated.'
    source = 'REAL_AI_MODEL' if narrative else 'RULE_BASED_REPORT_NO_AI'
    # Authoritative verdict and actions are from FraudFence, never from an LLM.
    header = ('FRAUDFENCE SA — ' + case_type.upper().replace('_', ' ') + ' REPORT\n'
              'SYSTEM FINDING (NOT WRITTEN BY AI): ' + result + '\n'
              'Evidence source: LOCAL SYNTHETIC DATA; NOT A LIVE BANK/CIPC CHECK.\n'
              'Data protection: no full account number or invoice message sent to AI.\n\n')
    analysis = ('AI-ASSISTED EXPLANATION (not verification):\n' + narrative + '\n\n') if narrative else (
        'EXPLANATION: AI model not connected/available; evidence-only report generated.\n\n')
    report_text = header + analysis + ('REQUIRED HUMAN NEXT STEPS (RULE-BASED):\n' +
        '\n'.join(str(i+1)+'. '+x for i,x in enumerate(actions)) +
        '\n\nThis report cannot confirm actual bank funds, approve a supplier, or override a HOLD.')
    report_hash = hashlib.sha256(report_text.encode()).hexdigest()
    with connection(write=True) as c:
        receipt_id = create_receipt(c, user['business_id'], user['id'], 'AI_REPORT_CREATED', {
            'case_type': case_type, 'source_id': source_id, 'generation': source,
            'sha256_of_downloadable_report': report_hash, 'decision': facts['decision']})
    return {'case_type': case_type, 'generation': source,
            'model': conf['model'] if narrative else None, 'source_id': source_id,
            'decision': facts['decision'], 'finding': result,
            'next_steps': actions, 'model_error': model_error,
            'report_text': report_text, 'report_sha256': report_hash,
            'receipt_id': receipt_id,
            'warning': 'AI is explanatory only. Synthetic data is NOT bank or CIPC verification.'}


@app.post('/api/ai/reports/invoice')
def ai_invoice_report(p: AIInvoiceReportRequest, user=Depends(mutating)):
    only(user, 'owner', 'bookkeeper')
    if not DEMO_MODE: abort(403, 'AI reports disabled for real customer data')
    with connection() as c:
        row = c.execute('''SELECT receipts.*, audit_events.action, audit_events.payload_json
             FROM receipts JOIN audit_events ON audit_events.id=receipts.audit_id
             WHERE receipts.id=? AND receipts.business_id=?''',
             (p.receipt_id, user['business_id'])).fetchone()
        if not row or row['action'] != 'INVOICE_CHECK': abort(404, 'Invoice check receipt not found')
        rec = json.loads(row['record_json'])
        if not verify_signature(rec, row['signature']) or not audit_chain_valid(c):
            abort(409, 'Receipt/audit integrity check failed: refusing AI report')
        payload = json.loads(row['payload_json'])
    facts, finding, actions = ai_reports.facts_for_invoice(payload)
    return _make_ai_report(user, 'invoice', facts, finding, actions, p.receipt_id)


@app.post('/api/ai/reports/payment')
def ai_payment_report(p: AIPaymentReportRequest, user=Depends(mutating)):
    only(user, 'owner', 'cashier')
    if not DEMO_MODE: abort(403, 'AI reports disabled for real customer data')
    with connection() as c:
        sale = c.execute('SELECT id,status FROM sales WHERE id=? AND business_id=?',
                         (p.sale_id, user['business_id'])).fetchone()
        if not sale: abort(404, 'Sale not found')
        facts, finding, actions = ai_reports.facts_for_payment(sale['status'])
    return _make_ai_report(user, 'payment', facts, finding, actions, p.sale_id)
