"""Provider-edge tests with local HTTP responders; NEVER submit real funds."""
import os
import uuid
from pathlib import Path
import pytest
import httpx
from fastapi.testclient import TestClient
import fraudfence.core as core
import fraudfence.main as main
import fraudfence.external as external
from scripts.seed_demo import seed

PASSWORD='DemoOnly-ChangeMe-2026!'
PAY_ID='497f6eca-6276-4993-bfeb-53cbbbba6f08'
TX_ID='d47c3bc3-87c9-4a6d-91ca-0eae75034c0a'

@pytest.fixture()
def ctx(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'ff.db')
    monkeypatch.setattr(core,'KEY_DIR',tmp_path/'keys')
    (tmp_path/'keys').mkdir()
    monkeypatch.setattr(core,'DEMO_MODE',True)
    monkeypatch.setattr(main,'DEMO_MODE',True)
    core.init_db()
    seed()
    monkeypatch.setenv('FF_OZOW_CLIENT_ID','synthetic-id')
    monkeypatch.setenv('FF_OZOW_CLIENT_SECRET','synthetic-secret')
    monkeypatch.setenv('FF_OZOW_SITE_CODE','TESTSITE')
    monkeypatch.setenv('FF_OZOW_RETURN_URL','https://localhost.example/success')
    with TestClient(main.app) as c:
        auth=c.post('/api/auth/login',json={'email':'demo-owner@fraudfence.test','password':PASSWORD})
        assert auth.status_code==200
        yield c,{'X-CSRF-Token':auth.json()['csrf_token']},monkeypatch


def ozow_responder(state='Successful',reference='SALE-EXTERNAL',amount=850,site='TESTSITE',count=1):
    def respond(request):
        if request.url.path.endswith('/token'):
            assert request.method=='POST'
            assert 'synthetic-secret' in request.content.decode()
            return httpx.Response(200,json={'access_token':'pretend-access-token'})
        assert request.headers.get('Authorization')=='Bearer pretend-access-token'
        if request.method=='POST' and request.url.path.endswith('/payments'):
            assert request.url.host=='stagingone.ozow.com'
            assert request.headers.get('Idempotency-Key')
            return httpx.Response(200,json={'id':PAY_ID,'redirectUrl':'https://stagingpay.ozow.com/checkout','status':'Created'})
        if request.method=='GET' and request.url.path.endswith('/transactions'):
            rows=[{'id':TX_ID if i==0 else str(uuid.uuid4()), 'merchantReference':reference,
                   'siteCode':site,'status':state,'amount':{'currency':'ZAR','value':amount}} for i in range(count)]
            return httpx.Response(200,json={'results':rows,'meta':{'totalPages':1}})
        return httpx.Response(404)
    return httpx.MockTransport(respond)


def sale_started(ctx):
    c,h,monkeypatch=ctx
    sale=c.post('/api/sales',headers=h,json={'reference':'SALE-EXTERNAL','amount_cents':85000})
    assert sale.status_code==200
    sid=sale.json()['id']
    start=c.post(f'/api/sales/{sid}/ozow-staging/start',headers=h)
    assert start.status_code==200,start.text
    assert start.json()['status']=='OZOW_STAGING_PENDING'
    return sid


def test_live_config_missing_does_not_guess_cipc(ctx):
    c,h,monkeypatch=ctx
    for k in ('FF_CIPC_CLIENT_ID','FF_CIPC_CLIENT_SECRET','FF_CIPC_TOKEN_URL','FF_CIPC_COMPANY_ENDPOINT','FF_CIPC_ALLOWED_HOST'):
        monkeypatch.delenv(k,raising=False)
    r=c.post('/api/suppliers/demo-buildrite/cipc-api-check',headers=h)
    assert r.status_code==503
    assert c.get('/health').json()['live_cipc_connected'] is False


def test_authorised_cipc_lookup_does_not_upgrade_mock_to_live(ctx):
    c,h,monkeypatch=ctx
    monkeypatch.setenv('FF_CIPC_CLIENT_ID','synthetic')
    monkeypatch.setenv('FF_CIPC_CLIENT_SECRET','synthetic')
    monkeypatch.setenv('FF_CIPC_TOKEN_URL','https://sandbox.cipc.co.za/token')
    monkeypatch.setenv('FF_CIPC_COMPANY_ENDPOINT','https://sandbox.cipc.co.za/lookup')
    monkeypatch.setenv('FF_CIPC_ALLOWED_HOST','sandbox.cipc.co.za')
    def res(req):
        if req.url.path=='/token':return httpx.Response(200,json={'access_token':'pretend'})
        assert req.headers['Authorization']=='Bearer pretend'
        assert req.url.params['registrationNumber']=='DEMO-REG-001'
        return httpx.Response(200,json={'registrationNumber':'DEMO-REG-001',
             'enterpriseName':'BuildRite Demo Supplies Pty Ltd','enterpriseStatus':'ACTIVE'})
    monkeypatch.setattr(external,'HTTP_TRANSPORT',httpx.MockTransport(res))
    r=c.post('/api/suppliers/demo-buildrite/cipc-api-check',headers=h)
    assert r.status_code==200,r.text
    assert r.json()['verdict']=='CIPC_COMPANY_DETAILS_MATCH_ONLY'
    assert r.json()['supplier_live_verified'] is False
    # The provider result is scoped to the logged-in business
    other=c.post('/api/auth/login',json={'email':'other-owner@fraudfence.test','password':PASSWORD})
    assert other.status_code==200
    no=c.post('/api/suppliers/demo-buildrite/cipc-api-check',headers={'X-CSRF-Token':other.json()['csrf_token']})
    assert no.status_code==404


