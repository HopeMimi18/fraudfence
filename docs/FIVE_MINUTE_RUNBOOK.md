# Team FORGE — three scenarios, under five minutes

**Use:** This is a 4:40 demo with 20 seconds of margin. One speaker and one screen driver. All identities, accounts, invoices and payment events are fictional. Registry and AVS results are mock adapters, callback answers are preloaded, and chat replies are local previews, **not** delivered via WhatsApp. No production money moves.

**Important:** The official HackSecure judges pack previously described a *3-minute pitch including demo*. If that rule still applies, **do not use the full five-minute version**. Confirm your current format; use the compact alternate below if the event remains three minutes.

## Before presenting (do this at least twice)

1. From the application root, run `python -m scripts.seed_pitch` before the first rehearsal. This restores the fictional Mokoena Hardware data and FF-1058 sale to `UNVERIFIED`; it does not erase all past audit history.
2. Run `python -m pytest -q`; the release build is expected to show **57 passed** if the package is unchanged and dependencies are installed.
3. Start Uvicorn, sign in as `demo-owner@fraudfence.test` using the local **demo password documented in README**, and open `http://127.0.0.1:8000/pitch`.
4. Put the page full-screen and set browser zoom to 80–90% if needed. Start the five-minute on-screen timer.
5. Keep a screenshot or the static preview as a fallback. The preview is **not** evidence that security endpoints executed.

## Script and operator cues — about 4:40

| Time | Act | Speaker — say this | Driver |
| --- | --- | --- | --- |
| 0:00–0:12 | Opening | “We're Team FORGE. Invoice redirection and fake proof-of-payment scams can cost a small business money or goods.” | Show dashboard. Start timer. |
| 0:12–1:00 | **1. THE PROBLEM** | “Mokoena Hardware gets an urgent BuildRite invoice for R18,400. The email demands payment to account ending 7890, but its supplier file says 5678. At the same time, a customer claims they paid R850 for cement. Neither claim is proof.” | Click **1 · Show scam invoice & fake POP**. Point to the two untrusted claims. |
| 1:00–1:55 | **2. THE SOLUTION** | “FraudFence compares the submitted account to a keyed fingerprint of the trusted account and issues STOP. It then evaluates three independent sources: simulated CIPC, simulated AVS, and a preloaded callback response. Here all the signals warn us, so the bank change stays on HOLD. The current supplier account is not overwritten.” | Click **2 · STOP supplier payment**. Point to STOP → HOLD, three source cards and signed receipt. |
| 1:55–2:55 | **2. THE SOLUTION** | “The fake proof of payment is still just a screenshot. The cashier checks FF-1058 and receives UNVERIFIED: do not release goods. Our real integration design would require authenticated provider evidence before confirmation. WhatsApp is only a notification channel.” | Click **3 · Check fake POP**. Do **not** inject a fictional payment during the timed demo. |
| 2:55–3:33 | **3. ATTACK FRAUDFENCE** | “Now we turn attacker. Someone sends a WhatsApp-style message ordering a bank change. FraudFence answers ‘Not here’. That channel cannot approve financial changes. The server also blocks bookkeeper approval using an owner-only role guard.” | Click **4 · Try forbidden approval**. |
| 3:33–4:30 | **3. ATTACK FRAUDFENCE** | “We test our own data defences: full supplier account numbers aren't stored in the table, only a keyed HMAC fingerprint and four digits. A bookkeeper's privilege escalation fails, queries cannot cross business boundaries, and tampering with an audit-record copy changes its cryptographic hash. Automated HTTP tests exercise these guards.” | Click **5 · Run platform security probes**. Point to all four checks. |
| 4:30–4:40 | Closing | “Our prototype's tests pass. Full field encryption, MFA, live CIPC, AVS and Ozow remain next steps. At a proposed R199 per SMME per month, 100 paying businesses would produce R19,900 in **gross** monthly revenue, not profit. FraudFence: check before you pay.” | Keep probe evidence displayed. |

### If judges ask whether this is penetration-test certified

“No. We ran automated adversarial tests against our access controls and demo fixtures. We have not completed an independent penetration test, and plaintext contact fields are still a production security gap. We would not use this local demo with real supplier or customer data.”

### If judges ask whether the database is encrypted

“Not fully. Supplier bank account numbers are minimised to HMAC fingerprints and last four digits; passwords are Argon2-hashed. Some other fields are still plaintext in the local SQLite prototype. Field-level encryption, separately managed keys and a production security assessment are next milestones.”

### If judges ask why the company check is simulated

“CIPC API subscription access and Ozow test-provider credentials are not yet available to our team. The architecture includes adapters, and our automated tests verify our response handling, but we do not present mock evidence as a live government or banking lookup.”

### If the judge's slot is still 3:00 rather than 5:00

The previously supplied HackSecure judge pack allows **three minutes total, including demo**. Shorten to: **0:00–0:25 problem** (click 1); **0:25–1:35 solution** (click 2 and 3); **1:35–2:40 pentester** (click 4 and 5); **2:40–3:00 commercial and close**. Keep the three acts, but skip the long explanation and optional payment injection. The on-screen countdown is five minutes; use a separate three-minute phone timer for the official 3-minute version.

## Security proof and limitations

- **Backend-backed**: invoice mismatch STOP; HOLD retaining stored account; signed receipts; role guard; business-scoped SQL; audit-chain verification.
- **Synthetic**: registry six-day director-change flag, mock AVS mismatched beneficiary, scripted callback denial, unverified sale fixtures and WhatsApp-style messages.
- **Real HTTP tests**: tests assert that a bookkeeper attempting a supplier approval receives `403` and a different tenant cannot read the pitch supplier. The presentation screen shows live guard/probe results, not an in-browser interactive offensive penetration-testing tool.
- **Tamper demo**: changes a copy of an audit event in memory to show detection, without editing the actual audit database.
- **Not implemented**: full field encryption, KMS, passkeys/MFA, freeze-switch, independent pentest, 24-hour cooling-off, production incident automation and external provider access. Never claim these controls work.
