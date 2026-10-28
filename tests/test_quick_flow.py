"""Quick screen must not turn simulated evidence into a verified real company/payment."""
import pytest
from fastapi.testclient import TestClient
import fraudfence.main as main
import fraudfence.core as core
from scripts.seed_demo import seed

@pytest.fixture
def context(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'quick.db')
    monkeypatch.setattr(core,'KEY_DIR',tmp_path/'keys')
    (tmp_path/'keys').mkdir()
    monkeypatch.setattr(core,'DEMO_MODE',True)
    monkeypatch.setattr(main,'DEMO_MODE',True)
    for k in ('FF_CIPC_CLIENT_ID','FF_CIPC_CLIENT_SECRET','FF_CIPC_TOKEN_URL','FF_CIPC_COMPANY_ENDPOINT','FF_CIPC_ALLOWED_HOST'):
        monkeypatch.delenv(k,raising=False)
    core.init_db();seed()
    with TestClient(main.app) as c:
        yield c

def login(c,email='demo-owner@fraudfence.test'):
    r=c.post('/api/auth/login',json={'email':email,'password':'DemoOnly-ChangeMe-2026!'})
    assert r.status_code==200,r.text
    return {'X-CSRF-Token':r.json()['csrf_token']}

def test_quick_screen_requires_login_and_is_single_page(context):
    assert context.get('/quick').status_code==401
    login(context)
    resp=context.get('/quick')
    assert resp.status_code==200
    for name in ('Check supplier','Verify payment','AI fraud report'):
        assert name in resp.text

def test_mock_company_is_explicitly_simulated(context):
    h=login(context)
    r=context.post('/api/quick/company',headers=h,json={'registration':'DEMO-REG-001','legal_name':'BuildRite Demo Supplies Pty Ltd'})
    assert r.status_code==200,r.text
    assert r.json()['source']=='SIMULATED_CIPC_FIXTURE'
    assert r.json()['decision']=='MOCK_MATCH'
    assert r.json()['verified_real_company'] is False

def test_unconnected_real_company_does_not_get_approved(context):
    h=login(context)
    r=context.post('/api/quick/company',headers=h,json={'registration':'2024/123456/07','legal_name':'Example (Pty) Ltd'})
    assert r.status_code==200,r.text
    assert r.json()['decision']=='HOLD_CIPC_NOT_CHECKED'
    assert r.json()['verified_real_company'] is False
    assert 'No automated registry check' in r.json()['next_step']

def test_mismatch_or_inactive_cannot_be_accepted_as_verified(context):
    h=login(context)
    for registration,name,expected in [
        ('DEMO-REG-001','Completely Different Ltd','MOCK_NAME_MISMATCH'),
        ('DEMO-REG-004','Inactive Demo Traders Pty Ltd','MOCK_COMPANY_INACTIVE'),
        ('DEMO-REG-003','Cedar Distribution Demo Pty Ltd','MOCK_RECENT_CHANGE'),
    ]:
        d=context.post('/api/quick/company',headers=h,json={'registration':registration,'legal_name':name}).json()
        assert d['decision']==expected
        assert not d['verified_real_company']

def test_cashier_cannot_run_cipc_check(context):
    h=login(context,'demo-cashier@fraudfence.test')
    r=context.post('/api/quick/company',headers=h,json={'registration':'DEMO-REG-001','legal_name':'BuildRite Demo Supplies Pty Ltd'})
    assert r.status_code==403

def test_cross_site_request_not_allowed(context):
    login(context)
    r=context.post('/api/quick/company',json={'registration':'DEMO-REG-001','legal_name':'BuildRite Demo Supplies Pty Ltd'})
    assert r.status_code==403

def test_quick_page_no_live_company_for_fake_registration(context):
    h=login(context)
    r=context.post('/api/quick/company',headers=h,json={'registration':'DEMO-UNKNOWN','legal_name':'No Such Demo'})
    assert r.status_code==200
    assert r.json()['decision']=='MOCK_NOT_FOUND'
    assert r.json()['verified_real_company'] is False
