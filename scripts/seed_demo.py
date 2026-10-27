"""Populate invented businesses and users for an offline, synthetic-data demo.
Usage from project root: python -m scripts.seed_demo
"""
import secrets
from fraudfence.core import (init_db, connection, HASHER, fingerprint, utcnow, audit)

def seed():
    init_db()
    users = [
        ('demo-owner@fraudfence.test','Demo Owner','owner','demo-shop'),
        ('demo-bookkeeper@fraudfence.test','Demo Bookkeeper','bookkeeper','demo-shop'),
        ('demo-cashier@fraudfence.test','Demo Cashier','cashier','demo-shop'),
        ('other-owner@fraudfence.test','Other Demo Owner','owner','other-shop'),
    ]
    with connection(write=True) as c:
        for bid,name in [('demo-shop','Mokoena Hardware (Fictional)'),('other-shop','Neighbour Store (Fictional)')]:
            c.execute('INSERT OR IGNORE INTO businesses(id,name) VALUES (?,?)',(bid,name))
        for email,name,role,bid in users:
            exists=c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone()
            if not exists:
                c.execute('INSERT INTO users(id,business_id,email,name,role,password_hash) VALUES(?,?,?,?,?,?)',
                          (secrets.token_urlsafe(12),bid,email,name,role,HASHER.hash('DemoOnly-ChangeMe-2026!')))
        found=c.execute('SELECT 1 FROM suppliers WHERE business_id=?',('demo-shop',)).fetchone()
        if not found:
            now=utcnow()
            c.execute('''INSERT INTO suppliers(id,business_id,name,expected_legal_name,registration,
                identity_source,trusted_phone,phone_source,account_hmac,account_last4,
                verification,avs_result,callback_by,callback_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('demo-buildrite','demo-shop','BuildRite Demo Supplies','BuildRite Demo Supplies Pty Ltd',
                 'DEMO-REG-001','independent_record','011 000 0001','prior_record',
                 fingerprint('0001112223'),'2223','DEMO_VERIFIED','MOCK_MATCH',
                 'SEED_DATA',now,now,now))
            audit(c,'demo-shop','SEED_DATA','SYNTHETIC_SUPPLIER_SEEDED',{'supplier_id':'demo-buildrite','account_last4':'2223','demo':True})
    print('Demo data seeded (re-running is safe).')
    print('Owner: demo-owner@fraudfence.test')
    print('Bookkeeper: demo-bookkeeper@fraudfence.test')
    print('Cashier: demo-cashier@fraudfence.test')
    print('Second independent business: other-owner@fraudfence.test')
    print('Password for each (demo ONLY): DemoOnly-ChangeMe-2026!')
    print('Mock account 0001112223 (BuildRite), mock legitimate changed account 0001112234')
    print('WARNING: this database and every bank record are fictional; NEVER use production data.')

if __name__=='__main__':
    seed()
