# FraudFence SA — Blank Invoice Form Fix

This update is for the existing `FraudFence-SA-Owner-Review-Invoice-Upload-Complete` project.

## What changes
- The invoice number, amount, account number, and supplier selection start blank in both `/` and `/quick`.
- The `/quick` company registration and legal-name fields also start blank.
- Selecting a different invoice immediately clears all previous invoice values, past check result, and review tick.
- Clicking **Extract invoice details** extracts values from the newly uploaded document. Any missing or ambiguous value remains blank; the user must verify and, if necessary, correct the extracted value manually.
- A failed extraction leaves the fields blank. An older extraction request cannot fill the form after a new file is selected.
- The invoice cannot be verified without extracting a selected file and checking the review checkbox.
- `invoice_extraction.py` also suggests a clearly labelled supplier legal name when unambiguous. This is an untrusted DOCUMENT CLAIM, not evidence of CIPC registration or supplier legitimacy.
- No changes to payment/owner review features.

## Easiest update (Windows PowerShell)

**First download** `FraudFence-SA-Blank-Invoice-Form-Update.zip` to Downloads from ChatGPT. Then:

```powershell
$project = "$HOME\OneDrive\Documents\FraudFence-SA-Owner-Review-Invoice-Upload-Complete"
$zip = "$HOME\Downloads\FraudFence-SA-Blank-Invoice-Form-Update.zip"
Test-Path $zip
Test-Path "$project\requirements.txt"
Expand-Archive -LiteralPath $zip -DestinationPath $project -Force
```

Both Test-Path commands must print True before the extraction command. If either says False, locate your downloaded ZIP or original project folder first.

Restart FastAPI if running (Ctrl+C in its terminal), run:

```powershell
cd $project
.\.venv\Scripts\python.exe -m uvicorn fraudfence.main:app --reload --port 8001
```

Open `http://127.0.0.1:8001` or `http://127.0.0.1:8001/quick`, then press `Ctrl+Shift+R` for a full browser refresh.

## Test
1. Open the invoice page: all invoice inputs should be blank; review box not checked.
2. Upload `02_BUILDRITE_CHANGED_ACCOUNT.pdf` and click **Extract invoice details**; amount/account/reference populate.
3. Select a different invoice file; all previous invoice fields and review tick clear immediately.
4. Upload an invoice with no account or two conflicting account numbers; the account input stays blank for manual review.
5. Verify only after selecting the saved supplier and confirming against the original invoice.

All test data and providers in this demo are fictional. Uploading and parsing an invoice does not authenticate it.
