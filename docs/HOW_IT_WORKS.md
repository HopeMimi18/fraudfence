# FraudFence SA — How the Web Application Actually Works

**Team FORGE | Beginner-first explanation | 27 October 2026**

> **Prototype, synthetic data only.** The system currently has no real banking, AVS or payment-provider connection. It must not be used to approve genuine supplier payments or release real goods.

## The idea in one sentence

FraudFence checks whether a payment-related decision matches records that a small business has already verified, stops suspicious changes, and records exactly how the decision was made.

It has two separate jobs:

1. **Money out:** prevent a bookkeeper from paying a supplier invoice with changed or unverified bank details.
2. **Goods out:** prevent a cashier from treating a screenshot as proof that a customer has paid.

It also records fraud incidents and signs verification receipts. **FraudFence does not make payments or transfer funds.**

## Five components, in plain English

| Component | What it does | Analogy |
|---|---|---|
| Browser interface (HTML/CSS/JS) | Forms, results, status panels | The shop counter |
| FastAPI backend (Python) | Checks who is logged in, authorises requests, runs rules | Security guard + manager |
| SQLite database (demo) | Stores suppliers, user roles, sales, incidents and logs | Locked records cabinet |
| Deterministic Trust Engine | Compares input with verified records and returns STOP/HOLD/MATCH | Written approval policy |
| Signed audit trail | Records checks and detects later tampering | Numbered, tamper-evident receipt book |

```
Person opens website
       |
       v
Logs in -> backend checks identity, role and active session
       |
       v
User performs permitted action (check invoice / check sale)
       |
       v
Backend validates input and fetches only THEIR business's records
       |
       v
Trust Engine applies rules (NOT AI guessing)
       |
       v
Backend records result in audit log; may generate a signed receipt
       |
       v
Browser shows a result and clear next action
```

## Walkthrough A: detect a fraudulent supplier invoice

The fictional hardware shop has saved **BuildRite Demo Supplies**, account `0001112223`. The record is marked demo-verified after simulated bank checks and an owner-attested independent supplier call.

1. A bookkeeper receives an invoice claiming the bank account has changed to `0009998877`.
2. They sign in to the web app and open **Invoice check**.
3. They select BuildRite and enter the bank account and invoice amount/reference.
4. The backend checks they belong to the business and have permission to check invoices.
5. The backend computes an HMAC fingerprint of the submitted bank account and compares it with the trusted supplier record. It never lets instructions within the invoice override the result.
6. Because the numbers differ, the result is `STOP_CHANGED_ACCOUNT`.
7. The interface explains: **Do not pay; contact the supplier using a previously verified phone number**.
8. The server records the check, signs a receipt and displays the receipt ID.

**Security benefit:** a believable invoice or email cannot automatically override saved supplier payment instructions.

**Important limitation:** a `MATCHES_VERIFIED_DEMO_RECORD` outcome means the account matches the application's fictional record, **not** that a bank has confirmed account ownership or that an invoice is genuine.

## Walkthrough B: prevent a new supplier from becoming automatically trusted

1. Owner or bookkeeper saves a supplier. Its status is `UNVERIFIED`.
2. A saved record alone is never sufficient to generate a fully verified verdict.
3. The mock AVS adapter checks the account against synthetic supplier identity fixtures.
4. The owner records an **independent** supplier call-back and confirms the last four digits.
5. The system requires a fresh owner-password check before recording that sensitive attestation.
6. Only the simulated workflow can mark it `DEMO_VERIFIED`.

**Why:** if a scammer got their account into the supplier database during initial onboarding, later comparisons would otherwise appear to match.

**Production changes needed:** genuinely independent supplier identity verification, an authorised real AVS provider, and phishing-resistant MFA for owner approvals.

## Walkthrough C: stop unauthorised supplier changes

1. Bookkeeper proposes new supplier banking details; proposal remains `PENDING`.
2. Until approval, invoice checks against the new account return `STOP_CHANGED_ACCOUNT`.
3. Only an authenticated **owner** can approve. The web app asks for their password again as a basic high-risk step-up.
4. The owner must attest to calling the supplier through a trusted independent channel and confirming the final digits.
5. If the mock AVS check failed, **even the owner cannot override it**.
6. An accepted change updates the record and generates a signed receipt.

**Security benefit:** ordinary staff cannot quietly substitute an attacker-controlled account.

**Limitation:** re-entering a password is NOT true MFA. Production requires passkeys or another strong second factor and stronger maker-checker workflows.

## Walkthrough D: fake proof of payment

1. A cashier records a fictional R850 sale under the unique reference `SALE-001`.
2. A customer shows a screenshot. FraudFence **does not trust the screenshot**.
3. With no matching transaction in the synthetic payment feed, FraudFence responds `UNVERIFIED`.
4. In the **demo only**, the owner injects a fictional successful transaction with the exact amount and reference.
5. FraudFence checks the account's tenant, amount, reference, settlement flag and whether this transaction was used for another sale.
6. It returns `SIMULATED_PAYMENT_MATCH`, not a real bank-confirmed credit.

**Production changes needed:** a genuine, authenticated payment-provider webhook plus a server-to-server status verification call; standard EFT requires an authorised bank transaction feed. A provider success notice must not automatically be described as money settled in the merchant's bank.

## What happens to sensitive information?

- Passwords: stored as salted Argon2 hashes, not readable plaintext.
- User sessions: random server-generated tokens; only token hashes are stored; the browser receives an HttpOnly cookie.
- Supplier account numbers: this demo stores an HMAC fingerprint and the final four digits, not the full account number. Full numbers are temporarily processed for matching.
- Supplier names, contact phone numbers, user emails and incident descriptions: currently stored **in plaintext in the local demo database**. They require encryption/retention policies and appropriate access controls before real use.
- Receipts: signed with a server-side Ed25519 key; public verification exposes minimal fields. The server key must be protected by a real secrets/KMS solution for production.

**No software can guarantee attackers will never gain access.** Our aim is to reduce the chance and impact of compromise, and to detect and respond when controls fail.

## Important terminology

- **Authentication:** Are you really the logged-in user?
- **Authorisation:** Even if logged in, may you perform *this specific action*?
- **Tenant isolation:** A user from Shop A cannot read Shop B's supplier records.
- **HMAC:** A keyed cryptographic fingerprint useful for matching account numbers without storing the originals.
- **AVS:** Bank-account verification service. **Mock only** in this project.
- **Webhook:** A verified notification sent from a provider's server to our backend. **Not integrated yet.**
- **Fail closed:** If verification cannot establish the evidence, return HOLD or UNVERIFIED—not a positive approval.
- **Audit trail:** Evidence of the action, actor, result and time.

## Explain it to a judge in 20 seconds

> “FraudFence is a secure web app for small businesses. The owner verifies their suppliers once. When a bookkeeper checks an invoice, our backend compares its bank details to that verified record. If anything changed, the app blocks the normal approval path and requires independent confirmation. We apply role permissions, log the decision and issue a signed receipt. Our payment-check flow uses simulated transaction data today; real bank connectivity is the next phase.”

## Try it yourself in five minutes

1. Follow the main README quick-start commands.
2. Log in as `demo-bookkeeper@fraudfence.test` (password in README).
3. Check supplier **BuildRite** with fraudulent account `0009998877` -> **STOP**.
4. Try the correct fictional account `0001112223` -> match to synthetic verified record. Notice the explicit warning: *not a bank check*.
5. Log in as the cashier; try to open suppliers -> backend denies permission.
6. Log in as the owner; open the receipt page and verify its integrity.

When you can explain what is compared, who may approve and what evidence is *missing*, you understand FraudFence.
