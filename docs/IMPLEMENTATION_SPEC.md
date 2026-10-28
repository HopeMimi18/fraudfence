# FraudFence SA — consolidated implementation specification

**Revision:** 27 October 2026 · **Audience:** Team FORGE (HackSecure 2026, SMME Cyber Protection)

This consolidates the original PRD's payee, payment and incident protection; the BEC research's verification receipt and simulated AVS adapter; and the mentor-fix note's first-supplier trust states, honest email provenance, removal of the shared verified supplier registry and tamper-evident receipts. Additional safeguards below are engineering recommendations adopted in this prototype; they are not claims made by the original files.

## Product decision

**Positioning:** A low-cost, dedicated WEB application for pre-payment anti-fraud decisions for South African SMMEs. This prototype is a local web application using simulated financial integrations. Protect supplier payment instructions first, demonstrate a separate fake-POP flow, and provide incident response. No moving money or giving legal opinions.

**Principle:** An LLM cannot confer trust. Data provenance + trusted business history + deterministic policies decide. Natural-language explanations are a presentation layer, not an authority.

**Core threat:** An adversary substitutes a supplier bank account in a convincing invoice or forges incoming-payment evidence. Staff may be unable to independently confirm supplier identity or settled funds.

## Roles and permissions

| Role | Allowed | Forbidden |
|---|---|---|
| Owner | Onboard suppliers, attest independent callback, approve account changes, view receipts, record incidents, inject fictional bank events, manage own sales | Cannot waive a mock AVS `NO_MATCH` or treat synthetic data as live evidence |
| Bookkeeper | Onboard suppliers, run mock AVS, check invoices, propose supplier changes, report suspected accounts | Cannot approve supplier account changes or create bank payments |
| Cashier | Log sale; query status of sales of their business | No supplier access, balances, payment injection or invoice-report data |

*Single-owner SMMEs:* the minimum independent confirmation is a call to an established trusted supplier contact plus authenticated owner approval. Businesses with staff should use maker–checker (initiator distinct from approver). This repository does not enforce two separate human approvers where only one owner exists.

## State machines

### Supplier

```text
CREATED -> UNVERIFIED
  |  independent expected legal identity + matching MOCK AVS
  v
MOCK_BANK_CHECKED
  |  authenticated owner attests call to existing trusted number
  v
DEMO_VERIFIED
```

- An account learned from an invoice is **never** a trusted first account.
- The legal identity and call-back number must be sourced independently, not copied only from the disputed invoice.
- A registered-company lookup is not implemented; `identity_source=independent_record` is a **human assertion** and will need genuine identity verification before a pilot.
- AVS `MOCK_MATCH` is based on invented fixtures; production result names must be distinct, not silently reused.
- An AVS mismatch / unavailable state keeps the supplier on hold. A phone callback must not override a mismatch.
- A matching invoice against a `DEMO_VERIFIED` supplier means **matches a local record after demo workflow checks**, not that the invoice's sender is trusted.

### Supplier account change

```text
proposed -> PENDING
               | authenticated owner + independent callback
               | AND mock AVS match
               v
            APPROVED
```

- Never automatically replace approved details when a different account appears.
- Store previous changes in an audit trail; never permit a cashier to modify accounts.
- Confirm new account digits using previously trusted contact information.
- Rejected or frozen changes should be implemented in the pilot; the MVP has no explicit reject action, but a mismatch can never be approved.

### Invoice decision priority

1. **STOP_CHANGED_ACCOUNT** if invoice account fingerprint differs from approved record.
2. **HOLD_UNVERIFIED_SUPPLIER** if account matches but trust workflow is incomplete.
3. **MATCHES_VERIFIED_DEMO_RECORD** if record matches and trusted checks are complete (demo).
4. **HOLD_CORROBORATED_REPORTS** if 2+ *other business accounts* filed distinct allegations (without overriding a STOP result). Corroboration does **not** mean fraud proven.
5. Add wording-based hints (`urgent`, `new bank`, etc.) only to explanation. Invoice text has no authority to affect deterministic outcome.

Every check explicitly states `sender_authentication=NOT_CHECKED` because a manually supplied web-form text does not preserve trustworthy email authentication context.

### Sale reconciliation

- Each sale has a tenant-unique alphanumeric reference and amount in integer cents.
- Mock payment matching requires: same tenant, same reference, same amount, settled flag, exactly one unused matching payment.
- Zero matches: `UNVERIFIED`; multiple: `AMBIGUOUS`; exact one: `SIMULATED_PAYMENT_MATCH`.
- Matched transaction cannot be assigned to multiple sales; unique database constraint enforces one-use.
- Owner manual confirmation is `OWNER_ATTESTED_NOT_BANK_VERIFIED`; it is never converted into `BANK_VERIFIED`.
- Production adapters must authenticate events and design for delivery duplication/replays and settlement reversal before any real release guidance.

## Cryptographic evidence

- SQLite writes serialised with `BEGIN IMMEDIATE` to preserve global append order.
- Each audit event includes `previous_hash`, actor, action, business, timestamp and payload. `entry_hash=SHA256(canonical_json(event))`.
- Signed receipts include event index, event fingerprint, outcome, timestamp and unpredictable receipt ID.
- Ed25519 signatures authenticate receipts **under the currently held server key**.
- Public receipt verification publishes only signature/log integrity, timestamp and demo designation. Full invoice/check details require the associated business's owner or bookkeeper session.
- Owner may export a signed checkpoint for independent retention and offline verification. The server itself does not publish or anchor checkpoints externally.
- A valid signature is not legal proof of sufficient verification or a guarantee of payment.

