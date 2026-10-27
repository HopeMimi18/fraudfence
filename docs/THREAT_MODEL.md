# FraudFence SA — threat model and residual risk

## Key assets

1. SMME supplier bank details and trusted historical phone numbers.
2. Authenticated owner approvals for supplier changes.
3. Sale/payment evidence used when staff decide whether to release goods.
4. Audit records and cryptographic signing keys.
5. Reported suspected accounts and their reputation implications.
6. Sensitive customer/business data and staff access privileges.

## Threat actors

- Fraudster impersonating a known supplier via compromised email or lookalike domain.
- Fraudster presenting forged proof of payment or manipulating invoice text.
- Malicious employee or stolen staff web session/account.
- Dishonest business submitting false allegations about a competitor.
- External attacker stealing application data or modifying audit evidence.
- Mistaken legitimate staff acting under time pressure.

| Attack / failure | Mitigation implemented | Residual risk |
|---|---|---|
| Initial fake supplier records | `UNVERIFIED`, owner-attested independent identity and contact | Initial identity source is self-attested, not actually independently checked; mock AVS only |
| Invoice bank-detail substitution | Fingerprint compare, STOP mismatches, owner approval workflow | Existing verified contact can be compromised; phone confirmation is a human assertion |
| Prompt injection in invoice | No LLM-authorised decisions; deterministic security logic | Regex hints are imperfect; full OCR/email ingest not implemented |
| Compromised owner session | Argon2id login, session token, CSRF, role checks and lockout | No MFA/passkeys; recovery and anomaly monitoring needed |
| Bank event forged or replayed | No public payment injection, owner demo-only endpoint, unique reference, one-to-one settlement matching | Demo owner can inject fake transactions; no real authenticated bank feed |
| Misleading receipt claims | Signature check and neutral language | Hash chaining does not stop whole-chain rewrite if server and key are compromised |
| Public receipt scraping | 160-bit+ random receipt IDs and minimal public response | No IP rate limiting in prototype; timestamps are still metadata |
| Malicious shared account reports | Tenant-distinct reports only, allegation labels, no automatic fraud designation | Two colluding businesses can still manipulate report count; moderation required |
| Tenant data leak | Server-enforced `business_id` filtering, role checks | Must conduct comprehensive endpoint and database security review before any pilot |
| Retention / POPIA noncompliance | Raw account numbers not stored, no public customer records | Other personal data remains; privacy policy/retention/access requests not implemented |
| Webhook/mailbox forgery | No claims of external authentication | Real integrations not yet built; signature validation & trusted email receiver provenance required |

## Non-negotiable production controls

- MFA or passkeys for owners and step-up verification for bank detail changes.
- Real legal-identity establishment from genuinely independent trustworthy sources.
- A contracted AVS provider with explicit account-holder match semantics, reliable failure handling and bank coverage.
- Strong payment-event source authentication and state reconciliation; never use screenshots as payment proof.
- OAuth scope minimisation, verified receiver authentication headers and breach response for mailbox integrations.
- HTTPS and secure cookies, key management / rotation, encrypted databases/backups, externally anchored audit checkpoints.
- Public endpoint throttling and report moderation/appeal; tenancy tests and independent penetration testing.
- POPIA notices, operator agreements, retention jobs, lawful basis and access/correction/deletion procedures.
- Fail-closed service degradation, reliable uptime strategy and an incident-response process.

## Specific anti-assurance language

Avoid **“Your supplier is safe”**, **“AVS confirms your real supplier”**, **“Bank payment received”** (when based on a mock/owner tap), **“Legal proof of due diligence”**, and **“Fraud confirmed”** (when based on user reports).

Prefer **“Matches an existing supplier account record”**, **“Mock AVS match (demo)”**, **“Owner attested checking their banking app; not bank verified”**, **“Tamper-evident record of performed checks”**, and **“Reported by independent businesses; not confirmed fraud.”**
