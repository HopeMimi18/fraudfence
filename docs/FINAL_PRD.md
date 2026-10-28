# FraudFence SA — Final Product Requirements Document

**Team FORGE · HackSecure 2026 · Track 3: SMME Cyber Protection**  
**Version:** 2.0 — consolidated product specification  
**Date:** 27 October 2026  
**Status:** Approved direction for team review; prototype implemented in part, integrations and production controls pending  
**Primary delivery channel:** Secure web application  
**Secondary channel:** Opt-in WhatsApp **notifications only** — never a payment-authorisation or authentication channel

> **Safety and claim boundary.** The supplied prototype works on synthetic data. Its CIPC and bank-account verification integrations are not live; its payment feed is simulated; there is no live WhatsApp notification delivery. A matching demo record is *not* proof of supplier legitimacy, a bank-confirmed deposit or permission to release goods. FraudFence cannot stop an EFT outside its platform. Real-data deployment is prohibited until the security and integration gates in this PRD are met.

---

## 1. Executive summary

FraudFence SA is an affordable, security-first web application that helps South African small, medium and micro enterprises (SMMEs) defend against **invoice redirection / business email compromise (BEC)**, **fraudulent supplier bank-detail changes**, **fake proof-of-payment claims**, and **confusion during fraud incidents**.

It delivers **decision support, not banking**. The application compares payment instructions with a business's independently established supplier records; checks available independent identity and bank-account evidence; enforces role-based reviews; reconciles payments only against trusted authorised sources; and records accountable, tamper-evident verification evidence. The web application is the source of truth. WhatsApp is used only to alert opted-in staff to events that must be reviewed securely in the web application.

**Core product rule:** no single artefact — invoice, screenshot, bank letter, company registration record, email header, phone call or payment notification — is sufficient on its own to establish trust. Missing, inconsistent or unauthenticated evidence must **fail closed** to a neutral `HOLD` / `NOT_VERIFIED` state rather than produce false assurance.

**Primary first-release value proposition:** “Check the supplier and the payment instruction before you pay; keep an auditable record of how the decision was made.”

### 1.1 The product in one scenario

A bookkeeper receives an R12,500 invoice claiming a long-standing supplier has switched bank accounts. The bookkeeper signs in to FraudFence, chooses the supplier and enters or uploads the instruction. FraudFence compares a keyed fingerprint of the account against the approved supplier record. A mismatch returns **STOP — ACCOUNT CHANGED**, creates a pending review, and alerts the owner in the web app and, if opted in, via WhatsApp. The owner reviews independent company and banking evidence and performs a callback using the *previously trusted contact*. A signed verification receipt records the evidence and decision. The system does **not** itself transfer or freeze bank funds.

### 1.2 User and stakeholder personas

| Persona | Main need | Key constraint |
|---|---|---|
| Owner / administrator (e.g., township hardware store) | Know which approvals are pending; prevent payment losses | May be away from the shop; no security staff |
| Bookkeeper / accounts clerk | Verify suppliers and invoices before EFT | Busy; exposed to impersonation and time pressure |
| Cashier / sales assistant | Check whether a specific sale is paid | Must not access the owner's banking app or other transactions |
| Supplier / third-party contact | Have legitimate changes verified without confusion | May be informal or not VAT-registered |
| FraudFence operations / security team | Operate safely without routine access to customer plaintext | Breach and privacy obligations |

**Initial target segment:** SA SMMEs regularly paying supplier invoices by EFT and/or accepting electronic customer payments; emphasise owner-managed retailers, wholesalers, trades and local shops. Validate assumptions through real interviews before claiming product-market fit.

---

## 2. Problem, security risk and evidence

### 2.1 Primary problem: payment instruction substitution

An attacker compromises a supplier's email, forges an invoice, clones a sender identity or deceives staff into paying an attacker-controlled bank account. The invoice may look legitimate while the payment destination is not. Even an existing supplier can become a risk if their email, company records or phone contact is compromised.

**Security risks:** business email compromise; social engineering; unauthorised alteration of payment instructions; account takeover; insider abuse; unreliable identity verification; financial loss and supplier disputes.

### 2.2 Secondary problem: fake proof-of-payment

A customer presents a screenshot or claims to have made an EFT. The cashier cannot independently see the owner's bank records and may release goods too early. A reference, amount, SMS or screenshot alone does not prove payment settlement.

**Security risks:** forged payment evidence; replay/reuse of a legitimate transaction; incorrect transaction matching; authorisation bypass.

### 2.3 Platform risk: FraudFence itself becomes a target

The database could reveal which businesses pay which suppliers, invoice amounts, historical payment timings and trusted contacts. An attacker might use stolen data to mount more convincing BEC attacks; compromise an owner account; trick support into resetting access; exploit broken multi-tenant authorisation; forge payment webhooks; or rewrite audit history.

**Security principle:** protect the defender. Keep as little sensitive information as possible; make key, identity, database, approval, integration and evidence trust boundaries explicit.

### 2.4 Source evidence and claim discipline

The team's BEC research cites South African payment-diversion cases, a SABRIC digital banking fraud total and relevant industry surveys. Those are supporting context rather than proof that every affected SMME would adopt the product. Claims about legal liability are case-specific, and industry-wide loss figures are **not** an SMME-only loss estimate. Do not say FraudFence “guarantees fraud prevention” or “provides legally conclusive evidence.” Validate published figures and use precise source attribution in external pitches.

---

## 3. Existing alternatives and differentiated value

