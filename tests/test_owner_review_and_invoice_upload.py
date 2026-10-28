"""Core owner-review and ephemeral invoice-upload security tests."""
import io
from pathlib import Path
from tests.test_api import context, login, PASSWORD
import fraudfence.core as core
from fraudfence.invoice_extraction import parse_invoice

SAMPLE=core.ROOT/'docs'/'DEMO_INVOICE_INV-2207.pdf'

def test_pdf_upload_extracts_without_persisting_bank_data(context):
    c,db=context;h=login(c,'demo-bookkeeper@fraudfence.test')
    body=SAMPLE.read_bytes()
    resp=c.post('/api/invoices/extract',headers=h,files={'file':('invoice.pdf',body,'application/pdf')})
    assert resp.status_code==200,resp.text
    d=resp.json()
    assert d['invoice_reference']=='INV-2207'
    assert d['amount_zar']=='18400.00'
    assert d['bank_account']=='0009998877'
    assert d['review_required'] is True
    assert d['extraction_method']=='PDF_TEXT'
    assert d['legal_name'] == 'BuildRite Demo Supplies Pty Ltd'  # document claim, not verified identity
    assert any('UNTRUSTED invoice' in note for note in d['warnings'])
    with db.connection() as con:
        rows=con.execute("SELECT payload_json FROM audit_events WHERE action='INVOICE_EXTRACTED_FOR_REVIEW'").fetchall()
    assert rows and '0009998877' not in rows[-1]['payload_json']
    assert body[:10] not in rows[-1]['payload_json'].encode()
    assert c.post('/api/checks/invoice',headers=h,json={'supplier_id':'demo-buildrite','invoice_reference':d['invoice_reference'],
      'amount_cents':1840000,'bank_account':d['bank_account']}).json()['decision']=='STOP_CHANGED_ACCOUNT'


def test_invoice_upload_rejects_cashier_oversize_invalid_and_missing_csrf(context):
    c,_=context;owner=login(c)
    assert c.post('/api/invoices/extract',files={'file':('inv.pdf',SAMPLE.read_bytes(),'application/pdf')}).status_code==403
    cashier=login(c,'demo-cashier@fraudfence.test')
    assert c.post('/api/invoices/extract',headers=cashier,files={'file':('inv.pdf',SAMPLE.read_bytes(),'application/pdf')}).status_code==403
    owner=login(c)
    assert c.post('/api/invoices/extract',headers=owner,files={'file':('inv.pdf',b'not-a-real-pdf','application/pdf')}).status_code==422
    big=b'%PDF-'+b'x'*(4*1024*1024)
    assert c.post('/api/invoices/extract',headers=owner,files={'file':('inv.pdf',big,'application/pdf')}).status_code==413


def test_invoice_multiple_account_numbers_fail_closed():
    d=parse_invoice('Invoice No: INV-2207\nTotal Amount Due: R18,400.00\nAccount Number: 0009998877\nAccount No: 0001112223')
    assert d['bank_account'] is None
    assert any('Multiple possible bank account' in warning for warning in d['warnings'])


def test_cashier_requests_and_owner_reviews_with_password(context):
    c,db=context
    cashier=login(c,'demo-cashier@fraudfence.test')
    sale=c.post('/api/sales',headers=cashier,json={'reference':'OWNER-001','amount_cents':85000}).json()
    sid=sale['id']
    assert c.post(f'/api/sales/{sid}/owner-review',headers=cashier,json={
         'decision':'CONFIRMED','checked_directly_in_bank_app':True,'checked_reference':'OWNER-001',
         'checked_amount_cents':85000,'owner_password':PASSWORD}).status_code==403
    r=c.post(f'/api/sales/{sid}/request-owner-review',headers=cashier)
    assert r.status_code==200 and r.json()['status']=='PENDING_OWNER_REVIEW'
    assert c.post(f'/api/sales/{sid}/request-owner-review',headers=cashier).status_code==200
    assert c.get('/api/sales').json()[0]['status']=='PENDING_OWNER_REVIEW'
    owner=login(c)
    req={'decision':'CONFIRMED','checked_directly_in_bank_app':True,'checked_reference':'OWNER-001',
         'checked_amount_cents':85000,'owner_password':PASSWORD}
    assert c.post(f'/api/sales/{sid}/owner-review',headers=owner,json={**req,'owner_password':'wrong'}).status_code==403
    assert c.post(f'/api/sales/{sid}/owner-review',headers=owner,json={**req,'checked_amount_cents':90000}).status_code==409
    assert c.post(f'/api/sales/{sid}/owner-review',headers=owner,json={**req,'checked_directly_in_bank_app':False}).status_code==409
    yes=c.post(f'/api/sales/{sid}/owner-review',headers=owner,json=req)
    assert yes.status_code==200,yes.text
    assert yes.json()['status']=='OWNER_ATTESTED_NOT_BANK_VERIFIED'
    assert yes.json()['source']=='OWNER_MANUAL_ATTESTATION'
    assert c.post(f'/api/sales/{sid}/owner-review',headers=owner,json=req).status_code==409
    cashier=login(c,'demo-cashier@fraudfence.test')
    assert c.post(f'/api/sales/{sid}/request-owner-review',headers=cashier).status_code==409
    assert c.post(f'/api/sales/{sid}/reconcile',headers=cashier).json()['status']=='OWNER_ATTESTED_NOT_BANK_VERIFIED'
    assert c.get('/api/sales').json()[0]['status']=='OWNER_ATTESTED_NOT_BANK_VERIFIED'
    with db.connection() as con:
        audit=con.execute("SELECT action FROM audit_events WHERE action LIKE 'OWNER_PAYMENT_REVIEW_%'").fetchall()
    assert len(audit)==2


def test_owner_can_record_not_received_and_re_request(context):
    c,_=context;cashier=login(c,'demo-cashier@fraudfence.test')
    sid=c.post('/api/sales',headers=cashier,json={'reference':'OWNER-002','amount_cents':85000}).json()['id']
    c.post(f'/api/sales/{sid}/request-owner-review',headers=cashier)
    owner=login(c)
    req={'decision':'NOT_RECEIVED','checked_directly_in_bank_app':True,'checked_reference':'OWNER-002',
         'checked_amount_cents':85000,'owner_password':PASSWORD}
    r=c.post(f'/api/sales/{sid}/owner-review',headers=owner,json=req)
    assert r.json()['status']=='OWNER_REPORTED_NOT_RECEIVED'
    cashier=login(c,'demo-cashier@fraudfence.test')
    assert c.post(f'/api/sales/{sid}/request-owner-review',headers=cashier).json()['status']=='PENDING_OWNER_REVIEW'


def test_cross_business_and_bookkeeper_denial(context):
    c,_=context;owner=login(c)
    sid=c.post('/api/sales',headers=owner,json={'reference':'OWNER-003','amount_cents':4500}).json()['id']
    other=login(c,'other-owner@fraudfence.test')
    assert c.post(f'/api/sales/{sid}/request-owner-review',headers=other).status_code==404
    assert c.post(f'/api/sales/{sid}/owner-review',headers=other,json={
         'decision':'CONFIRMED','checked_directly_in_bank_app':True,'checked_reference':'OWNER-003','checked_amount_cents':4500,
         'owner_password':PASSWORD}).status_code==404
    book=login(c,'demo-bookkeeper@fraudfence.test')
    assert c.post(f'/api/sales/{sid}/request-owner-review',headers=book).status_code==403
