# FraudFence SA — Phase 2: Three-source supplier trust (mock demonstration)

**Status:** implemented in this branch as a local **fictional-data demo**. The existing payment reconciliation and incident workflows remain unchanged. No real CIPC, banking, Paystack or WhatsApp integrations are claimed.

## Why this matters

A scammer may use a genuine company name and registration number with a different bank account. A counterfeit bank letter or convincing phone call also cannot authenticate a supplier alone. The new workflow requires three complementary sources to agree before a *demo* supplier receives a verified-workflow status.

## Data flow

```text
Owner / bookkeeper saves synthetic supplier  -> UNVERIFIED
    |            |             |
    v            v             v
Mock registry    Mock AVS      Owner callback, with independent trusted number
 legal name      account       authenticated owner re-authenticates
 active status   + company     confirms bank account last four digits
 director-change|             |
    +------------+-------------+
                 |
         All evidence agrees?
         NO -> HOLD (no verified status)
         YES -> DEMO_VERIFIED (not live identity/bank verification)
```

`POST /api/suppliers/{id}/registry-check` uses `fraudfence/registry.py`. Its records are fixed fictional fixtures. It is role-restricted, CSRF-protected, business-scoped, writes an audit event, and issues an Ed25519-signed receipt. It never contacts CIPC or returns `BANK_SETTLED` / real identity verification.

### Registry outcome semantics

| Result | Meaning | Policy |
|---|---|---|
| `MOCK_MATCH` | Fictional company is active and expected legal name matches | Continue to other evidence |
| `MOCK_NAME_MISMATCH` | Expected identity differs from fictional registry | HOLD |
| `MOCK_COMPANY_INACTIVE` | Company not active | HOLD |
| `MOCK_RECENT_CHANGE` | Recent director change in fixture | HOLD for independent review |
| `MOCK_NOT_FOUND` | Registration missing in fixture | HOLD |
| `IDENTITY_NOT_ESTABLISHED` | Legal identity only sourced from invoice | HOLD |
| `UNAVAILABLE` | Registry adapter disabled (non-demo) | HOLD |

### Other security changes

- Initial onboarding requires matching simulated registry evidence, simulated AVS and independent owner callback.
- A failed registry recheck downgrades previously demo-verified supplier to `UNVERIFIED`.
- Old databases are migrated with new registry columns. Formerly verified records that lack this evidence are downgraded until rechecked.
- Owner cannot approve a banking-detail change they proposed; maker and checker must differ.
- Same-session role and CSRF protection, tenant separation and signed receipts remain in place.
- Real-world limitations remain: spoofed/compromised supplier contacts, company hijacking, compromised accounts, stolen server keys, no production MFA, no real payment feed, and plaintext supplier contact records in current SQLite data. **Never use this prototype for real business payment decisions.**

### Run the demonstration

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.seed_demo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload
```

Then open http://127.0.0.1:8000 and select **Suppliers**. For scripted output run `python -m scripts.demo_scenarios` using the active virtual environment.

### Next work, in priority order

1. Pilot a **real, authorised registry provider** and real AVS partner; model provider timeouts and freshness; avoid presenting matching fictional data as actual company verification.
2. Design a strong **sole-owner exception workflow**. Maker-checker is currently intentionally strict.
3. Encrypt supplier contact details using managed keys, then add PostgreSQL row-level security, passkeys and secure recovery.
4. Implement a sandbox payment adapter and signed webhooks without granting a simulated event the same status as real settled funds.
5. Add notification delivery only after authoritative events; WhatsApp must remain a notification channel, never the approval source.