| Alternative | Existing capability | Remaining gap FraudFence addresses |
|---|---|---|
| Manual supplier callback | Independent voice confirmation at low cost | Inconsistent practice, weak documentation, can be skipped under pressure or redirected to a compromised number |
| Bank account-verification services (AVS) | Checks selected account-holder or business details according to provider capabilities | Does not alone prove the sender or instruction is genuine; often separate from invoice approval workflow |
| CIPC / company registry lookup | Checks registered company information | Does not prove a sender's authority or bank-account ownership; informal businesses may lack a company registration |
| SPF/DKIM/DMARC and email security | Mitigates some email identity threats | Cannot eliminate hacked real mailboxes, lookalike domains or payment-instruction alteration |
| Bank app alerts / payment gateways | Reports certain bank/provider transaction states | Cashiers may lack permission; unrelated EFTs are not visible to a payment gateway; status is not always bank settlement |
| Enterprise vendor-verification platforms | Multi-step vendor vetting and workflow controls | May have SMME affordability and onboarding friction; integration-heavy workflows |
| Generic AI scam scanners | Identify suspicious wording or visual patterns | No authoritative knowledge of *this business's* supplier history, approvals or payment records |

**Product differentiation:** low-friction SA SMME workflow combining **supplier trust history + change detection + independent verification + least-privilege approvals + transaction-specific payment evidence + signed audit receipts**, with web access and optional WhatsApp alerts. This is a proposed value proposition, not a proven claim of market uniqueness.

---

## 4. Product objectives, measurable outcomes and non-goals

### 4.1 Objectives

1. Prevent an unverified or changed supplier bank account from being treated as an automatically approved payment instruction.
2. Give a cashier an accurate **sale-specific payment status** without bank credentials or broader transaction visibility.
3. Ensure only authorised staff perform sensitive actions, with extra owner verification and separation of duties.
4. Protect business-to-supplier relationships and personal information against unauthorised disclosure, alteration and excessive retention.
5. Make failed checks understandable and actionable to non-specialist SMME users.
6. Produce trustworthy records of *what was checked*, by whom, when, using which source and rule version.
7. Deliver timely but minimal out-of-band notifications without using WhatsApp as a source of financial truth.

### 4.2 Proposed pilot success measures (to validate)

| Metric | Proposed validation target / rule |
|---|---|
| Safety | **Zero** test cases where failed/missing evidence produces a positive verified state |
| Isolation | **Zero** successful cross-business reads/writes in adversarial tests |
| Payment matching | **Zero** confirmed statuses for screenshot-only or reused transaction evidence |
| User workflow | Median time for manual invoice check under 60 seconds once supplier is enrolled; benchmark with users |
| Supplier onboarding | Record completion time and abandonment; improve based on 5–10 interviews |
| Pilot engagement | Track weekly active businesses and repeated verification usage; targets set after discovery |
| Alerts | Count delivered, delayed, duplicated and failed notifications; do not require receipt for correctness |
| Willingness to pay | Test a candidate low-cost subscription, including the original R49–R99/month hypothesis |

These are proposed measures, not achieved field results.

### 4.3 Non-goals

- No issuing, moving, intercepting, reversing or holding customer funds.
- No guarantee that a supplier is genuine or that fraud is impossible.
- No automatic payment authorisation through WhatsApp, email or one-click untrusted links.
- No direct access to users' personal banking PINs, passwords or OTPs.
- No publicly searchable supplier ‘trusted’ registry and no public naming/shaming of suspected accounts.
- No obligation to perform image-forensic classification of screenshots; use authoritative transaction evidence instead.
- No assertion that a generic AI model determines security verdicts.

---

## 5. Scope and implementation truth table

**Release R0: local HackSecure prototype (available in supplied web-secure archive). R0.5: planned enhanced demo; R1: controlled pilot; R2: broader production rollout.**

| Capability | R0 current implementation | Next intended state |
|---|---|---|
| Web UI with owner/bookkeeper/cashier roles | Implemented, local demo | Polish dashboards and accessibility |
| Authentication, CSRF, tenant-scoped queries, account lockout | Implemented basic controls | MFA/passkeys, recovery, stronger sessions, PostgreSQL RLS |
| Supplier onboarding with initially unverified status | Implemented | Independent CIPC / business identity assurance |
| Comparison of invoice account with verified stored record | Implemented via manual entry and HMAC | Safe document ingestion/OCR; confidence checks |
| Bank account verification | Synthetic mock AVS | Authorised AVS provider, agreed match semantics |
| Owner callback attestation and account-change approval | Implemented with password re-check | Trusted-contact provenance, maker-checker, high-risk holds and alerts |
| Registry/CIPC verification | **Not integrated** | Mock CIPC adapter in R0.5; authorised official/partner lookups in pilot |
| Sales and incoming-payment matching | Synthetic events; owner manual attestation | Provider sandbox (R0.5), live approved partner later |
| Paystack/PayFast/Ozow/Stitch/Peach connectivity | **Not integrated** | Select one sandbox first; avoid committing to unapproved credentials |
| Incident recording, suspected-account reports | Implemented basic workflows | Moderation, appeals, response playbooks |
| Signed receipts and hash-chained audit | Implemented in local demo | External immutable checkpointing, key protection |
| Field encryption for supplier PII / KMS | **Not implemented** | Required before storing real data |
| WhatsApp messages | **Not integrated** | Opt-in notification service only; approved utility templates |
| Live company-monitoring, user interviews, penetration test | **Not completed in supplied implementation** | Pilot requirements |

**Rule:** demo results must display `SIMULATED / MOCK` wherever source data are fictional. Nothing in an R0 mock flow may be re-labelled as live verified by changing display text alone.

---

## 6. Core user journeys and decisions

### 6.1 Journey A — Establish a trusted supplier