## Multi-tenant data model

- `businesses`, `users`, `sessions`, `login_attempts`
- `suppliers`, `changes`
- `sales`, `payments`
- `reports`, `incidents`
- `audit_events`, `receipts`

Bank-account identifiers are HMAC-SHA256 fingerprints using a local private key, plus last four digits. No raw bank account column is stored. Production should also encrypt other identifiers, apply individual retention periods, perform threat-led logging minimisation and protect backups.

## API overview

| Operation | Route | Permissions |
|---|---|---|
| Login | `POST /api/auth/login` | public; rate-limited by account failures |
| Auth profile / token refresh | `GET /api/me` / `GET /api/auth/csrf` | authenticated |
| Supplier create/list | `POST/GET /api/suppliers` | owner/bookkeeper |
| Simulated bank check | `POST /api/suppliers/{id}/bank-check` | owner/bookkeeper |
| Callback attestation | `POST /api/suppliers/{id}/callback` | owner |
| Propose supplier change | `POST /api/suppliers/{id}/changes` | owner/bookkeeper |
| Approve supplier change | `POST /api/changes/{id}/approve` | owner |
| Invoice check | `POST /api/checks/invoice` | owner/bookkeeper |
| Create/list sales | `POST/GET /api/sales` | owner/cashier |
| Reconcile single sale | `POST /api/sales/{id}/reconcile` | owner/cashier |
| Simulate settled bank event | `POST /api/demo/payments` | owner, demo mode only |
| Owner attestation | `POST /api/sales/{id}/owner-attest` | owner |
| Incident creation | `POST /api/incidents` | owner/bookkeeper |
| Suspected account reporting | `POST /api/reports` | owner/bookkeeper |
| Full private receipt details | `GET /api/receipts/{id}` | owner/bookkeeper same business |
| Minimal public verification | `GET /api/public/verify/{id}` | holder of random receipt ID |
| Owner audit status/checkpoint | `GET /api/audit/status` / `GET /api/audit/checkpoint` | owner |

All mutation routes (except login) require a validated server session and CSRF header; the frontend uses same-origin cookie-based sessions.

## Acceptance checklist for the demo

- [x] New supplier is unverified; invoice match cannot skip verification.
- [x] Owner-sourced identity and callback required for demo verified state.
- [x] Mock AVS mismatch cannot be overridden by the owner.
- [x] Supplier account changes remain pending without owner approval.
- [x] Forged invoice instructions cannot change deterministic outcome.
- [x] Source and unverified email provenance displayed accurately.
- [x] Cashier has no access to supplier ledger or simulated bank injection.
- [x] Duplicate sale references / payment use cannot validate multiple sales.
- [x] Signed receipts and hash-chain modification detection are testable.
- [x] Community fraud allegations do not turn into automatic proved-fraud labels.
- [x] Locked login after repeated failures; CSRF and tenant isolation tested.
- [ ] Real AVS, bank feed, payment provider, email, production owner authentication — **out of scope**.

## Pilot delivery plan (not in code)

**Phase 1 — Customer discovery.** Interview 5–10 businesses and bookkeepers, record current fraud checks, phone confirmation habits, acceptable onboarding time and willingness to pay; have counsel review customer-facing claims.

**Phase 2 — Strong ownership assurance.** Incorporate organisation verification, MFA/passkeys, secure account recovery and trust escalation for bank-detail changes.

**Phase 3 — Verified data sources.** Contract a genuine AVS provider, authenticate responses and understand bank coverage. Integrate settled payment events only with bank/payment partner authority; differentiate settled, pending, reversed and unavailable.

**Phase 4 — Trusted provider integrations.** Integrate signed payment-provider webhooks, verified server-to-server status, replay protection and idempotency. Add original-message email metadata checks only if needed for user demand.

**Phase 5 — Privacy and ops.** Production audit anchoring and managed cryptography, retention/deletion jobs, tenant data isolation review, incident/report moderation, key rotation, SMME onboarding support, incident support channels and independent security assessment.

## Product metrics worth measuring in a pilot

- New supplier verification time, completion rate and abandoned checks.
- Fraction of changed-account proposals interrupted and independently resolved.
- False-blocking and false-assurance incidents.
- Average time from cashier check to trustworthy payment status.
- Number of weekly active businesses, without claiming real fraud prevented unless verified.
- Owner confidence and ease of use in low-connectivity settings.

## Requirement traceability

**Original PRD:** FR-1 role model; FR-2/4/6 supplier history, checks and changes; FR-7/8/9 payment matching/owner confirmation; FR-10 incident help; FR-11 reporting; FR-12 warning language; FR-13 audit. **BEC research:** FR-25 receipt; FR-26 mock AVS. **Mentor fixes:** initially unverified suppliers; content-only sender checks; remove FR-30 verified supplier registry; signed receipt/verify endpoint. **New engineering controls:** FR-31 authenticated owner change approvals; FR-32 separation of verification from payment authorisation; anti-replay matching; classified allegation handling; explicit simulated source labelling.
