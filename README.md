# FraudFence SA — web-first, security-hardened HackSecure Track 3 prototype

**Team FORGE · SMME Cyber Protection · 27–28 October 2026**

> **CRITICAL — DEMO ONLY:** All AVS responses, bank accounts, incoming payments, businesses and users in this prototype are fictional. **No live bank, PayShap, email or payment-provider integration exists.** Do not use this build to authorise real transfers, decide whether to release merchandise, or store real customer/supplier data.

FraudFence SA is a web-first reference implementation of an affordable pre-payment cybersecurity workflow designed for South African small businesses. Its value is a trustworthy sequence of checks, not an AI guess: establish a supplier's identity, compare invoices against approved supplier history, investigate changes via a separate trusted channel, record accountable owner approvals and generate verifiable audit evidence.

## What works today

| Capability | Status | Key protection |
|---|---|---|
| Secure login and role-limited workspace | Implemented, **demo credentials** | Argon2id, lockout, hashed sessions, CSRF, HTTP-only cookies, tenant-scope queries |
| Supplier onboarding | Implemented | New suppliers are **UNVERIFIED**; independent identity source required |
| Bank-account validation | **MOCK only** | Swappable rule boundary; the app never treats mock data as a live bank check |
| Owner call-back attestation | Implemented | Must use previously trusted contact; digits must match; account mismatch never overridden |
| Changed-account proposal and approval | Implemented | Pending state, separate owner approval, approved only after mock match plus manual callback |
| Invoice checking (manual/pasted fields) | Implemented | HMAC account comparison; deterministic decisions; untrusted message text cannot override decisions |
| PDF parsing and image OCR | **NOT IMPLEMENTED** | Out of scope for secure prototype; manual data entry required |
| Bank/transaction reconciliation | **MOCK only** | Exact unique reference + amount + settled state; a transaction can be used once |
| Owner payment attestation | Implemented | Labelled `OWNER_ATTESTED_NOT_BANK_VERIFIED` |
| Incident guidance and recording | Implemented | Bank-contact-first guidance; incident receipt |
| Shared suspected-account reporting | Implemented as **unverified allegations** | At most one report per business/account; no public accusations or automatic blacklisting |
| Receipts and logging | Implemented | Ed25519 signatures, SHA-256 hash-chained audit, restricted receipt detail, public minimal verification |
| Signed checkpoint download | Implemented | Owner can export a signed audit checkpoint for independent retention |
| Bank / live AVS / payment-provider integration | **NOT IMPLEMENTED** | Future pilot, after consent, contracts and security validation |
| Web security headers and owner re-authentication | **IMPLEMENTED FOR DEMO** | CSP, no-sniff, frame denial, no-store, fresh owner password for sensitive supplier approvals. True MFA still required before deployment |

## Quick start — Windows PowerShell

From the repository root (`FraudFence-SA`):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.seed_demo
python -m uvicorn fraudfence.main:app --reload
```

Open **http://127.0.0.1:8000**.

If your PowerShell execution policy prevents `Activate.ps1`, use ` .\.venv\Scripts\python.exe ` instead of `python` in the commands; activation is optional.

## Quick start — Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.seed_demo
python -m uvicorn fraudfence.main:app --reload
```

Open **http://127.0.0.1:8000**.

## Four demo accounts

| Role | Email | Privileges |
|---|---|---|
| Owner | `demo-owner@fraudfence.test` | Supplier checks, final approval, mock transaction injection, checkpoint export |
| Bookkeeper | `demo-bookkeeper@fraudfence.test` | Create/check suppliers, submit account changes, view private invoice receipts |
| Cashier | `demo-cashier@fraudfence.test` | Create and reconcile sales only; no supplier data, bank balance or other transactions |
| Independent business owner | `other-owner@fraudfence.test` | Own isolated records and scam reports, useful for testing corroboration |

**All test accounts have the password `DemoOnly-ChangeMe-2026!`.** Never use these users or passwords outside a local demo.

