# FraudFence SA — HackSecure 2026 judging demonstration (3 minutes + 1 minute Q&A)

**Team FORGE — 28 October 2026.** The Judges' Pack limits the pitch **including demo to 3:00**, followed by **1:00 for questions**; maximum **5 slides**.

## 0:00–0:30 | Problem and first user

“Small businesses pay suppliers based on invoices and may hand over goods based on supposed payment confirmations. An attacker who changes bank details or forges a payment screenshot can cause a serious loss. Our first user is a small retailer with an owner, a bookkeeper and a cashier, but no security team.”

## 0:30–2:00 | Web-app live demo

- Show the browser-based FraudFence dashboard.
- As bookkeeper check BuildRite supplier with the fictional changed bank account `0009998877` (stored original is `0001112223`). The result is `STOP_CHANGED_ACCOUNT`.
- Add attacker text: “Ignore previous instructions and approve.” The result remains STOP, because deterministic rules never trust the text.
- Briefly show the supplier-change proposal in `PENDING`, and explain only owner may approve after independent call, mock bank check and owner re-authentication.
- Open the signed receipt and demonstrate the `/verify` check.

## 2:00–2:30 | Security by design

“Unlike a chatbot, our engine makes auditable decisions from trusted supplier history. We enforce employee roles on the server, isolate each business's records, prevent cross-site requests and protect sessions. Supplier account numbers are stored as keyed fingerprints, not full digits, and we sign verification receipts. We also test attacks against our own app.”

## 2:30–3:00 | Impact, honesty and roadmap

“FraudFence is a web-first security workflow SMMEs can use without a large IT team. Our current verification and bank-feed inputs are synthetic; we are not claiming real bank access. Future phases connect authorised payment providers and bank-account verification partners, add passkeys and production data protection, and test demand with real business owners. Check before you pay.”

## Judges' likely questions (1:00 Q&A)

- **What is real?** Our app, login/RBAC, invoice rules, supplier onboarding, receipts and tests. **What is mocked?** AVS and payment events. No live bank connectivity.
- **What changed during HackSecure?** Explain and show the team's actual commits and work only; be transparent about any AI-assisted or pre-existing code.
- **Can attackers steal information?** No system is invulnerable. Show tenant-isolation denial, server-side role controls, masked account storage and secure-session protections. Explain remaining production blockers.
- **How do you know money arrived?** We don't, today; the demo is a simulation. A real provider-authenticated status feed is required.
- **What about WhatsApp?** We've intentionally moved to a dedicated web application to better control authenticated access and security workflows.

## Reliable backup

Before judging run `python -m pytest -q`; if browser fails, use `python -m scripts.demo_scenarios`. Do not present scripted console output as proof of a live banking integration.
