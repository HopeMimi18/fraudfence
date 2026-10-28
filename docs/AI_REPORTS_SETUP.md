# FraudFence SA — AI Fraud Reports (HackSecure demo)

## Scope and what the feature truly does

AI is an **explanation/report-writing assistant**, not a bank verifier, payment checker, supplier verifier or final decision-maker. The existing deterministic Trust Engine must first decide `STOP_CHANGED_ACCOUNT`, `HOLD_*`, `UNVERIFIED`, etc. Then a model explains those results and proposes practical questions/actions.

**Real model supported:** Local Ollama (`llama3.2:3b`) or OpenAI's Responses API (`gpt-4.1-mini` by default). **No live LLM request has been completed in this package:** to execute real AI, run the local model or supply your own API credentials. All integration tests use mocked model responses. **No AI provider configured = clearly labelled rules-only report**; it is never called AI-generated.

**No model can upgrade a status, make an approval, or inject a payment.** The official decision and required next steps are computed and rendered separately from the AI paragraph. Reports are returned to the current authenticated user, with a signed receipt that records the report's SHA-256 hash, case type and source reference. The full report is *not stored* in the database; download it from the UI to retain it.

## Fastest REAL AI demo — local Ollama (no account or API secret)

1. Install Ollama for Windows from https://ollama.com/download/windows and launch it.
2. In **one PowerShell window**, run `ollama pull llama3.2:3b` (downloads the model once). Then `ollama list` to confirm it's installed. Most Windows installations start the Ollama service automatically; if not, run `ollama serve` in a separate terminal.
3. Run `ollama run llama3.2:3b "Summarise why a fake payment screenshot is not payment proof."` **once before pitching** to warm the model.
4. In **a fresh PowerShell window** in your extracted FraudFence project folder, set:

   ```powershell
   $env:FF_AI_PROVIDER = "ollama"
   $env:FF_AI_MODEL = "llama3.2:3b"
   .\.venv\Scripts\python.exe -m scripts.seed_pitch
   .\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload
   ```

5. Open `http://127.0.0.1:8000`, log in as the demo owner, use **Invoice check** then **AI reports** (the receipt ID fills automatically). Alternatively, open `http://127.0.0.1:8000/pitch`, run **STOP supplier payment**, then **★ AI invoice report**.
6. Verify the report's label is `REAL_AI_MODEL` (not `RULE_BASED_REPORT_NO_AI`). If Ollama cannot be reached or times out, the system deliberately shows rules-only fallback.

The model runs on the laptop at `127.0.0.1:11434` and does not require CIPC, Ozow, Meta or internet *after download*.

## Alternative — OpenAI API

OpenAI API use requires an API key and separately billed API access; a ChatGPT subscription is not an API key. Set keys *only in the same PowerShell session used to launch Uvicorn*, not in repository files or screenshots:

```powershell
$env:FF_AI_PROVIDER = "openai"
$env:FF_AI_MODEL = "gpt-4.1-mini"
$env:OPENAI_API_KEY = "<your privately created API key>"
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload
```

The code uses `POST https://api.openai.com/v1/responses` with `store:false` and a fixed HTTPS destination. Sending data to any third-party AI still requires a privacy/operator assessment and permission before real-world use. Do **not** put actual customer or supplier information into this hackathon build.

## Evidence and data minimisation

To the model, FraudFence sends **only allowlisted status fields** like:

```json
{"case_type":"supplier_invoice","decision":"STOP_CHANGED_ACCOUNT","registry_evidence":"MOCK_MATCH","avs_evidence":"MOCK_ONLY","supplier_state":"DEMO_VERIFIED","sender_authentication":"NOT_CHECKED","warning_count":1,"is_demo":true}
```

It **does not send** raw invoice text, image pixels, full banking details, company names, phone numbers, logins, API secrets, personally identifying contacts, or payment screenshots. Both the model prompt and report clearly distinguish mocked providers from real provider evidence. Risk indicators aren't guaranteed fraud findings.

Reports require a same-business authenticated session and CSRF token. Invoice reports are limited to owners/bookkeepers; payment reports to owners/cashiers. The invoice source must be an intact signed receipt and valid audit chain. Obvious contradictory model advice is rejected, but automated content filtering is imperfect; the fixed system verdict always remains authoritative.

## Endpoints

- `GET /api/ai/status` — provider presence/status (authenticated).
- `POST /api/ai/reports/invoice` — body `{"receipt_id":"<existing valid invoice receipt>"}`.
- `POST /api/ai/reports/payment` — body `{"sale_id":"<your business's sale id>"}`.

All POSTs require a logged-in session and `X-CSRF-Token`. The interface provides these automatically.

## Presenter script (20 seconds)

> “Our Trust Engine first refuses the changed supplier account. Then our AI Analyst turns the verified system evidence into an understandable incident report—what was detected, why it matters and what the owner should do. The model never receives complete bank details or raw attacker-controlled invoices, and it cannot approve a payment. We can show the real AI narrative running locally on the laptop.”

**Only use the last sentence if the report says `REAL_AI_MODEL`.** If not, say “The report workflow is integrated; this run uses our evidence-only fallback until a model is available.”

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_reports.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_api.py tests/test_external_integrations.py tests/test_notifications.py tests/test_pitch_mode.py
```

The combined project has 68 tests across two groups (11 AI report tests + 57 pre-existing tests). All test provider responses are synthetic. Tests do not establish that a production provider has accepted a request or that AI output is guaranteed accurate.
