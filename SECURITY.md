# Security policy — FraudFence SA (HackSecure demonstration)

## Current safety boundary
This repository is a **synthetic-data-only local prototype**. It has no live CIPC, AVS, WhatsApp, bank, or payment-provider integrations. The demo accounts and fictional passwords in `README.md`, tests, and seed scripts must never be used for a real deployment.

Do not run it as a public payment-verification service or use it to approve real transfers. The current SQLite data and local key-storage model are not appropriate for production.

## Reporting suspected issues
Privately contact the repository maintainers/team. Do not include secrets or real personal/financial data in a public GitHub issue. Reproduce using synthetic records only.

## Before a pilot
- Complete organisation verification, passkeys/MFA, recovery and maker-checker controls.
- Implement real integrations with authenticated evidence and clear source labels.
- Encrypt personal and supplier contact data; separate signing/HMAC/encryption keys from the database with managed key services.
- Use managed storage, encrypted backups, tenant isolation at the database layer, and external signed audit checkpoints.
- Enforce POPIA minimisation, lawful processing, retention/deletion, operator agreements and incident response.
- Add vulnerability scanning, rate-limits, operational monitoring and independent security testing.

For details read `docs/WEB_SECURITY_BLUEPRINT.md` and `docs/THREAT_MODEL.md`.