def test_cipc_mismatch_fails_closed(ctx):
    c,h,monkeypatch=ctx
    for key,value in dict(FF_CIPC_CLIENT_ID='x',FF_CIPC_CLIENT_SECRET='y',
         FF_CIPC_TOKEN_URL='https://sandbox.cipc.co.za/token',
         FF_CIPC_COMPANY_ENDPOINT='https://sandbox.cipc.co.za/lookup',
         FF_CIPC_ALLOWED_HOST='sandbox.cipc.co.za').items():monkeypatch.setenv(key,value)
    def responder(req):
        if req.url.path=='/token':return httpx.Response(200,json={'access_token':'t'})
        return httpx.Response(200,json={'registrationNumber':'WRONG','enterpriseName':'BuildRite Demo Supplies Pty Ltd','enterpriseStatus':'ACTIVE'})
    monkeypatch.setattr(external,'HTTP_TRANSPORT',httpx.MockTransport(responder))
    r=c.post('/api/suppliers/demo-buildrite/cipc-api-check',headers=h)
    assert r.status_code==200 and r.json()['verdict']=='HOLD_REGISTRATION_MISMATCH'


def test_ozow_success_requires_authenticated_provider_transaction_mock(ctx):
    c,h,monkeypatch=ctx
    monkeypatch.setattr(external,'HTTP_TRANSPORT',ozow_responder())
    sid=sale_started(ctx)
    assert c.get('/api/sales').json()[0]['status']=='OZOW_STAGING_PENDING'
    r=c.post(f'/api/sales/{sid}/ozow-staging/check',headers=h)
    assert r.status_code==200,r.text
    assert r.json()['status']=='OZOW_STAGING_PROVIDER_CONFIRMED'
    assert r.json()['transaction_id']==TX_ID
    rid=r.json()['receipt_id']
    assert c.get('/api/public/verify/'+rid).json()['signature_and_log_valid'] is True
    # No misleading synthetic-feed reconciliation when Ozow is involved
    m=c.post(f'/api/sales/{sid}/reconcile',headers=h)
    assert m.status_code==200
    assert m.json()['status']=='OZOW_STAGING_PROVIDER_CONFIRMED'


@pytest.mark.parametrize('kwargs,expected',[({'state':'Pending'},'OZOW_STAGING_PENDING'),
    ({'state':'Error'},'OZOW_STAGING_NOT_PAID'),
    ({'reference':'WRONG'},'HOLD_PROVIDER_MISMATCH'),
    ({'amount':600},'HOLD_PROVIDER_MISMATCH'),
    ({'site':'OTHERSITE'},'HOLD_PROVIDER_MISMATCH'),
    ({'count':2},'HOLD_MULTIPLE_SUCCESSFUL_TRANSACTIONS'),
    ({'state':'Refunded'},'HOLD_REFUNDED')])
def test_ozow_fail_closed(ctx,kwargs,expected):
    c,h,monkeypatch=ctx
    monkeypatch.setattr(external,'HTTP_TRANSPORT',ozow_responder(**kwargs))
    sid=sale_started(ctx)
    r=c.post(f'/api/sales/{sid}/ozow-staging/check',headers=h)
    assert r.status_code==200 and r.json()['status']==expected
    assert r.json()['status']!='OZOW_STAGING_PROVIDER_CONFIRMED'


def test_ozow_without_credentials_returns_unavailable(ctx):
    c,h,monkeypatch=ctx
    monkeypatch.delenv('FF_OZOW_CLIENT_SECRET')
    sid=c.post('/api/sales',headers=h,json={'reference':'SALE-NO-CREDS','amount_cents':10000}).json()['id']
    r=c.post(f'/api/sales/{sid}/ozow-staging/start',headers=h)
    assert r.status_code==503
    assert c.get('/api/sales').json()[0]['status']=='UNVERIFIED'


def test_ozow_payment_not_usable_by_another_tenant(ctx):
    c,h,monkeypatch=ctx
    monkeypatch.setattr(external,'HTTP_TRANSPORT',ozow_responder())
    sid=sale_started(ctx)
    other=c.post('/api/auth/login',json={'email':'other-owner@fraudfence.test','password':PASSWORD})
    other_h={'X-CSRF-Token':other.json()['csrf_token']}
    assert c.post(f'/api/sales/{sid}/ozow-staging/check',headers=other_h).status_code==404
