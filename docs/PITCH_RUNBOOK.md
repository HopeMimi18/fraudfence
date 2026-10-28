# Team FORGE — FraudFence SA: 3-minute pitch mode

**Build tested: 55 automated tests passing.** All CIPC, AVS, supplier-callback, transaction and WhatsApp-style replies in Pitch Mode are fictional. Do **not** submit customer data or use for actual releases of goods or EFT transfers.

## Install on the Windows machine that already runs FraudFence

1. Stop Uvicorn with `Ctrl+C` in its terminal.
2. Download **FraudFence-SA-Pitch-Demo-Update.zip**.
3. From your existing, working **fraudfence-demo** application root (the directory with `requirements.txt`):

```powershell
cd "$HOME\OneDrive\Desktop\fraudfence-demo"
Expand-Archive -LiteralPath "$HOME\Downloads\FraudFence-SA-Pitch-Demo-Update.zip" -DestinationPath . -Force
.\.venv\Scripts\python.exe -m scripts.seed_pitch
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload
```

Expected: **55 passed**. Note: the tests use isolated databases, do not affect pitch fixtures, and confirm mocked provider responses are not real bank funds. If your venv hasn't been created, run `py -3 -m venv .venv` and ` .\.venv\Scripts\python.exe -m pip install -r requirements.txt ` first.

Go to `http://127.0.0.1:8000` and log in as the **owner**, with email `demo-owner@fraudfence.test` and local demo password `DemoOnly-ChangeMe-2026!`. Then click **PRESENTATION MODE** or open `http://127.0.0.1:8000/pitch`.

**Do not run `seed_pitch` while the team is already performing the demonstration**; re-run between rehearsals to reset only the pitch fixtures. Restart app if anything gets stuck.

## Stage run (one speaker, one driver, five mandatory clicks)

| Time | Speaker | Driver action | What appears |
|---|---|---|---|
| 0:00–0:20 | “A scammer edits a supplier invoice or fakes a payment; small firms cannot always check whether the money and banking details are real.” | Show pitch home, start timer | Fictional Mokoena Hardware · BuildRite supplier · INV-2207 |
| 0:20–0:43 | “They demand R18,400 be sent to a changed account. FraudFence compares the submitted digits with the approved supplier fingerprint.” | **1. Send suspicious invoice** | Red **STOP_CHANGED_ACCOUNT**, signed receipt and mock WhatsApp-style STOP |
| 0:43–1:05 | “CIPC identity, bank AVS and an independent supplier callback must agree; here all three are fictional test signals and conflicting evidence keeps the change on hold.” | **2. Verify three sources** | MOCK director change, MOCK AVS NO_MATCH, scripted callback denial, **HOLD** |
| 1:05–1:24 | “Even an insider cannot approve a bank change in WhatsApp; the owner must use the authenticated web app.” | **3. Attempt WhatsApp approval** | **NOT HERE**; local unsent notification, no bank change |
| 1:24–1:40 | “A cashier sees sale status, not banking balances. A screenshot cannot validate a payment.” | **4. Cashier: paid?** | **UNVERIFIED** and **DO NOT release goods** |
| 1:40–2:25 | “We attacked FraudFence itself. The database stores bank fingerprints, not full numbers. Role checks reject bookkeepers; tenant isolation blocks other companies; the audit chain reveals altered records.” | **5. Run pentester evidence** | Four backend-backed controls, pass flags and implementation limits |
| 2:25–2:45 | “Our tests pass on fictional data. Real integrations still require authorisation. Commercial model: proposed R199 per SMME monthly, R19,900 gross at 100 customers—*not profit*.” | Keep evidence displayed | Security and business bands visible |
| 2:45–3:00 | “FraudFence: check before you pay, verify before you release goods. Thank you.” | End | Don't spend demo time changing tabs |

**Optional after the pitch / for questions:** Click **Optional: inject FICTIONAL payment**, then **Cashier: paid?** to demonstrate that the status becomes `SIMULATED_PAYMENT_MATCH`, *not a verified real bank deposit*. Use only for explanatory Q&A if there is time.

## What is actually built, and what is not

**Built and verified locally:** FastAPI authentication, Argon2 password hashes, cookie+CSRF checks, user/business scoping, supplier HMAC account fingerprints plus last four digits, deterministic invoice STOP rules, simulated three-source checks, maker/checker permissions, signed Ed25519 receipts, SHA-256 hash-chain integrity, mock payment reconciliation, local owner notification outbox and the Pitch Mode UI.

**Not built/connected:** live WhatsApp messages, live CIPC, live bank AVS, a real Ozow payment transaction, encryption for every personal field, passkey MFA, a 24-hour cooling-off process, freeze-all-approvals switch, production KMS / independent immutable audit checkpoints, automated POPIA breach notifications. **Never claim these work.** Some contact records remain plaintext in SQLite. HMAC hashing is not equivalent to database encryption. A passing test suite is not a penetration-test certification.

## Evidence and fallback

- Test report: run ` .\.venv\Scripts\python.exe -m pytest -q ` — expected **55 passed**.
- Show `docs/pitch_preview.png` as a static backup of the dashboard layout (it is NOT a screenshot of a live security result).
- The original web app remains at `/`; the owner-only stage page is at `/pitch`.
- Run ` .\.venv\Scripts\python.exe -m scripts.seed_pitch ` to restore the supplier and sale before each practice run. It does not delete older audit history.
- If a scenario fails unexpectedly, show the failing error and discuss it as a test failure rather than claim a pass.

## Extra clarification for technical judges

- WhatsApp can notify, but it does not verify payments or approve supplier changes. Pitch Mode replies are simulated in a browser, not sent to any phone.
- The original business-scoped supplier record stays at last four digits **5678** even when the invoice asks for **7890**.
- The demo registry “director changed 6 days ago” is a fictional flag in a fixed fixture, not a historical live CIPC lookup.
- A full attacker who steals both the database and server keys could defeat some existing controls. Production needs field-level encryption, key isolation, MFA and independently protected audit checkpoints.
- A real production deployment would require provider contracts, HTTPS, data protection and security review. Never deploy this local demo for actual supplier payments.
