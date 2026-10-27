# FraudFence SA — Web-first security by design

**Threat model and next engineering decisions | Team FORGE**

## Principle

There is no guarantee that attackers cannot access sensitive data. Security by design means identifying important assets, minimising collected data, protecting each trust boundary, testing realistic attacks, and preparing for compromise.

## Assets to protect

- Staff credentials, owner permissions and active sessions.
- Supplier identity, contacts, registration numbers and payment fingerprints.
- Payment-provider keys, webhooks, synthetic/real transaction metadata.
- Signed receipts, audit history and cryptographic private keys.
- Incident descriptions and personally identifying information.

## Main threats and controls

| Attack | Implemented now | Still required before live data |
|---|---|---|
| Stolen login password | Argon2 hashing, login lockout, cookie sessions, sensitive-approval password step-up | Phishing-resistant MFA/passkeys, recovery, abnormal-login monitoring, IP and distributed throttling |
| Cashier reads supplier records | Server-enforced role restrictions | Full privilege review and automated access-control matrix |
| One SMME reads another's data | `business_id`-scoped database queries and negative tests | PostgreSQL row-level security/defence in depth, independent penetration testing |
| Forged cross-site request | CSRF token and SameSite cookie | Production CSRF/Origin policy and secure proxy configuration |
| Malicious browser/XSS payload | Escaping in UI; CSP restricting scripts to same origin; `nosniff` | No inline CSS exceptions, formal output encoding review and dependency scanning |
| Clickjacking | `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'` | Browser testing after deployment |
| Stolen HTTP session cookie | HttpOnly, SameSite=Strict; secure cookie configurable | Mandatory HTTPS, Secure cookies, HSTS, session rotation/expiry and session management UI |
| Database theft | Password hashes, HMAC fingerprints of bank accounts | Encryption at rest for supplier PII, encrypted backups, short retention, strong key separation |
| Fake invoice instructions | Deterministic rules ignore untrusted invoice instructions | File upload validation/OCR sandbox when supporting PDFs |
| Fake payment webhook | No real provider integration; mock feed clearly labelled | Provider signature verification, event replay/idempotency checks, server-to-server status check, settlement semantics |
| Fake supplier change | Trusted record, independent call attestation, owner approval, owner password step-up | Out-of-band identity proof, passkeys, maker-checker, real AVS provider |
| Forged audit history | Hash chain, Ed25519 receipts, signed checkpoint export | External immutable audit anchors, key isolation/rotation, alerting |
| False scam reports | Unverified allegations, duplicate-business controls | Reporter identity, moderation, appeals, fraud abuse prevention |

## Current implementation details

1. **Browser security response headers:** CSP, no-sniff, frame denial, referrer control, permissions policy, no-store caching. HSTS only when the secure-cookies environment flag is on.
2. **Access:** every protected API route checks the signed-in user and role on the server. Supplier and payment queries are scoped by the authenticated business ID.
3. **High-risk change approvals:** require owner role, CSRF and fresh password verification. This is useful *step-up* but not multi-factor authentication.
4. **Privacy:** minimal public verification, HMAC of bank account, no account number in receipt response. BUT names/phone/incident narrative remain plaintext in the demo SQLite DB.
5. **Integrity:** Ed25519 receipt signatures and chained log hashes are checked in tests; offline signed checkpoint available.
6. **Test coverage:** includes forged invoice instructions, role bypass, tenant isolation, payment reuse, changed supplier bank detail, tampered receipts, re-authentication and response security headers.

## Required architecture for pilot

```
Browser -- HTTPS --> reverse proxy/WAF
                            |
                      FastAPI API
                  / auth + MFA / RBAC \
                 |                      |
       Verification service        Payment adapter
                 |                (authorised provider)
           PostgreSQL RLS                  |
                 |                 signed callback +
           envelope encryption      server-side status
                 |
       immutable audit + isolated signing keys
```

Use a managed identity provider if feasible rather than creating your own MFA and recovery flows. Use a secrets manager/KMS and separate staging from production. For uploads, verify types, limit sizes, scan files, and isolate document parsers. Build a POPIA retention/deletion policy with explicit access rights, a breach response plan and vendor agreements.

## Web app pages to build next

- **Owner dashboard:** pending supplier changes, flagged checks, incidents, security alerts.
- **Supplier vault:** verified/unverified suppliers, masked account, history and independent verification proof.
- **Invoice checker:** manual form now; PDF/CSV import only once upload safety is complete.
- **Sales & payment status:** reference and provider-verified state, distinct from bank settlement.
- **Incident and audit centre:** minimise personal data and support exports safely.
- **Settings & access:** inviting employees, revoking sessions, requiring MFA, review permissions.

## No-go list for public launch

Do not deploy seeded accounts/default passwords, leave auto-open `/docs`, trust raw payment webhooks without authenticating them, store full account numbers in logs, rely on frontend-only permissions, claim a real banking match from a mock, or allow real money/stock decisions based on this demo.

## Acceptance tests before using any real records

- User from Shop B cannot retrieve or update Shop A's record even by guessing IDs.
- Cashier gets `403` for every supplier-management and private audit endpoint.
- Owner high-risk changes fail without password re-authentication and production MFA.
- Malicious invoice text cannot override `STOP`.
- A missing, ambiguous, stale, repeated or unauthenticated payment event never produces a bank-confirmed result.
- Tampering with receipt signature fails verification.
- Sensitive HTTP responses have no-store and clickjacking protections; production cookies are Secure/HttpOnly.
- Data deletion, recovery, rate limiting, key rotation and secure backup recovery are tested.

## Standards to use for a serious product

- OWASP ASVS 5.0.0 — application security requirements.
- OWASP Session Management, Logging, CSRF, and File Upload Cheat Sheets.
- POPIA section 19 (reasonable technical/organisational safeguards) and applicable breach notification requirements.

*Engineering guidance, not certification or legal advice.*
