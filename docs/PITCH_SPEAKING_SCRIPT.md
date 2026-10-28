# FraudFence SA — under-five-minute speaker notes

**Scene 1 — The problem**

“Imagine Mokoena Hardware receives an urgent invoice from its regular supplier. The invoice says ‘bank details changed’, and R18,400 must go to a new account. At the counter, a customer also shows a screenshot claiming an R850 payment. In both cases the business could lose money or goods by trusting unverified information.”

**Scene 2 — Our solution**

“FraudFence remembers a fingerprint of the trusted bank account, not the complete number. The changed invoice fails the comparison. To establish supplier identity, our design requires three sources to agree: CIPC, bank AVS and a callback to an independently established contact. We run this scenario on fictional provider results: recent registry change, AVS mismatch and a denied callback. The supplier change stays on HOLD, with a signed evidence receipt. For the cashier, a screenshot alone keeps the R850 sale UNVERIFIED. WhatsApp can alert people but cannot confirm funds.”

**Scene 3 — Try to break FraudFence**

“Now we attack ourselves. A malicious chat request to approve a new bank account is refused. Our backend only allows the owner to approve, and tests confirm a bookkeeper gets a 403. We minimise the stored bank information to a keyed HMAC fingerprint and the last four digits. Cross-business queries are restricted, and an altered audit record is detectable by its hash chain. These are implemented prototype controls, not a claim that the system is unhackable. Additional encryption, key isolation, MFA and independent security testing are required for production.”

**Close**

“We've tested our local security rules with automated tests; live CIPC and payment-provider access is still pending. We propose subscriptions from R199 a month: 100 customers would mean R19,900 gross monthly revenue, before costs. FraudFence SA: check before you pay.”
