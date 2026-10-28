"""Seed/reset ONLY fictional pitch fixtures for a deterministic 3-minute stage demonstration.

Run from repository root: python -m scripts.seed_pitch
No real company identity, bank or WhatsApp message is used.
Re-running safely resets pitch-specific rows; it does not delete audit history.
"""
from __future__ import annotations
from fraudfence.core import init_db, connection, fingerprint, utcnow, audit
from scripts.seed_demo import seed

SUPPLIER_ID = 'pitch-buildrite'
CHANGE_ID = 'pitch-CH-031'
SALE_ID = 'pitch-FF-1058'
BUSINESS_ID = 'demo-shop'
TRUSTED_ACCOUNT = '62012345678'
FRAUD_ACCOUNT = '1234567890'


def seed_pitch():
    seed()  # keeps demo accounts, passwords and original test records
    init_db()
    now = utcnow()
    with connection(write=True) as c:
        c.execute("UPDATE businesses SET name='Mokoena Hardware (Fictional)' WHERE id='demo-shop'")
        c.execute("UPDATE businesses SET name='Dube Wholesalers (Fictional)' WHERE id='other-shop'")
        # Historical trusted supplier. A fictional director change occurred AFTER its
        # original verification; this recheck is meant to revoke old trust.
        c.execute('''INSERT INTO suppliers (id,business_id,name,expected_legal_name,registration,
          identity_source,trusted_phone,phone_source,account_hmac,account_last4,
          verification,avs_result,registry_result,registry_checked_at,callback_by,callback_at,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET account_hmac=excluded.account_hmac,
          account_last4=excluded.account_last4, verification='DEMO_VERIFIED',
          avs_result='MOCK_MATCH', registry_result='MOCK_MATCH',
          registry_checked_at=excluded.registry_checked_at,updated_at=excluded.updated_at''',
          (SUPPLIER_ID,BUSINESS_ID,'BuildRite Supplies (Fictional)',
           'BuildRite Supplies (Pty) Ltd','DEMO-PITCH-BUILDRITE',
           'independent_record','27820000001','prior_record',fingerprint(TRUSTED_ACCOUNT),'5678',
           'DEMO_VERIFIED','MOCK_MATCH','MOCK_MATCH',now,'HISTORICAL_TEST',now,now,now))
        bookkeeper=c.execute("SELECT id FROM users WHERE email='demo-bookkeeper@fraudfence.test'").fetchone()[0]
        cashier=c.execute("SELECT id FROM users WHERE email='demo-cashier@fraudfence.test'").fetchone()[0]
        c.execute('''INSERT INTO changes (id,supplier_id,business_id,account_hmac,account_last4,
          avs_result,status,initiated_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET status='PENDING', account_hmac=excluded.account_hmac,
          account_last4=excluded.account_last4,avs_result='NO_MATCH',approved_by=NULL,approved_at=NULL''',
          (CHANGE_ID,SUPPLIER_ID,BUSINESS_ID,fingerprint(FRAUD_ACCOUNT),'7890',
           'NO_MATCH','PENDING',bookkeeper,now))
        # Separate fictional tenant used for the cross-business isolation probe.
        c.execute('''INSERT INTO suppliers (id,business_id,name,expected_legal_name,registration,
          identity_source,trusted_phone,phone_source,account_hmac,account_last4,
          verification,avs_result,registry_result,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING''',
          ('pitch-dube-supplier','other-shop','Only Dube Knows (Fictional)',
           'Only Dube Knows Pty Ltd','DEMO-OTHER-999','independent_record',
           '27820000099','prior_record',fingerprint('63000001234'),'1234',
           'UNVERIFIED','NOT_RUN','NOT_RUN',now,now))
        # Keep the sale ready for the cashier's 'paid?' question.
        c.execute("DELETE FROM payments WHERE used_by_sale=?", (SALE_ID,))
        c.execute("DELETE FROM payments WHERE business_id=? AND reference='FF-1058'",(BUSINESS_ID,))
        c.execute('''INSERT INTO sales (id,business_id,amount_cents,reference,created_by,created_at,status)
          VALUES (?,?,?,?,?,?,'UNVERIFIED') ON CONFLICT(id) DO UPDATE SET
          amount_cents=85000,status='UNVERIFIED',payment_id=NULL''',
          (SALE_ID,BUSINESS_ID,85000,'FF-1058',cashier,now))
        c.execute("DELETE FROM notification_outbox WHERE business_id=? AND event_key LIKE 'pitch:%'",(BUSINESS_ID,))
        audit(c,BUSINESS_ID,'SEED_DATA','PITCH_FIXTURES_PREPARED',
              {'synthetic':True,'supplier_id':SUPPLIER_ID,'change_id':CHANGE_ID,'sale_id':SALE_ID})
    print('PITCH MODE READY — 100% synthetic, never live CIPC/AVS/Ozow/WhatsApp')
    print('Open /, log in as demo-owner@fraudfence.test, then open /pitch')
    print('Demo password: DemoOnly-ChangeMe-2026!')


if __name__ == '__main__':
    seed_pitch()
