# FraudFence Lite — three core actions

## One screen, three decisions

Visit `/quick` **after logging in** to the web application. This page simplifies the existing backend; it does not replace or weaken security checks.

### 1. Check supplier — protect money going out

**Quick input:** registration number + independently established legal company name. Two inputs are enough to **request a registry lookup**, not to establish trust or legal/tax compliance.

- In the hackathon, enter fictional `DEMO-REG-001` and `BuildRite Demo Supplies Pty Ltd`. You will see `SIMULATED_CIPC_FIXTURE` and `MOCK_MATCH`. Those are not government results.
- A real-looking registration number without an authorised CIPC API subscription returns `HOLD_CIPC_NOT_CHECKED`. It must **never** be treated as verified automatically.
- An authorised human can consult CIPC **BizPortal → Services → BizProfile** at https://www.bizportal.gov.za/ and review the legal name, registration status and history. The quick screen does **not** ingest the manual result or mark a supplier verified; adding a documented, accountable manual review workflow requires another development step.
- Registration itself does **not** prove tax/VAT compliance, account ownership, legitimate intentions or invoice authenticity. Registered-only onboarding is a chosen product scope, not a government certification.
- Next, use an existing supplier from the drop-down, type a fictional invoice number, amount and account, and click **Check invoice account**. FraudFence compares a keyed fingerprint with the supplier's saved record and returns STOP/HOLD/MATCHES_DEMO_RECORD. In future, a **real Ozow bank AVS** account ownership check plus independent callback should be required to establish payee trust. Ozow AVS is **not** the same service as Ozow payment checkout.

### 2. Verify payment — protect goods going out

**Quick input:** sale reference + amount. When Ozow staging credentials are configured, click **Create Ozow staging checkout**, complete the test checkout in Ozow, then click **Check Ozow transaction**.

Evidence required for `OZOW_STAGING_PROVIDER_CONFIRMED`:
- An authenticated Ozow One API transaction; not a customer screenshot, browser redirect, SMS or claims.
- Exact registered merchant site, unique transaction ID, sale reference, amount and ZAR currency.
- A successful payment status; no conflicting, ambiguous or duplicate transaction evidence.

If Ozow returns pending/failed, FraudFence does **not** show confirmed payment. When Ozow confirms a payment it processed, the result is available on provider transaction status, without waiting for later settlement from Ozow to the merchant's bank account. Provider completion can still be pending, so no guaranteed number of seconds. **Ordinary EFTs made outside Ozow cannot be verified with Ozow.** Those require independently authorised receiving-bank transaction evidence.

**No Ozow credentials:** `Create Ozow staging checkout` remains disabled. An owner can inject an **explicitly fictional bank event** and run a simulated payment match for the judges, which must never authorise real goods release. The app does not include or promise live Ozow access.

Ozow official documentation:
- Prerequisites: https://hub.ozow.com/getting-started/prerequisites-and-onboarding/
- One API quick start: https://hub.ozow.com/getting-started/quick-start/
- Transaction statuses: https://hub.ozow.com/integration-methods/statuses/
- Ozow bank AVS (separate and merchant-enabled): https://hub.ozow.com/api-reference/one-api/post-bankaccount-verify/

### 3. AI report — make the evidence understandable

After an invoice or payment decision, click the appropriate report button. The generator reads the backend verification status and creates an investigation report. It cannot modify records, release goods or override STOP/HOLD.

- **Connected model:** `REAL_AI_MODEL` when Ollama or a configured API actually responds.
- **No model:** `RULE_BASED_REPORT_NO_AI` is an evidence-based fallback, not a misleading claim of live AI.
- Only allowlisted, limited status facts are supplied to the model; screenshots, full bank details and raw supplier contact information are not sent.

### Quick presentation path (under 2 minutes)

1. Show a registered-company **mock** match. Clarify CIPC is simulated. Type an invoice account that differs from the saved record: `STOP_CHANGED_ACCOUNT`.
2. Create a sale for R850. Show `UNVERIFIED`. Without Ozow staging credentials, inject a fictional event and show `SIMULATED_PAYMENT_MATCH`, **not real payment**.
3. Generate an invoice fraud report. If a real model is connected, show `REAL_AI_MODEL`; otherwise say the reporting fallback is rules-only.

For penetration-testing questions, open `/pitch` and demonstrate denied approvals, tenant isolation and audit integrity. Do **not** say that every database field is encrypted or that independent penetration testing has been completed.

## Windows update

Stop the existing server with `Ctrl+C` and extract `FraudFence-SA-Lite-Update.zip` over the **project root** (the folder with `requirements.txt`). Run from that root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.seed_demo
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload
```

Seeded demonstration data may overwrite local demo fixtures; do not use this for real customer information. Existing demo owner credentials are documented in the standard README. Visit `http://127.0.0.1:8000/quick` after signing in.

## Security and production blockers

This is demo-only. Real bank data requires an authorised Ozow merchant contract and credentials, valid callback/webhook protection, reconciliation, retention controls, encryption/key management and security review. Existing CIPC adapter parsing may need adaptation to the exact schema/method issued by the user's subscription. Do not deploy to the public internet with synthetic demo credentials.