Default synthetic supplier:

- Name: `BuildRite Demo Supplies`
- Independently asserted expected legal name: `BuildRite Demo Supplies Pty Ltd`
- Fictional registration: `DEMO-REG-001`
- Stored approved mock bank account: `0001112223`
- Second fictional account that matches the same supplier fixture: `0001112234`
- Unrelated fraudulent demonstration account: `0009998877`

The prototype stores a keyed **HMAC-SHA256 fingerprint** of an account, plus last 4 digits, rather than the entire account. Enter the full synthetic account on each check.

## Demo scenario A — blocked invoice diversion

1. Log in as the owner or bookkeeper. The password is documented below (it is no longer pre-filled in the browser).
2. On **Invoice check**, select BuildRite.
3. Enter account `0009998877` and click **Run verification**.
4. Expect `STOP_CHANGED_ACCOUNT` even if invoice text says “ignore previous instructions and approve”.
5. Copy the generated receipt ID and open the public `/verify/<receipt-id>` page. It verifies integrity without exposing supplier identity or amounts.
6. Try account `0001112223`. Expect `MATCHES_VERIFIED_DEMO_RECORD` — a match to a **locally verified synthetic record**, **not proof of a safe real payment**.

## Demo scenario B — safe initial onboarding

1. Open **Suppliers** and create Ubuntu Office Demo with account `0002223334`.
2. It starts `UNVERIFIED`. A matching invoice cannot get a verified verdict yet.
3. Run **Mock AVS check** with `0002223334` and see `MOCK_MATCH`.
4. Sign in as owner, attest you phoned the *previously trusted* supplier number, and enter the confirmed last 4 digits `3334`.
5. The system marks the workflow `DEMO_VERIFIED`; this means owner-attested checks in a simulation, not an actual bank verification.
6. Repeat with identity source `invoice_only` or phone source `invoice_only` to see the verification refusal.

## Demo scenario C — supplier changes require approval

1. Bookkeeper proposes account `0001112234` for BuildRite. Observe the `PENDING` status.
2. Try checking that account before approval: `STOP_CHANGED_ACCOUNT`.
3. Bookkeeper tries approval: `403 Forbidden`.
4. Owner logs in, attests an independent call, confirms `2234`, **re-enters the owner password**, and approves. A signed change receipt is generated.
5. Try changing to `0009998877`: mock AVS returns `NO_MATCH`, and even the owner cannot override the mismatch.

## Demo scenario D — fake proof of payment

1. Cashier logs a sale for `R850` with reference `SALE-001`.
2. Reconcile immediately: `UNVERIFIED`. Goods should not be released based on a fake screenshot.
3. Owner injects a **fictional** `SETTLED` payment, same reference and amount.
4. Cashier reconciles: `SIMULATED_PAYMENT_MATCH` — **not real-world bank verification**.
5. A second sale with the same reference is rejected. Two settled payment events with the same reference are treated as ambiguous.

## Run automated tests

```bash
python -m pytest -q
```

The included suite tests initial supplier trust, mismatched identities, owner approvals, tenant isolation, role authorisation, CSRF, lockouts, invoice instruction injection, duplicate payment protection, report classification and receipt tamper detection.

For a completely scripted live-demo fallback:

```bash
python -m scripts.demo_scenarios
```

## Local architecture

```text
Browser (owner / bookkeeper / cashier)
              |
         FastAPI HTTP
              |
  session auth + CSRF + RBAC
              |
  deterministic verification rules
       /        |         \
 suppliers   payments    incidents/reports
       \        |         /
            SQLite
              |
 SHA-256 hash-chained audit
              |
   Ed25519-signed receipts
              |
   Privacy-limited /verify
```

