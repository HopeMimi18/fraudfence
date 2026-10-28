"""Three-attack live-pitch evidence: exercises actual HTTP handlers with fictional records."""
import json
import pytest
from fastapi.testclient import TestClient
import fraudfence.core as core
import fraudfence.main as main
from scripts.seed_pitch import seed_pitch

PASSWORD='DemoOnly-ChangeMe-2026!'

@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'isolated.sqlite')
    monkeypatch.setattr(core,'KEY_DIR',tmp_path/'secrets')
    (tmp_path/'secrets').mkdir()
    monkeypatch.setattr(core,'DEMO_MODE',True)
    monkeypatch.setattr(main,'DEMO_MODE',True)
    seed_pitch()
    with TestClient(main.app) as c:
        yield c


def login(c, email='demo-owner@fraudfence.test'):
    result=c.post('/api/auth/login',json={'email':email,'password':PASSWORD})
    assert result.status_code==200,result.text
    return {'X-CSRF-Token':result.json()['csrf_token']}


def test_invoice_stop_and_real_signature(ctx):
    h=login(ctx)
    invoice=ctx.post('/api/pitch/invoice',headers=h)
    assert invoice.status_code==200,invoice.text
    data=invoice.json()
    assert data['decision']=='STOP_CHANGED_ACCOUNT'
    assert '••••5678' in data['message'] and '••••7890' in data['message']
    assert data['channel'].endswith('NOT SENT')
    assert ctx.get('/api/public/verify/'+data['receipt_id']).json()['signature_and_log_valid'] is True
    assert '1234567890' not in json.dumps(data)


def test_three_sources_hold_and_never_change_saved_account(ctx):
    h=login(ctx)
    d=ctx.post('/api/pitch/three-sources',headers=h)
    assert d.status_code==200,d.text
    response=d.json()
    assert response['decision']=='HOLD'
    assert response['registry']['result']=='MOCK_RECENT_CHANGE'
    assert response['bank']['result']=='NO_MATCH'
    assert response['callback']['source'].startswith('PRELOADED FICTIONAL')
    state=ctx.get('/api/pitch/state').json()
    assert state['saved_last4']=='5678'
    assert state['change_status']=='HOLD'
    with core.connection() as db:
        row=db.execute("SELECT * FROM suppliers WHERE id='pitch-buildrite'").fetchone()
        assert row['account_hmac']==core.fingerprint('62012345678')
        assert row['account_hmac']!=core.fingerprint('1234567890')


def test_whatsapp_cannot_approve_and_bookkeeper_really_gets_403(ctx):
    h=login(ctx)
    refusal=ctx.post('/api/pitch/chat-attack',headers=h)
    assert refusal.status_code==200
    assert refusal.json()['decision']=='NOT_HERE'
    assert refusal.json()['change_performed'] is False
    # Real HTTP request with bookkeeper's session, not a mocked route guard.
    bk=login(ctx,'demo-bookkeeper@fraudfence.test')
    approval=ctx.post('/api/changes/pitch-CH-031/approve',headers=bk,json={
         'last4_confirmed':'7890','called_independently':True,'owner_password':PASSWORD})
    assert approval.status_code==403
    assert ctx.get('/api/pitch/state').status_code==403
    assert ctx.get('/pitch').status_code==403


def test_payment_is_unverified_until_fictional_bank_event(ctx):
    h=login(ctx)
    initial=ctx.post('/api/pitch/payment-check',headers=h).json()
    assert initial['status']=='UNVERIFIED'
    assert 'Do NOT release' in initial['message']
    received=ctx.post('/api/pitch/mock-payment',headers=h)
    assert received.status_code==200, received.text
    assert received.json()['status']=='SIMULATED_PAYMENT_MATCH'
    updated=ctx.post('/api/pitch/payment-check',headers=h).json()
    assert updated['status']=='SIMULATED_PAYMENT_MATCH'
    assert 'DO NOT release actual goods' in updated['message']
    repeated=ctx.post('/api/pitch/mock-payment',headers=h)
    assert repeated.json()['status']=='SIMULATED_PAYMENT_MATCH'
    with core.connection() as db:
        matches=db.execute("SELECT count(*) FROM payments WHERE reference='FF-1058'").fetchone()[0]
        assert matches==1


def test_platform_security_and_tenant_isolation(ctx):
    h=login(ctx)
    d=ctx.get('/api/pitch/security')
    assert d.status_code==200,d.text
    x=d.json()
    assert x['account_storage']['supplier_account_number_column_present'] is False
    assert x['role_probe']['bookkeeper_approval_denied'] is True
    assert x['tenant_probe']['second_business_fixture_exists'] is True
    assert x['tenant_probe']['cross_business_supplier_visible'] is False
    assert x['integrity_probe']['audit_chain_intact'] is True
    assert x['integrity_probe']['altered_record_detected_in_memory'] is True
    # A different tenant cannot see the pitch supplier even from normal API.
    other=login(ctx,'other-owner@fraudfence.test')
    assert 'pitch-buildrite' not in json.dumps(ctx.get('/api/suppliers').json())
    assert ctx.get('/api/pitch/security').status_code==403


def test_production_mode_disables_pitch(ctx, monkeypatch):
    login(ctx)
    monkeypatch.setattr(main,'DEMO_MODE',False)
    assert ctx.get('/api/pitch/security').status_code==404
    assert ctx.get('/pitch').status_code==404


def test_five_minute_problem_stage_is_read_only_and_untrusted(ctx):
    h=login(ctx)
    before=ctx.get('/api/pitch/state').json()
    problem=ctx.get('/api/pitch/problem')
    assert problem.status_code==200,problem.text
    data=problem.json()
    assert data['type']=='FICTIONAL_ATTACK_EXAMPLE'
    assert data['invoice']['reference']=='INV-2207'
    assert data['invoice']['amount_cents']==1840000
    assert data['invoice']['previously_trusted_last4']=='5678'
    assert data['invoice']['submitted_last4']=='7890'
    assert data['payment_claim']['sale_reference']=='FF-1058'
    assert data['payment_claim']['system_status']=='UNVERIFIED'
    assert '1234567890' not in problem.text
    assert ctx.get('/api/pitch/state').json()==before
    # Story endpoint cannot be used by the cashier or the other business.
    login(ctx,'demo-cashier@fraudfence.test')
    assert ctx.get('/api/pitch/problem').status_code==403
    login(ctx,'other-owner@fraudfence.test')
    assert ctx.get('/api/pitch/problem').status_code==403


def test_five_minute_web_page_has_three_named_scenarios(ctx):
    login(ctx)
    p=ctx.get('/pitch')
    assert p.status_code==200
    body=p.text
    assert '05:00' in body
    assert 'The problem: two fraud attempts' in body
    assert 'FraudFence checks the evidence' in body
    assert 'The penetration tester' in body
    assert body.count('<article class="scenario')==3
    assert '/static/pitch.js' in body
