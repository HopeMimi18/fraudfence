# FraudFence — Owner Payment Review and Invoice Autofill

**HackSecure demo update • Team FORGE • 28 October 2026**

## What changed

- **Cashier:** Logs an R850 sale and taps **Request owner verification**. The sale changes to `PENDING_OWNER_REVIEW`. Cashiers cannot record an owner decision, and the owner banking balance/credentials are not exposed to cashiers.
- **Owner:** Signs into the owner account, finds the pending sale under **Payment check**, opens their **actual receiving bank app independently**, checks the *exact* reference and amount, then chooses **I found the payment** or **Not received / cannot confirm**. Re-entering the owner account password is required. The decision is recorded with an audit event; the cashier taps **Refresh** to see it.
- **Statuses:** `OWNER_ATTESTED_NOT_BANK_VERIFIED` for manual owner confirmation, `OWNER_REPORTED_NOT_RECEIVED` for an unsuccessful owner check. These are never labelled independent bank verification. A pending transaction does not justify releasing goods. Normal store fulfilment policy must consider reversals and other risks.
- **Invoice:** From the existing Invoice check tab or Lite `/quick`, upload a **PDF, PNG or JPEG**, up to **4 MB**, and the app suggests invoice number, amount and banking account. Human approval checkbox is mandatory; a record chosen from the *saved supplier list* is needed to run the actual mismatch check.
- **Privacy:** The upload is processed in memory; the source file and its raw OCR text are **not persisted**. The audit contains only extraction method and extracted field **names**. The application does not send invoice text to a model or outside OCR API. An image may need Tesseract installed locally.

## Install the update over the previous FraudFence Lite project (Windows PowerShell)

1. Stop `uvicorn` with **Ctrl+C**. Back up the existing folder first.
2. Copy the downloaded `FraudFence-SA-Owner-Review-Invoice-Upload-Update.zip` into Downloads and run:

```powershell
cd "$HOME\OneDrive\Desktop\fraudfence-lite"
Expand-Archive -LiteralPath "$HOME\Downloads\FraudFence-SA-Owner-Review-Invoice-Upload-Update.zip" -DestinationPath . -Force
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload --port 8001
```

The database is migrated on startup; the update ZIP does **not** overwrite your DB, keys, `.env`, or `.git` repository. If you prefer, unzip the **Complete** package into a new folder, create a Python virtual environment, install requirements and seed synthetic data using `python -m scripts.seed_demo`.

## Demonstrate the two improvements

**Invoice:** Log in as `demo-owner@fraudfence.test` using the original demo password. Open **Invoice check** and upload `docs/DEMO_INVOICE_INV-2207.pdf`. Confirm it suggests `INV-2207`, `R18,400.00`, and account `0009998877`. Choose **BuildRite** from the existing supplier dropdown, **inspect the PDF**, tick the checkbox and click **Run verification**. Expected: `STOP_CHANGED_ACCOUNT` because the supplier's demo account differs. CIPC and AVS are fictional, not live provider checks.

**Payment:** Log in as `demo-cashier@fraudfence.test`. Open **Payment check**, log a new sale `SALE-2026-10` for **R850** and tap **Request owner verification** on the sale. Log out; log in as the demo owner. Go to **Payment check**, select **Review bank payment**, confirm with the demo-only attestation and password. You can also choose **Not received** for the adverse case. Switch back to the cashier and refresh. The status reflects the owner's decision; **FraudFence has not connected to the bank**. The owner should never attest to a real payment without actually checking the receiving bank app.

The same interactions appear in the simpler `/quick` page. On that page the owner sees pending review requests after tapping **Refresh review queue**.

## OCR setup (optional)

Text PDFs are handled by `pypdf`, without a separate OCR executable. PNG/JPEG files require **Tesseract OCR** installed locally with its executable on PATH or in the standard Windows location `C:\Program Files\Tesseract-OCR\tesseract.exe` (or set environment variable `TESSERACT_CMD` to the full executable path). For scanned PDFs, also install optional PyMuPDF:

```powershell
.\.venv\Scripts\python.exe -m pip install pymupdf
```

OCR is not flawless. Handwritten text, poor image quality and multiple candidate account numbers may fail. The app deliberately leaves ambiguous fields unfilled. **Never automatically approve supplier identity or bank changes based only on extracted invoice text.** Do not upload real private invoices to this demo.

## Operational and security boundaries

- Existing live Ozow and CIPC integrations are **not configured**; successful demo matches remain fictional. The owner manually checking a bank app is an accountable attestation, not independent bank evidence.
- For production, use encrypted storage, managed secrets, robust antivirus/content scanning, isolated file processing, additional step-up authentication and provider-backed payment reconciliation.
- The current owner notification inbox is a **simulated WhatsApp-style preview**. It does not send real WhatsApp notifications. The cashier/owner status updates are visible inside the signed-in application after refresh.
- The AI reports component remains separate: it explains a previous evidence-backed status using Ollama/API only when connected. Invoice extraction itself currently uses deterministic text parsing and local OCR, **not a generative AI model**.
