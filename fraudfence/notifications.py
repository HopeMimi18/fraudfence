"""Hackathon-only WhatsApp-style outbox; intentionally performs NO external delivery.

All messages are generated server-side from an allowlist of trusted internal
workflow events. Users and invoice text cannot select arbitrary message bodies.
A real integration must add explicit opt-in, approved templates, a transactional
outbox worker, delivery tracking and Meta credentials in server-side secrets.
"""
import secrets
from .core import utcnow

TEMPLATES = {
    'SALE_REVIEW_REQUIRED': (
        'Payment verification required',
        'A sale was logged in FraudFence. Payment is NOT verified. '
        'Review the sale inside the web application before releasing goods.'
    ),
    'SUPPLIER_CHANGE_PENDING': (
        'Security alert: supplier bank change',
        'A supplier banking-detail change was requested. The change is ON HOLD '
        'until the required independent checks and authorisation are completed.'
    ),
    'DEMO_PAYMENT_MATCHED': (
        'DEMO ONLY: simulated payment match',
        'A FICTIONAL payment event matched a demo sale. This is NOT bank confirmation '
        'and must not be used as proof that funds were received.'
    ),
    'OZOW_STAGING_RESULT': (
        'Ozow staging verification update',
        'A TEST transaction received a server-side status update in FraudFence. '
        'Ozow staging does NOT represent real funds arriving in a bank account.'
    ),
}


def enqueue_demo_notification(c, business_id, kind, event_key):
    """Transactional, idempotent and tenant scoped. Never sends to WhatsApp."""
    if kind not in TEMPLATES:
        raise ValueError('Unsupported notification type')
    title, preview = TEMPLATES[kind]
    c.execute("""INSERT OR IGNORE INTO notification_outbox
      (id,business_id,recipient_role,event_key,kind,title,preview,created_at)
      VALUES(?,?,'owner',?,?,?,?,?)""",
      (secrets.token_urlsafe(14),business_id,event_key,kind,title,preview,utcnow()))
