"""No Meta calls occur in these tests. All messages remain local previews."""
import pytest
from fastapi.testclient import TestClient
import fraudfence.core as core
import fraudfence.main as main
from scripts.seed_demo import seed

PASSWORD = 'DemoOnly-ChangeMe-2026!'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path/'ff_test.db')
    monkeypatch.setattr(core, 'KEY_DIR', tmp_path/'keys')
    (tmp_path/'keys').mkdir()
    monkeypatch.setattr(core, 'DEMO_MODE', True)
    monkeypatch.setattr(main, 'DEMO_MODE', True)
    core.init_db()
    seed()
    with TestClient(main.app) as c:
        yield c


def log_in(c, email):
    r = c.post('/api/auth/login', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 200
    return {'X-CSRF-Token': r.json()['csrf_token']}


def test_cashier_sale_notifies_owner_but_does_not_send_whatsapp(client):
    hc = log_in(client, 'demo-cashier@fraudfence.test')
    created = client.post('/api/sales', headers=hc, json={'reference':'SALE-MESSAGE-1', 'amount_cents':85000})
    assert created.status_code == 200
    assert created.json()['status'] == 'UNVERIFIED'
    assert client.get('/api/notifications').status_code == 403
    ho = log_in(client, 'demo-owner@fraudfence.test')
    data = client.get('/api/notifications').json()
    assert data['unread'] == 1
    assert data['real_messages_sent'] is False
    item=data['items'][0]
    assert item['kind']=='SALE_REVIEW_REQUIRED'
    assert item['delivery_status']=='SIMULATED_NOT_SENT'
    assert 'NOT verified' in item['preview']
    assert '85000' not in item['preview']
    assert 'SALE-MESSAGE-1' not in item['preview']
    assert client.post('/api/notifications/'+item['id']+'/read').status_code==403
    assert client.post('/api/notifications/'+item['id']+'/read',headers=ho).status_code==200
    assert client.get('/api/notifications').json()['unread']==0


def test_supplier_change_creates_security_alert_without_bank_data(client):
    hb=log_in(client,'demo-bookkeeper@fraudfence.test')
    change=client.post('/api/suppliers/demo-buildrite/changes',headers=hb,
                       json={'bank_account':'0001112234'})
    assert change.status_code==200
    assert change.json()['status']=='PENDING'
    ho=log_in(client,'demo-owner@fraudfence.test')
    items=client.get('/api/notifications').json()['items']
    assert len(items)==1
    assert items[0]['kind']=='SUPPLIER_CHANGE_PENDING'
    assert 'ON HOLD' in items[0]['preview']
    assert '0001112234' not in repr(items)
    assert '2234' not in repr(items)


def test_mock_payment_match_is_explicitly_simulated_and_idempotent(client):
    ho=log_in(client,'demo-owner@fraudfence.test')
    sale=client.post('/api/sales',headers=ho,
                     json={'reference':'SALE-MESSAGE-2','amount_cents':9900}).json()
    assert sale['status']=='UNVERIFIED'
    before=client.get('/api/notifications').json()
    assert len(before['items'])==1
    m=client.post('/api/demo/payments',headers=ho,
                  json={'reference':'SALE-MESSAGE-2','amount_cents':9900,'state':'SETTLED'})
    assert m.status_code==200
    # Merely injecting a fictional payment must not generate a success alert.
    assert len(client.get('/api/notifications').json()['items'])==1
    matched=client.post('/api/sales/'+sale['id']+'/reconcile',headers=ho)
    assert matched.status_code==200
    assert matched.json()['status']=='SIMULATED_PAYMENT_MATCH'
    items=client.get('/api/notifications').json()['items']
    assert len(items)==2
    payment_notice=[n for n in items if n['kind']=='DEMO_PAYMENT_MATCHED'][0]
    assert 'FICTIONAL' in payment_notice['preview']
    assert 'NOT bank confirmation' in payment_notice['preview']
    again=client.post('/api/sales/'+sale['id']+'/reconcile',headers=ho)
    assert again.status_code==200
    assert len(client.get('/api/notifications').json()['items'])==2


def test_alerts_are_tenant_isolated_and_not_readable_via_guessed_id(client):
    ho=log_in(client,'demo-owner@fraudfence.test')
    client.post('/api/sales',headers=ho,json={'reference':'SALE-MESSAGE-3','amount_cents':100})
    alert=client.get('/api/notifications').json()['items'][0]
    hother=log_in(client,'other-owner@fraudfence.test')
    assert client.get('/api/notifications').json()['items']==[]
    assert client.post('/api/notifications/'+alert['id']+'/read',headers=hother).status_code==404
    assert client.get('/api/notifications').json()['unread']==0
    log_in(client, 'demo-owner@fraudfence.test')
    assert len(client.get('/api/notifications').json()['items'])==1


def test_notification_surface_in_web_ui(client):
    r=client.get('/')
    assert r.status_code==200
    assert 'data-tab="notifications"' in r.text
    assert 'SIMULATED · NOT SENT' in r.text
