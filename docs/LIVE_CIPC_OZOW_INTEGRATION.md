# FraudFence SA — CIPC and Ozow staging connection guide

**Status:** Actual HTTP client code is implemented and tested against fake HTTP servers. **No account-specific live CIPC or Ozow transaction has been performed**: provider credentials are required.

## CIPC APIVerse
1. Register at https://developer.cipc.co.za/ and subscribe to **Authorisation API** and the appropriate **Companies API**.
2. Inspect the exact token URL, subscribed company-lookup URL, request parameter, subscription-key requirement, OAuth authentication method, allowed hostnames, and response JSON schema in YOUR portal. The public landing pages do not document all values.
3. Set the `FF_CIPC_*` environment variables from `.env.example` **in your terminal/secret manager**, not in Git or ChatGPT. This application intentionally refuses unconfigured/unknown endpoints.
4. Sign in as an owner or bookkeeper. In the local Swagger UI (`/docs`), invoke `POST /api/suppliers/{sid}/cipc-api-check`. It only uses the supplier's stored independently established registration number; no customer-supplied URL.
5. Review the `verdict`. If the subscribed API's field names differ from `registrationNumber` / `enterpriseNumber`, `enterpriseName` / `registeredName`, and `enterpriseStatus` / `status`, it returns `UNMAPPED_CIPC_SCHEMA` rather than falsely approving. Modify the mapping only after reviewing the authorised schema.
6. Even if the CIPC data match, the supplier is NOT marked live-verified: live AVS and an independently sourced callback are still necessary.

## Ozow — One API staging (NOT deprecated Payments API)
1. Contact **support@ozow.com**, requesting **One API staging client ID, client secret and site code**; the official docs say staging credentials for no-money tests are available on request.
2. Supply a public HTTPS `FF_OZOW_RETURN_URL` (for local development use an authorised HTTPS tunnel). This is only a redirect landing page, not payment evidence.
3. Set the four `FF_OZOW_*` variables as local OS environment variables. Never commit secrets or configure production credentials in this staging-only app.
4. Run the FastAPI app. Log in as owner or cashier, create a sale using `POST /api/sales` in `/docs`.
5. Call `POST /api/sales/{sale_id}/ozow-staging/start`. The backend obtains OAuth token and creates a **real Ozow staging payment request**; the response contains an Ozow staging checkout URL.
6. Complete a staging test payment in Ozow's test checkout. The browser redirect is **not trusted**.
7. Call `POST /api/sales/{sale_id}/ozow-staging/check`. This requests `GET /payments/{id}/transactions` from authenticated Ozow staging One API, and checks transaction status `Successful` PLUS merchant reference, exact ZAR amount, site code and unique transaction ID.
8. Expected outcomes: `OZOW_STAGING_PROVIDER_CONFIRMED` only on a unique exact matching successful test transaction; `OZOW_STAGING_PENDING` before confirmation; `HOLD_PROVIDER_MISMATCH`, `HOLD_MULTIPLE_SUCCESSFUL_TRANSACTIONS`, `HOLD_REFUNDED` or `OZOW_STAGING_NOT_PAID` otherwise. Every check creates a signed audit receipt.

This uses authenticated **server-side polling**, not a webhook, so your HTTP server does not need public webhook access; Ozow still requires a public HTTPS return URL. Future webhooks must validate signatures and be idempotent.

## Testing
Run `python -m pytest -q`. The integration tests use `httpx.MockTransport` and exercise the **actual HTTP adapter code**, but with synthetic provider responses. This is not proof that external accounts are configured.

## Sources
- https://developer.cipc.co.za/
- https://hub.ozow.com/api-reference/
- https://hub.ozow.com/getting-started/quick-start/
- https://hub.ozow.com/api-reference/one-api/get-payments-id-transactions/

## Security / limitations
No live money is moved. Do NOT claim bank settlement when Ozow staging returns `Successful`. The app remains a prototype; live banking operations and personal data should not be handled until further security hardening and validation. The CIPC client needs schema validation against the specific API subscription.