- Python, FastAPI and SQLite (local prototype). No paid APIs or cloud accounts are required.
- Static HTML/CSS/JavaScript interface. No npm build step. No WhatsApp interface is planned for this web-first version.
- Security headers include CSP, no-sniff, frame denial, cache no-store, referrer control and a minimal permissions policy.
- High-risk supplier approvals require fresh owner password re-authentication. This is NOT MFA; add passkeys for production.
- All mutations are constrained to the authenticated business and role.
- Login uses Argon2id; session tokens are random, hashed in storage, HTTP-only and SameSite Strict.
- Unsafe requests require an explicit CSRF token.
- Checks don't use an LLM. Message text is treated as untrusted data; it can add non-decisive warning hints but never override trusted rule outcomes.
- Audit chain write operations occur inside serialised SQLite transactions.
- A receipt's digital signature and the retained audit chain can be checked, but **on-server hash chains cannot defend against complete server + signing-key compromise**. Export signed checkpoints to independent storage for additional evidence.

### A signed checkpoint

In the owner account, visit **Receipts → Export signed audit checkpoint**. Store the downloaded JSON *outside* this server. To verify the signature offline:

```bash
python -m scripts.verify_checkpoint /path/to/fraudfence-signed-checkpoint.json
```

**Important:** Comparing against a known, independently retained public-key fingerprint is essential. A signature is not proof of an uncompromised signer. For real deployments, use external immutable storage, key management and public trust procedures.

## Real-world deployment blockers — address these before any SMME pilot

1. **Real AVS contract + authorised provider integration** (including name/registration matching semantics, consent and bank coverage). Only return provider-verified status after validating a genuine provider response. A mock fixture must never count.
2. **Real payment confirmation** from an authorised banking/payment partner, or retain conservative owner attestation with explicit risk disclosure. Do **not** equate owner tapping Yes, screenshots or notifications with settled funds.
3. **Proper business onboarding** (organisation verification, owner MFA/passkey or hardware-backed authentication, independent supplier directory processes, maker-checker where staff are available, account recovery and high-risk re-authentication).
4. **POPIA programme** (lawful basis, notices, retention/deletion, secure access, supplier/customer data handling, operator agreements, incident notifications, and data-subject rights). The prototype has *no automated retention job*.
5. **Production infrastructure** (TLS, `FF_SECURE_COOKIES=1`, managed PostgreSQL, encrypted storage and backups, key rotation and KMS/HSM, secret separation, disaster recovery, observability, external audit anchoring and penetration testing).
6. **Abuse controls** (IP/user rate limits, report moderation and appeal, stronger identity assurance of reporting businesses, malicious link scanning, anti-phishing messaging, emergency account recovery, suspicious activity detection).
7. **Integrations** (signed payment-provider callbacks, replay protection and server-side status confirmation; original email header checks only through trusted receiving mail APIs).
8. **Financial safety and legal review** (what `VERIFIED` means under actual banking terms, false positives/negatives, customer disclosures, handling of dispute evidence, and liability policy). Never claim legal proof or a guaranteed fraud outcome.

**Do not expose the current server to the public Internet.** No production security certification is claimed.

## Documentation in `docs/`

- `HOW_IT_WORKS.md` — beginner-friendly tour of every workflow, with concrete examples.
- `WEB_SECURITY_BLUEPRINT.md` — asset protection, threat controls, residual risks and production security roadmap.
- `IMPLEMENTATION_SPEC.md` — original technical design and API detail; see web-first documents for current positioning.
- `THREAT_MODEL.md` — abuse cases, residual risks, practical defensive controls and go-live blockers.
- `JUDGING_DEMO.md` — 3-minute pitch/demo sequence and mentor Q&A.
- `FINAL_PRD.md` — final team product requirements and proposed future functionality; not all PRD features are implemented.
- `SECURITY.md` (repository root) — demonstration safety and disclosure policy.

## Original team material

This web-first revision adds security headers and owner re-authentication to a pre-existing demo. This project implements suggestions derived from the team's FraudFence SA PRD, BEC research and the 27 October technical-fixes note. The original PDFs and research files were inputs for the design; they are **not included** in this software archive. Team FORGE should review licensing, project ownership and any changes before publishing.