1. Owner or bookkeeper creates a supplier record. Its state starts `UNVERIFIED`.
2. The operator records the supplier type and an **independently sourced expected identity**, not just identity text copied from the invoice.
3. For a registered company, a company-information adapter checks registration, legal name, current status and available historical/director-change signals. R0.5 uses **fictional CIPC-style fixtures only**. CIPC does not authenticate the invoice sender.
4. A separate AVS adapter checks whether the bank account information is consistent with the expected legal identity (subject to the provider's supported checks). R0 uses a **mock**.
5. Owner performs callback using a previously trusted number sourced from established records/contract or a separately validated switchboard, not from a suspicious invoice or new search result. System records **source of number**, time, actor, method and partial-account confirmation.
6. If required independent checks agree, set `VERIFICATION_CHECKS_COMPLETED` (R0 must instead say `DEMO_VERIFIED`). Any mismatch or unavailable mandatory source produces `HOLD_*`.
7. For a sole proprietor / informal supplier, route to a documented alternate due-diligence workflow; absence of CIPC or VAT registration is **not proof of fraud**. Do not label such a supplier `CIPC_VERIFIED`.

**Trust caveat:** company hijacking, colluding contacts and SIM-swapped numbers are residual risks. Recent director changes, unusual timing, first-payment limits and cooling-off mitigate risk; they do not prove safety.

### 6.2 Journey B — Check a supplier invoice before EFT

1. Bookkeeper selects approved supplier and enters invoice reference, amount, recipient/account and optional suspicious text. Manual input is R0; secure PDF upload is planned.
2. Backend checks authenticated user, business scope, role and input validity.
3. Trust Engine compares the submitted account HMAC to the approved supplier fingerprint and checks verification state, risk holds and report corroboration.
4. Account mismatch -> **`STOP_CHANGED_ACCOUNT`**; unverified supplier -> **`HOLD_UNVERIFIED_SUPPLIER`**; conflicting/expired evidence -> **`HOLD_REVERIFY`**; matching approved synthetic record -> **`MATCHES_VERIFIED_DEMO_RECORD`** in R0.
5. System gives next action: do not pay; use established callback; refer to owner. Creates event and signed receipt.
6. Optional WhatsApp alert says only that an invoice or supplier-change review requires attention. **Never transmit account details or offer approve-by-reply.**

A match means “account matches the trusted record,” **not** “invoice sender is genuine” or “safe to pay.” FraudFence does not block an EFT initiated elsewhere.

### 6.3 Journey C — Supplier changes banking details

1. Staff proposes a change, storing it as `PENDING`; existing approved record stays unchanged.
2. Trust Engine re-checks registered company identity as appropriate, AVS, risk flags and an independent callback to the **old trusted contact**.
3. A company registry or AVS mismatch -> `HOLD_IDENTITY_MISMATCH` / `HOLD_BANK_MISMATCH`, with **no force-approve**.
4. Proposed production control: initiator cannot approve own proposal; an owner with phishing-resistant MFA and appropriate role approves only after checks. Single-person businesses need a clearly defined step-up and cooling-off exception rather than an impossible two-person requirement.
5. Proposed production control: recent change, newly enrolled supplier or first high-value payment triggers cooling-off/limits and out-of-band alerts.
6. Approved changes are versioned; old fingerprints and history are retained according to a defined retention policy, not silently overwritten.

**R0 caveat:** current prototype supports pending change and authenticated owner approval with password step-up, but not a complete no-self-approval / timed-cooling-off production policy.

### 6.4 Journey D — Check whether a customer paid

1. Cashier creates a sale with a unique reference (`FF-1058`) and an amount in integer cents.
2. Sale starts `PAYMENT_UNVERIFIED`.
3. If the customer only displays a screenshot, SMS or EFT claim, sale **remains unverified**.
4. Where available, an integrated provider receives a payment via provider checkout or reports a status; FraudFence authenticates signed callback metadata **and queries the provider server-to-server** before changing status.
5. Match provider transaction ID, merchant identity, currency, reference, amount, state, freshness and unique use. Duplicates, ambiguous matches, mismatches or missing data do not produce confirmation.
6. `PROVIDER_CONFIRMED` means payment succeeded per **provider-defined** semantics; it does not necessarily mean bank-settled. `BANK_SETTLED` requires independently confirmed merchant bank-credit evidence. An unrelated EFT needs a separate authorised bank-data source.
7. If owner checks their bank and attests manually, label `OWNER_ATTESTED_NOT_BANK_VERIFIED`; do not silently promote to `BANK_SETTLED`.
8. Notify cashier in-app and optionally owner by WhatsApp of the **recorded status**, without inventing a successful payment.

**R0 caveat:** payment matching operates on synthetic settled events and must display `SIMULATED_PAYMENT_MATCH` when they match.

### 6.5 Journey E — Respond to suspected fraud

User selects the suspected incident category (diverted payment, fake POP, account compromise, malicious link). FraudFence prioritises contacting the business's own bank using independently obtained contact details, securing compromised accounts, preserving source evidence, recording essential chronology and obtaining assistance. A case ID and signed evidence summary can be generated. Shared suspected-account reports are **unverified allegations**, deduplicated per business; corroboration warrants investigation, not a defamatory public “confirmed scammer” label. Provide correction/appeal procedures before network-wide pilot rollout.

### 6.6 Journey F — WhatsApp notifications, not authorisation

1. Owner opts in explicitly and verifies a notification phone number; app stores consent purpose, timestamp and preference.
2. A server-side **validated** event changes status and writes an audit event.
3. An outbox/queue constructs a minimally revealing message using an approved utility template.
4. WhatsApp provider delivers the notification; API responses and delivery receipts update *delivery status only*.
5. The user opens the FraudFence website **via a bookmarked/known address** and authenticates to review details. The message may show a neutral event reference but never sensitive banking data, passwords, OTPs, full invoices or approval links that bypass login.
6. Failed or delayed WhatsApp delivery has **no effect** on the authoritative verification result. An in-app notification remains available. Include opt-out, rate limiting and deduplication.

**Never send** “payment received” merely because the customer clicked a button, uploaded a screenshot or a payment notification arrived without authoritative validation.

---

## 7. Decision engine: enforceable state policy

### 7.1 Supplier and invoice states

| Domain | States | Transition rule |
|---|---|---|
| Supplier | `UNVERIFIED` → `BANK_CHECKED` → `VERIFICATION_CHECKS_COMPLETED` | Only after independently established identity, supported AVS and callback; use `DEMO_VERIFIED` for mocks |
| Company evidence | `NOT_CHECKED`, `MATCH`, `MISMATCH`, `UNAVAILABLE`, `STALE` | A CIPC match is one evidence point, not full supplier identity proof |
| AVS evidence | `NOT_CHECKED`, `MATCH`, `PARTIAL`, `NO_MATCH`, `UNAVAILABLE` | `NO_MATCH` or `UNAVAILABLE` blocks positive verification; `PARTIAL` requires review |
| Change | `PENDING`, `HOLD`, `APPROVED`, `REJECTED`, `EXPIRED` | Approval requires authenticated authorised actor, verified evidence, audit event and risk-gate checks |
| Invoice | `STOP_CHANGED_ACCOUNT`, `HOLD_UNVERIFIED_SUPPLIER`, `HOLD_REVERIFY`, `HOLD_REPORTED_ACCOUNT`, `MATCHES_VERIFIED_RECORD` | Highest-risk contradictions take precedence; R0 positive result always labelled `...DEMO_RECORD` |

**Precedence:** mismatch/explicit high-risk hold > unavailable/incomplete verification > report-review hold > record match. A community report never downgrades a STOP to HOLD or produces a definitive guilty verdict.

### 7.2 Payment states and what users may be told

| Internal status | Required evidence | Safe UI wording |
|---|---|---|
| `PAYMENT_UNVERIFIED` | None or customer claim only | “Not verified — do not rely on screenshot” |
| `PENDING` | Initiated but incomplete | “Payment pending — no confirmation yet” |
| `AMBIGUOUS` | Multiple plausible records / matching conflict | “Cannot match this payment; review required” |
| `TEST_PROVIDER_CONFIRMED` | Verified **sandbox** event + provider check | “Test payment confirmed (no real money)” |
| `PROVIDER_CONFIRMED` | Authenticated live provider success + server-side validation | “Payment confirmed by [provider]; not necessarily bank-settled” |
| `BANK_SETTLED` | Authorised bank/settlement feed proves merchant funds credited | “Funds credited according to [source] at [time]” |
| `OWNER_ATTESTED_NOT_BANK_VERIFIED` | Owner declares they inspected bank app | “Manually confirmed by owner; not independently bank verified” |
| `FAILED`, `EXPIRED`, `REVERSED` | Provider/bank source state | “Payment failed / expired / reversed; review required” |

Positive transaction wording must come from authoritative sources and specific provider-contract semantics. Payment-source time, freshness, refund/reversal policy and idempotency are mandatory in production.

### 7.3 No AI authority

Security verdicts are computed from validated inputs and deterministic policy rules. OCR, text extraction and optional AI-generated explanations may assist usability but must be treated as **untrusted presentation/input-processing components**. Prompt injection within invoices must never override approvals or payment status.

---

## 8. Application UX and primary screens

1. **Sign-in / MFA:** organisation-scoped login, trusted-device review, secure recovery; demo uses local password login.
2. **Owner dashboard:** pending supplier changes, holds, payment-status requests, incidents, alert preferences, security events and audit exports.
3. **Supplier vault:** masked account suffix, identity evidence and freshness, independent trusted-contact provenance, change history and risk status.
4. **Invoice checker:** choose supplier, enter account/reference/amount; structured comparison result with evidence source, confidence boundaries and next step; later protected PDF upload.
5. **Sales & payment status:** sale-specific visibility for cashiers; unique reference, provider test/live label, bank settlement distinction and historical changes.
6. **Approval centre:** maker-checker review, callback record, AVS/company statuses, cooling-off timer and re-authentication.
7. **Incidents & evidence:** category-driven response, private case log, signed receipts and safe export.
8. **Security & notification settings:** staff invitations, role permissions, session revocation, MFA, verified notification contacts, WhatsApp opt-in/out and minimal delivery history.

**Accessibility:** plain English first, mobile responsive, keyboard accessible, low-bandwidth pages, clear colour **and text** states; future language packs (isiZulu, Sesotho, isiXhosa, Afrikaans) should never change rule outcomes. Never depend solely on colour to communicate HOLD/STOP.

---

## 9. Security by design and privacy requirements

### 9.1 Security objectives

Maintain confidentiality, integrity, availability, auditability and least privilege. Prevent information disclosure across businesses and stop spoofed events/unauthorised approvals from affecting decisions. Assume compromise is possible and design for detection, containment and recovery.

### 9.2 Threats, required controls and actual status

| Threat | Required control | R0 status |
|---|---|---|
| Password theft / owner compromise | Argon2id, distributed rate limiting, passkeys/MFA, session revocation, protected recovery | Argon2id/lockout/session basics; passkeys/recovery **not built** |
| Cashier sees suppliers / owner-only actions | Server-enforced RBAC + denied-by-default API permissions | Basic RBAC **implemented** |
| Shop B accesses Shop A | Authenticated `business_id` scope on every query and test; PostgreSQL RLS for defence in depth | Application-level scope/tests **implemented**; DB RLS **not built** |
| SQL injection / bad input | Parameterised queries, strict validation, robust access review | Basic validations; independent audit still required |
| Stolen database/backups | HMAC account fingerprints, field-level envelope encryption for supplier PII, encrypted backups, separate KMS keys | HMAC **implemented**; field encryption/KMS **not built** |
| Keys and provider credentials leaked | Secrets manager/KMS, distinct environments, minimum key permissions, rotation and secret scanning | Local demo key files; production key isolation **not built** |
| Browser CSRF/XSS/clickjacking/session theft | CSRF checks, encoding/CSP, SameSite+HttpOnly cookies, TLS/Secure cookies, HSTS | Demo controls partly **implemented**; TLS production setup pending |
| Changed supplier payment destination | Immutable original until verified change, independent callback and AVS, maker-checker, cooling-off | Change approval & callback demo **implemented**; full maker-checker/cooling-off pending |
| Compromised CIPC record, cloned site, ported number | Cross-source checks, historical differences, multi-contact escalation, time/amount caps | Threat-modelled; real enforcement pending |
| Fake payment webhook / replay | Verify signature on raw body, verify with provider API, unique event/transaction IDs and idempotent state updates | Only synthetic events; real adapter **not built** |
| False scam report / competitor abuse | Business authentication, moderation, neutral reports, appeals, no public accusations | Allegation states/dedup basic; moderation pending |
| Changed audit/receipt | SHA-256 hash chain, Ed25519 receipt signing, protected independent checkpoints | Chain/signatures and export **implemented**; external WORM pending |
| Privacy leak through WhatsApp | Consent + approved templates + minimal content; no sensitive data or approvals | Design only; **not integrated** |
| Lost or hijacked account via recovery | Recovery at least as strong as sign-in, second admin/verified process, cooling-off and alerts | **Not built** |
| Malicious file upload / dependency | Type/magic validation, size caps, isolated parser, AV scan; pinned dependencies/CI scans | PDF upload not built; controls required before adding it |
| Ransomware/deletion | Encrypted independent backups, restore drills, incident response | **Not built** |

**Key nuance:** Moving secrets into `.env` is not the same as protecting them with KMS. If both data and decryption/signing keys are stolen, encryption and signatures do not guarantee protection. Privileged runtime compromise remains a critical residual risk.

### 9.3 Minimum privacy controls for any real pilot

- Document roles and responsibilities under POPIA, including whether FraudFence is acting as an **operator** for its business customers for particular processing activities; obtain required written operator agreements where applicable.
- Define purposes, lawful basis, privacy notice and user/employee/supplier data handling; collect the minimum required fields.
- Protect relevant personal information in transit and at rest; no full bank account number in general logs, WhatsApp or receipts; keep keys independent.
- Enforce tenant isolation both in service logic and, for production, database row-level policies.
- Define retention and deletion rules per record: raw invoice uploads, transaction references, security events, logs, complaints and evidence; reconcile audit integrity with deletion needs.
- Provide access correction/deletion workflows where legally applicable; protect incident and suspected-account allegations.
- Train operators, implement breach detection/notification response, test backups and incident recovery, and conduct a threat-based independent security review.
- No claim of formal POPIA certification, bank affiliation or legal proof.

### 9.4 Secure recovery and administrative access

Use phishing-resistant MFA/passkeys for owner accounts at pilot stage. Do not permit a casual support-desk reset of a compromised owner's credentials. Require higher-assurance recovery, alert existing administrators, invalidate old sessions and place sensitive approvals under temporary hold. Production support and cloud administrators should have least privilege, access logs and break-glass approval rather than standing unrestricted access to customer plaintext.

---

## 10. Data model and audit evidence

**Proposed logical entities:** `Business`, `User`, `Membership/Role`, `Session`, `Supplier`, `SupplierVerificationEvidence`, `SupplierTrustedContact`, `SupplierAccountVersion`, `AccountChangeRequest`, `InvoiceCheck`, `Sale`, `PaymentAttempt`, `ProviderEvent`, `PaymentMatch`, `Incident`, `SuspectedAccountReport`, `AuditEvent`, `SignedReceipt`, `NotificationPreference`, `NotificationOutbox`, `DeliveryReceipt`, `KeyVersion`, `RiskHold`.

Data rules:

- Every business-owned row carries a `business_id` or equivalent scoped tenant key; never trust a tenant identifier supplied by the browser.
- Supplier account fingerprint: keyed HMAC with protected secret and only last four digits rendered; keep raw submitted account in volatile processing where possible. If a provider absolutely requires storage, separately justify and encrypt it.
- Currency amounts represented as integer cents; references unique at defined merchant/sale scope.
- Payment transactions uniquely associated with at most one sale; tolerate webhook duplicates and reordering safely.
- Callback evidence includes the trusted number's provenance, actor, date, method and limited masked confirmation; do not store unnecessary secret challenge answers.
- Company and AVS evidence includes provider, request ID, returned fields, timestamp, freshness, limitations and mock/live designation.
- Security events are append-only in application logic; periodically anchor signed checkpoints externally for tamper-evidence beyond the server itself.
- Receipt verification is minimal for anyone possessing the link/ID; detailed data require an authenticated, authorised tenant session. Avoid predictable IDs.
- Sensitive notes, supplier phone numbers, identities and relationships require field encryption and clear retention limits before real data use.

### 10.1 Illustrative record lifecycle

`UNVERIFIED_SUPPLIER` → evidence records → `DEMO_VERIFIED / VERIFICATION_CHECKS_COMPLETED` → invoice checks → `HOLD/STOP/MATCH` → audit/receipt → opt-in alert. Independent bank/provider status, where integrated, produces separate sale/payment evidence. Audit and delivery-event records must never be mistaken for payment settlement records.

---

## 11. Integration contracts and trust boundaries

| Integration | Direction and trust | Required gating |
|---|---|---|
| CIPC or authorised company-information partner | Backend outbound request to authorised source; may return company details/status/history | Credentials, terms, available API fields/refresh, error handling; no screen-scraping as production trust source |
| Bank AVS provider | Backend outbound request for supported account-identity checks | Contract, permissions, supported match semantics, name/registration consistency and fail-closed logic |
| Payment provider (first candidate: Paystack sandbox) | Backend creates test transaction; provider callback; backend verifies status directly | Test keys, signed-webhook validation, exact amount/reference/merchant, unique transaction, retry/replay handling |
| Ordinary EFT bank feed | Authorised backend connection to merchant-account data | Separate bank access consent/partnership; never infer from unrelated gateway transactions |
| WhatsApp Business Platform | Backend notification outbox to official provider; asynchronous delivery status | Consent/opt-in, approved utility templates, rate/dedup controls, minimum content, secure token storage |
| Original business email (optional later) | Read-only consented mailbox API, not forwarded PDFs | Correct trusted receiver's authentication results; avoid treating email pass as supplier legitimacy |

**Sandbox separation:** use different environment flags, credentials, webhook URLs and visibly different UI labels for `DEMO`, `SANDBOX` and `LIVE`. Reject any promotion from mock status to production verified states. Production failover may leave a check on HOLD but must never invent confirmation.

### 11.1 WhatsApp template examples (illustrative, subject to platform approval)

**Payment review request:** “FraudFence SA: A payment check for sale {{reference}} needs review. Open your usual FraudFence website to view the status. We never request your bank PIN or OTP.”

**Payment update:** “FraudFence SA: The payment status for sale {{reference}} changed. Open FraudFence to review the verified evidence.” **Only** a server-validated status change may trigger this.

**Supplier security alert:** “FraudFence SA: A supplier payment-detail change is on hold. Sign in to FraudFence using your usual address to review.”

**Account security alert:** “FraudFence SA: A sensitive account action was detected. If unexpected, visit FraudFence through your saved website address and review your security activity.”

**Forbidden WhatsApp content:** full bank account numbers, supplier private contacts, passwords, OTPs, balances, arbitrary invoice text, direct unauthenticated approval links, “funds received” based on screenshots or raw payment notifications.

---

## 12. Requirements catalogue and acceptance criteria

These are **final-product requirements**. Each ID includes a delivery phase; only items explicitly labelled `R0 implemented` have a corresponding existing prototype pathway.

| ID | Requirement | Phase | Acceptance criteria |
|---|---|---|---|
| FR-01 | User login and server-side RBAC | R0 implemented | Cashier cannot read supplier endpoints; owner-only mutations denied to others |
| FR-02 | Tenant data isolation | R0 basic / R1 hardened | Cross-business guesses, reads and writes are denied; R1 has RLS defence in depth |
| FR-03 | Supplier created `UNVERIFIED` | R0 implemented | Saving a record never yields a fully verified verdict |
| FR-04 | Independent source for legal identity and trusted contact | R0 assertion / R0.5 evidence | Invoice-only identity/contact never becomes an independent trust anchor |
| FR-05 | CIPC/company evidence adapter | R0.5 mock / R1 real | Matches registration/name/status; mismatch or unavailable -> HOLD; mock labelled |
| FR-06 | AVS adapter | R0 mock / R1 real | `NO_MATCH`, unavailable or incompatible partial result cannot produce VERIFIED |
| FR-07 | Three-source verification policy for registered companies | R0.5 / R1 | Relevant company, AVS and trusted callback evidence consistent before completion |
| FR-08 | Alternative verification for non-CIPC suppliers | R1 | Does not assume sole proprietors are fraudulent; documented independent evidence and controls |
| FR-09 | Supplier-account fingerprint compare | R0 implemented | Any changed account yields STOP before lower-priority warnings |
| FR-10 | Proposed account changes stay pending | R0 implemented | No staff member may directly replace approved account via invoice input |
| FR-11 | Strong owner approval + maker-checker | R0 password recheck / R1 MFA | Unauthorised/self-approval blocked where separation required; mismatch never overridden |
| FR-12 | High-risk cooling-off, director-change and first-payment limits | R0.5 / R1 | Recently changed/suspicious supplier flagged; hold enforced on configured threshold |
| FR-13 | Invoice check and explanations | R0 manual / R1 uploads | Explains checked vs unchecked evidence; prompt injection has no authority |
| FR-14 | Sale-specific reference and matching | R0 synthetic / R1 live | Exact amount/ref/source, unique payment allocation and ambiguous-match hold |
| FR-15 | Payment-provider sandbox integration | R0.5 | Authenticated test callbacks + server-side verification; explicit test status |
| FR-16 | Live provider and bank feed for real payments | R1 | Real provider success and bank settlement are clearly distinguished |
| FR-17 | Manual owner payment attestation | R0 implemented | Display explicitly says *not bank verified* |
| FR-18 | Incident help and evidence | R0 implemented / R1 expanded | Clear first response, timestamped private case, minimally necessary data |
| FR-19 | Suspected-account reports | R0 basic / R1 moderated | One report/business/account; unverified allegation, appeal and moderation controls |
| FR-20 | Tamper-evident signed receipts | R0 implemented / R1 anchored | Modified receipt fails; detailed records are tenant-private; external anchor at R1 |
| FR-21 | Consent-based WhatsApp notifications only | R0.5 mock / R1 live | Only validated event triggers message; no approval via message; opt-out works |
| FR-22 | User security settings and session revocation | R1 | Owner can revoke staff access and sessions promptly |
| FR-23 | Secure owner recovery | R1 | No unauthorised support reset; MFA/step-up, cooldown and alerts |
| FR-24 | Encrypted supplier PII and secret management | R1 | Stolen DB alone lacks usable sensitive plaintext; secrets independent and rotated |
| FR-25 | Retention/deletion and privacy controls | R1 | Per-record schedule tested; POPIA notices/agreements and breach plan present |
| FR-26 | Production observability, backup/restore and security testing | R1 | Failure alerts, restore test and independent security review completed |

### 12.1 Non-functional requirements

| Area | Requirement and validation |
|---|---|
| Security | Threat-driven access tests, no exposed demo credentials, HTTPS, hard session controls, secure supply chain |
| Integrity | Idempotent provider events; all important state changes audited; key versioning and independently anchored hashes |
| Privacy | Minimise display and storage; segregate tenants; configurable retention; WhatsApp opt-in/out |
| Reliability | Verification provider timeout returns HOLD; WhatsApp failure never changes payment truth |
| Performance | Proposed pilot SLOs: text/manual status under 5 seconds excluding external provider latency; UI must acknowledge pending long-running calls |
| Usability | Mobile responsive, low-data, plain-language action and risk state, accessible keyboard and screen reader flows |
| Operations | Separate DEV/SANDBOX/PROD, observability with sensitive-data redaction, incident playbooks and tested disaster recovery |
| Evidence | Every decision exposes evidence source, time, rule version, actor and explicit uncertainty |

---

## 13. Acceptance scenarios: demonstrate both protection and limitations

1. **Changed bank account:** seeded invoice bank account differs from approved fingerprint -> `STOP_CHANGED_ACCOUNT`, signed receipt, owner alert queued if opted in.
2. **Poisoned first supplier:** new supplier saves attacker-controlled account -> remains `UNVERIFIED`; cannot become trusted from invoice-only source.
3. **Borrowed company identity:** registered company fixture matches, mock AVS returns `NO_MATCH` -> `HOLD_BANK_MISMATCH`; callback cannot override.
4. **Company hijack signal:** fictional director details recently changed plus bank-account change -> `HOLD_FURTHER_REVIEW` pending independent investigation.
5. **Stolen/ported callback number:** trust-contact provenance cannot be replaced by current invoice; suspicious number change triggers review.
6. **Insider:** bookkeeper creates bank-change proposal then attempts to approve via API -> `403`; actor and violation logged.
7. **Cross-tenant attack:** Shop B user guesses Shop A supplier ID -> denied without disclosing private details.
8. **Forged invoice prompt:** embedded “ignore your rules” text has no effect on deterministic STOP.
9. **Fake POP screenshot:** screenshot alone produces `PAYMENT_UNVERIFIED`.
10. **Provider sandbox success:** sandbox webhook authenticated and status re-queried -> `TEST_PROVIDER_CONFIRMED`, not `BANK_SETTLED`.
11. **Webhook replay:** duplicate callback/transaction ID does not validate second sale.
12. **Owner attestation:** records manually attested status, never converts into live bank-confirmation label.
13. **Audit tamper:** modification of signed receipt fails signature verification; anchored checkpoint mismatch flags rewritten history.
14. **Notification privacy:** WhatsApp body lacks full account/contact details; duplicate event generates at most one notification; delivery failure does not alter verification status.
15. **Secrets/data breach simulation:** database dump does not reveal raw bank account numbers; after R1 encryption, does not reveal supplier phone numbers or incident PII without keys.
16. **Provider outage:** failed CIPC/AVS/bank lookup returns appropriate HOLD/PENDING, never positive verified status.
17. **Lost-owner-device recovery:** unsupported reset attempt rejected, current sessions revoked through a higher assurance process once implemented.

**Test evidence:** preserve repeatable scripts, automated test outputs, environment labels and timestamps. Do not present planned adversarial cases as already passing.

---

## 14. Delivery plan and dependencies

### R0 — Existing hackathon reference prototype (completed in supplied archive)

- FastAPI web UI and local SQLite store; demo users and role separation.
- Supplier unverified state, HMAC invoice comparison, owner confirmation workflow and mock AVS.
- Synthetic sale/payment reconciliation and owner manual-attestation distinction.
- Incident and suspected-account report workflows.
- Signed receipts, hash-chained logs, exported checkpoint, browser security headers and baseline tests.

**Demo limitations:** no actual CIPC, WhatsApp, Paystack, live AVS, ordinary EFT feed, safe invoice OCR, encryption of all PII, RLS or passkeys.

### R0.5 — Next demonstrable improvements (priority order)

1. Mock CIPC/company adapter and three-source rule for registered companies; explicit sole-trader exception policy.
2. Provenance-locked trusted contact and optional simulated cooling-off / first-payment cap.
3. Maker-checker / no-self-approval rule for staffed businesses, including owner-only safe exception policy.
4. Mock WhatsApp notification outbox (record queue and delivery result in web UI); no sensitive data in templates.
5. One real provider sandbox integration *only if credentials and testing access are ready*; otherwise retain clearly labelled mock.
6. Data-leak tests for log redaction and key/data separation; avoid overstating field encryption until built.

### R1 — Controlled SMME pilot (gated)

- Business onboarding and user validation; real AVS + authorised registry source where available; payments only through contracted verified providers.
- Managed PostgreSQL with RLS, encrypt sensitive PII, backups, KMS/secrets, passkeys, secure recovery and support access.
- Official WhatsApp Business notification templates with recipient opt-in, approved messaging and delivery observability.
- Safe invoice upload/OCR, retention/deletion jobs, POPIA governance, incident response, abuse moderation and independent security review.
- Consent-based pilot with no real payment/stock decisions until evidence pathways and safeguards pass acceptance.

### R2 — Scale

- More payment and bank data providers, multi-language support, accessible mobile flows, user-requested integrations and affordable subscription/partner options.
- Strengthen metrics, fraud patterns and incident partnerships **without creating an unmoderated public accusation database**.

### Hard launch gates

No live SMME payment decision, production data import, real WhatsApp messaging or public launch until the appropriate vendor keys/contracts, legal/privacy review, authentic verification inputs, MFA/recovery, tenancy protections, encryption, retention, incident response, audit anchoring, security assessment and support operations are demonstrably ready. An event demo is not a security certification.

---

## 15. HackSecure presentation and demonstration (judges' pack alignment)

The official judges' pack allows **3 minutes for pitch plus demo and 1 minute of questions**, with **5 slides maximum**. Team FORGE is listed at 13:28 on 28 October 2026; organisers may change order. Slides are due at noon. The pack also warns against presenting mocks as real services or implying entirely pre-built work was completed during the event.

**Suggested three-minute structure:** 0:00–0:30 problem/user; 0:30–2:00 real locally running supplier change STOP plus tenant isolation/owner denial and signed receipt; 2:00–2:30 security-by-design and explicit remaining threats; 2:30–3:00 practical SMME impact, WhatsApp notification vision and truthful integration roadmap.

**Best mentor / judge attack:** Show that a fictional valid CIPC company record does **not** approve a different bank account when mock AVS mismatches, then show a cashier/bookkeeper cannot bypass the hold or view another business's data. This scenario is a planned R0.5 demonstration until code is implemented.

**Talk-track boundary:** “The security workflow is coded and tested with fictional suppliers; company and bank source results are simulated. WhatsApp will only send opt-in status notifications. A real payment success can only come from an authenticated provider and is not the same as bank settlement.”

---

## 16. Risks, assumptions and open decisions

| Topic | Risk / open choice | Proposed mitigation or decision owner |
|---|---|---|
| Real CIPC access | API data and field/history access may depend on subscriptions or partners | Validate official availability, terms, prices, accuracy and update cadence before naming product as integrated |
| Real AVS | Bank coverage and name-match semantics vary | Select provider and run match, partial and outage tests |
| Informal supplier onboarding | Registry-based hard gate excludes legitimate sellers | Design separate risk-based evidence and escalation policy |
| Payment providers | Sandbox outcome not equivalent to merchant bank credit | Distinct states, direct verification and documentation |
| Supplier contact compromise | SIM swap / cloned website can subvert callback | Previously trusted provenance, change alerts, second contact for risk, cooling-off |
| Owner-only business | Strict maker-checker impossible for sole owner | High-assurance solo exception with timing/limits/independent check |
| Data breach | Cross-tenant access and relationship graph leak | RLS, encryption, KMS, privacy minimisation and testing |
| Receipts | Server-key theft / server log rewrite | Protected signing keys and independent WORM anchors |
| WhatsApp phishing | Spoofed notification / message forwarding | Minimal wording, verified sender, bookmarked-site instruction, never approvals by chat |
| False security claims | Users mistake demo MATCH for live bank verification | Persistent source labels, disclosures and test/live boundaries |
| Unit economics | WhatsApp messaging, AVS queries and support may exceed subscription | Provider pricing and cost-to-serve discovery before public fees |
| Social proof | Limited real user interviews | Interview owners, cashiers and bookkeepers before pilot decisions |

### Decisions for Team FORGE to record

- Final product is **web first**; WhatsApp is **opt-in notification only**.
- Primary product emphasis is **outgoing supplier-payment protection**; customer-payment evidence and incident response are supporting flows.
- Company lookup is **one evidence source**, not a guarantee; unregistered supplier handling is explicit.
- AVS and CIPC remain **mock or manual until authorised live access**; payment sandbox is separate from bank settlement.
- Verdicts are deterministic and fail closed; AI may explain but never decide.
- FraudFence has no authority to execute or stop external EFTs.
- Protection of the platform (tenant isolation, cryptography, recovery, audit integrity and POPIA) is a core product feature, not optional infrastructure.

---

## 17. Source baseline and terminology

This PRD consolidates the following **team-provided** materials, interpreted according to their actual content:

1. *FraudFence SA — Product Requirements Document*, 16 October 2026 (original payee check, money check, incident response, local scam reporting and audit plan).
2. *FraudFence SA — BEC & Invoice Fraud Research*, 27 October 2026 (South African context, verification receipt, AVS adapter, sender-check boundaries).
3. *FraudFence SA — Fixes for the mentor's technical issues*, 27 October 2026 (initially unverified suppliers, real email provenance limitations, removal of shared verified-supplier registry, signed receipts).
4. *FraudFence SA — Red team: attacking our own system*, 27 October 2026 (CIPC/AVS/callback corroboration, insider and company-hijack attacks, data/keys and account-recovery risk, privacy and evidence hardening).
5. *FraudFence-SA-Web-Secure* code archive, README, HOW_IT_WORKS and WEB_SECURITY_BLUEPRINT (the existing reference prototype and its limitations).
6. *HackSecure 2026 Participant Guide* and *HackSecure 2026 Judges' Pack* (Track 3 fit, pitch format and judging requirements).
7. Team's subsequent product decisions in this conversation (secure web app instead of WhatsApp as an interaction channel; WhatsApp alerts for status changes and payment-review notifications).

**Terminology:**

- **CIPC:** Companies and Intellectual Property Commission; registry checks establish recorded legal-company details, not the sender's authority.
- **AVS:** Account Verification Service; checks depend on what the authorised provider exposes.
- **BEC:** Business Email Compromise, including invoice/payment redirection fraud.
- **HMAC:** Keyed cryptographic digest used to compare accounts without storing full values.
- **Maker-checker:** Distinct initiator and approver for sensitive changes.
- **Tenant:** One customer's business workspace; its data must be isolated from other businesses.
- **Provider-confirmed:** Authenticated payment-provider success, not necessarily settled in merchant's bank.
- **Bank-settled:** Trusted settlement/credit evidence from an authorised merchant-bank source.
- **Fail closed:** Missing or conflicting evidence returns HOLD/UNVERIFIED rather than approval.
- **Demo-verified:** Verification against fictional fixtures, never a claim of real-world supplier authenticity.

**End of PRD — ready for Team FORGE review and implementation planning.**
