"""Database, secure session and demo-signature primitives.

NOT an approved bank integration. Server-verified records mean verified *workflow*
steps, never that a real bank confirmed payee or funds in demo mode.
"""
from __future__ import annotations
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("FF_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("FF_DATABASE_PATH", DATA_DIR / "fraudfence.db"))
KEY_DIR = Path(os.environ.get("FF_KEY_DIR", DATA_DIR))
KEY_DIR.mkdir(parents=True, exist_ok=True)
DEMO_MODE = os.environ.get("FF_DEMO_MODE", "1") == "1"
SECURE_COOKIES = os.environ.get("FF_SECURE_COOKIES", "0") == "1"
ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("FF_ALLOWED_ORIGINS", "").split(",") if x.strip()]
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical(v):
    return json.dumps(v, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def secret_file(name, create=None):
    path = KEY_DIR / name
    if not path.exists():
        data = create() if create else secrets.token_bytes(32)
        with path.open("xb") as f:
            os.chmod(path, 0o600)
            f.write(data)
    return path.read_bytes()


def signing_key():
    encoded = secret_file(
        "receipt_ed25519.key",
        lambda: Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    return Ed25519PrivateKey.from_private_bytes(encoded)


def public_key_b64():
    return base64.b64encode(signing_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )).decode()


def sign(payload):
    return base64.b64encode(signing_key().sign(canonical(payload).encode())).decode()


def verify_signature(payload, signature):
    try:
        signing_key().public_key().verify(base64.b64decode(signature, validate=True), canonical(payload).encode())
        return True
    except Exception:
        return False


def normal_account(raw):
    # Only permit ASCII digits, spaces and hyphens. Silently stripping arbitrary
    # letters/Unicode numerals can create a false match against trusted data.
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9\s-]+", raw):
        raise ValueError("Account must contain ASCII digits, spaces or hyphens only")
    value = re.sub(r"[\s-]", "", raw)
    if not 8 <= len(value) <= 16:
        raise ValueError("Account number must contain 8–16 digits")
    return value


def fingerprint(raw):
    value = normal_account(raw)
    return hmac.new(secret_file("account_hmac.key"), value.encode(), hashlib.sha256).hexdigest()


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(stored, password):
    try:
        return HASHER.verify(stored, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


@contextmanager
def connection(write=False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
 id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
 email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','bookkeeper','cashier')),
 password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 csrf_hash TEXT NOT NULL, expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (
 email TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, locked_until TEXT);
CREATE TABLE IF NOT EXISTS suppliers (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
 name TEXT NOT NULL, expected_legal_name TEXT NOT NULL, registration TEXT NOT NULL,
 identity_source TEXT NOT NULL CHECK(identity_source IN ('invoice_only','independent_record')),
 trusted_phone TEXT NOT NULL, phone_source TEXT NOT NULL CHECK(phone_source IN ('invoice_only','existing_contact','prior_record','official_verified')),
 account_hmac TEXT NOT NULL, account_last4 TEXT NOT NULL,
 verification TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(verification IN ('UNVERIFIED','MOCK_BANK_CHECKED','DEMO_VERIFIED')),
 avs_result TEXT NOT NULL DEFAULT 'NOT_RUN', callback_by TEXT, callback_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS changes (
 id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL REFERENCES suppliers(id), business_id TEXT NOT NULL,
 account_hmac TEXT NOT NULL, account_last4 TEXT NOT NULL,
 avs_result TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', initiated_by TEXT NOT NULL,
 approved_by TEXT, created_at TEXT NOT NULL, approved_at TEXT);
CREATE TABLE IF NOT EXISTS sales (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
 reference TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'UNVERIFIED', payment_id TEXT UNIQUE,
 UNIQUE(business_id, reference));
CREATE TABLE IF NOT EXISTS payments (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL, amount_cents INTEGER NOT NULL,
 reference TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('SETTLED','PENDING')),
 source TEXT NOT NULL DEFAULT 'MOCK_FEED', received_at TEXT NOT NULL,
 used_by_sale TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL, account_hmac TEXT NOT NULL,
 account_last4 TEXT NOT NULL, category TEXT NOT NULL, details TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'UNVERIFIED_REPORT', created_at TEXT NOT NULL,
 UNIQUE(business_id, account_hmac));
CREATE TABLE IF NOT EXISTS incidents (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL, created_by TEXT NOT NULL,
 category TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, business_id TEXT NOT NULL,
 actor TEXT NOT NULL, action TEXT NOT NULL, payload_json TEXT NOT NULL,
 recorded_at TEXT NOT NULL, prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS receipts (
 id TEXT PRIMARY KEY, business_id TEXT NOT NULL, audit_id INTEGER NOT NULL REFERENCES audit_events(id),
 record_json TEXT NOT NULL, signature TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_suppliers_business ON suppliers(business_id);
CREATE INDEX IF NOT EXISTS idx_payments_match ON payments(business_id,reference,amount_cents,state);
CREATE INDEX IF NOT EXISTS idx_reports_account ON reports(account_hmac);
"""


def init_db():
    with connection(write=True) as c:
        c.executescript(SCHEMA)


def audit(c, business_id, actor, action, payload):
    now = utcnow()
    prev = c.execute("SELECT entry_hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev[0] if prev else "0" * 64
    event = dict(business_id=business_id, actor=actor, action=action,
                 payload=payload, recorded_at=now, prev_hash=prev_hash)
    entry_hash = hashlib.sha256(canonical(event).encode()).hexdigest()
    cur = c.execute("INSERT INTO audit_events(business_id,actor,action,payload_json,recorded_at,prev_hash,entry_hash) VALUES(?,?,?,?,?,?,?)",
        (business_id, actor, action, canonical(payload), now, prev_hash, entry_hash))
    return cur.lastrowid, entry_hash


def audit_chain_valid(c):
    prev = "0" * 64
    for e in c.execute("SELECT * FROM audit_events ORDER BY id ASC"):
        expected = hashlib.sha256(canonical(dict(business_id=e['business_id'], actor=e['actor'],
            action=e['action'], payload=json.loads(e['payload_json']), recorded_at=e['recorded_at'], prev_hash=prev)).encode()).hexdigest()
        if e['prev_hash'] != prev or not hmac.compare_digest(e['entry_hash'], expected):
            return False
        prev = e['entry_hash']
    return True


def create_receipt(c, business, actor, action, payload):
    audit_id, entry_hash = audit(c, business, actor, action, payload)
    record = dict(check_id=secrets.token_urlsafe(20), audit_id=audit_id,
                  audit_hash=entry_hash, outcome=payload.get('decision','RECORDED'), recorded_at=utcnow(), demo=DEMO_MODE)
    sig = sign(record)
    c.execute("INSERT INTO receipts(id,business_id,audit_id,record_json,signature,created_at) VALUES(?,?,?,?,?,?)",
              (record['check_id'],business,audit_id,canonical(record),sig,record['recorded_at']))
    return record['check_id']
