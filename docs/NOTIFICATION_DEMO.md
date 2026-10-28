# FraudFence SA — WhatsApp-style notification demonstration

**Status: working local notification previews only.** Meta/WhatsApp API delivery has **not** been implemented. Every notification has `delivery_status: SIMULATED_NOT_SENT`.

## Run / test in a local demo

1. Extract the **update ZIP** into the same project root that contains `requirements.txt` and `fraudfence/main.py`. Stop the Uvicorn process with `Ctrl+C` first.
2. Start the app again: `py -3 -m uvicorn fraudfence.main:app --reload` (or use the `.venv` Python in your demo folder).
3. Sign in as **owner** `demo-owner@fraudfence.test` with your existing demo password.
4. Select **Payment check**, create a unique sale such as `SALE-WA-101` for `R850.00`.
5. Select **Notifications**. You should see **Payment verification required**, with `SIMULATED NOT SENT` and payment **NOT verified**.
6. Under **Suppliers**, propose an account change for the fictional BuildRite supplier using `0001112234`. Reopen **Notifications**: **Security alert: supplier bank change** appears. This action does not approve the change.
7. For a separate demo, return to **Payment check**, inject a fictional `SETTLED` payment event matching `SALE-WA-101`, then click **Reconcile payment** on that sale. The notification is titled **DEMO ONLY: simulated payment match**. It **does not** represent a real bank credit.
8. Click **Mark as read** to demonstrate the authenticated, CSRF-protected inbox endpoint.

A cashier can create a sale but cannot view the owner's notifications. An owner for another business cannot read or acknowledge these notifications.

## Back-end endpoints

- `GET /api/notifications`: authenticated **owner-only** list of a business's local previews, unread count and explicit `real_messages_sent: false` flag.
- `POST /api/notifications/{notification_id}/read`: owner-only and CSRF-protected. No delivery is performed.

## Technical design

- SQLite `notification_outbox`, created by `init_db()` at startup, stores a **business-scoped** outbox with a deduplication key. It does **not** contain real phone numbers.
- `fraudfence/notifications.py` contains an allowlist of event types and **server-authored message text**. No customer input or banking account numbers are interpolated into the message.
- Notifications are inserted in the same transaction as the action that generated them.
- Events are generated for new sales, proposed supplier changes, successful mock payment reconciliation and Ozow **staging** status checks. They are **not** generated for merely receiving a claimed proof of payment.

## Production requirements (not implemented)

- Recipient-specific opt-in and opt-out, approved utility templates and verified WhatsApp Business sender.
- Meta Cloud API credentials stored in an isolated secrets manager; never in Git or a browser.
- Asynchronous, idempotent delivery worker and monitored delivery receipts; no sending before the underlying trusted payment state is independently established.
- Rate limits and safeguards against notification flooding and compromised owner phones.
- Security review, POPIA documentation, retention/deletion controls, encrypted contact storage, and robust authentication before handling real data.

**Important:** These local previews are *not real notifications delivered to phones*. Do not demonstrate them as such.
