# Personal Finance Tracker

An automated pipeline that transforms raw bank statement PDFs into structured, categorised transaction data — ready for analysis in Google Sheets.

Built for Singapore-based banking (DBS, UOB, Citi), with SGD as the base currency.

---

## How It Works

The pipeline runs in three stages:

```
Bank Statement PDFs
        │
        ▼
┌─────────────────────┐
│  1. PDF Scrubber    │  clean_bank_statement.py
│  Extract + Redact   │  Strips PII, detects bank/type/date
└────────┬────────────┘
         │  Processed JSON
         ▼
┌─────────────────────┐
│  2. Gemini Bridge   │  gemini_to_csv.py
│  Categorise & Parse │  LLM extracts and labels transactions
└────────┬────────────┘
         │  Structured CSV
         ▼
┌─────────────────────┐
│  3. n8n Webhook     │  run_batch.py → localhost:5678
│  Push to Sheets     │  Sends CSV payload to Google Sheets
└─────────────────────┘
```

### Stage 1 — PDF Scrubber (`clean_bank_statement.py`)

Reads a bank statement PDF and:
- Extracts raw text using `pypdf`
- Redacts PII (name, NRIC, account numbers, address) using patterns from `.env`
- Auto-detects the bank name (DBS, UOB, Citi, OCBC, etc.), document type (Account or CreditCard), and statement date from the text
- Outputs a clean JSON file named using the pattern `Processed_YYMM_Bank_DocType.json`

Can be run manually (file picker dialog) or headlessly with a file path argument.

### Stage 2 — Gemini Bridge (`gemini_to_csv.py`)

Takes the scrubbed JSON and sends it to Google Gemini with a structured prompt that instructs the model to:
- Extract every transaction
- Classify each as **Expense**, **Income**, or **Transfer**
- Assign a category (Transport, Food, Groceries, Shopping, Subscriptions, Bills, Insurance, Travel, Transfer, Income, General)
- Output SGD amounts only (handles FX conversion lines)
- Format dates as YYYY-MM-DD

Output CSV columns: `Date, Description, Type, Category, Amount, Account, Original Description`

### Stage 3 — Batch Runner + n8n (`run_batch.py` + `n8n Finance.command`)

`run_batch.py` orchestrates the full pipeline:
1. Scans the `Input/` folder for PDFs
2. Runs the scrubber on each file
3. Runs the Gemini bridge on each resulting JSON
4. POSTs the CSV content to a local n8n webhook
5. Archives the original PDF to `Archive/`

`n8n Finance.command` is the macOS launcher — double-click to run the batch processor from Finder. The n8n workflow (running locally on port 5678) receives the CSV payload and appends rows to Google Sheets.

---

## Folder Structure

```
Finance/
├── Scripts/
│   ├── clean_bank_statement.py   # Stage 1: PDF extraction + PII scrubbing
│   ├── gemini_to_csv.py          # Stage 2: Gemini categorisation → CSV
│   └── run_batch.py              # Stage 3: Batch orchestrator + n8n dispatch
├── Input/                        # Drop new PDFs here to process (gitignored)
├── Processed/                    # Intermediate scrubbed JSON files (gitignored)
├── Processed CSVs/               # Final categorised CSVs (gitignored)
├── Archive/                      # PDFs moved here after processing (gitignored)
├── n8n Finance.command           # macOS double-click launcher
├── .env                          # API keys and sensitive data (gitignored)
└── .env.example                  # Template for required environment variables
```

---

## Setup

### Prerequisites
- Python 3.12
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)
- [n8n](https://n8n.io/) running locally on port 5678 with a webhook configured to receive CSV payloads and write to Google Sheets

### Installation

```bash
# Install dependencies
pip install pypdf python-dotenv google-genai requests

# Copy the environment template and fill in your values
cp .env.example .env
```

### Configuration

Edit `.env` with your details:

```
GEMINI_API_KEY=your_key_here
SENSITIVE_DATA=Your Name,YourNRIC,PartialAccountNumber
```

`SENSITIVE_DATA` accepts a comma-separated list of any strings you want redacted from statement text before it leaves your machine. Be thorough — include name variations, partial account numbers, and address fragments.

The n8n webhook URL is hardcoded in `run_batch.py` as `http://localhost:5678/webhook/bank-statement`. If you're adapting this for your own setup, update that URL to match your n8n instance and webhook path.

---

## Usage

### Batch Mode (recommended)

1. Drop one or more bank statement PDFs into the `Input/` folder
2. Double-click `n8n Finance.command` (macOS) or run:
   ```bash
   python3.12 Scripts/run_batch.py
   ```
3. Processed CSVs are sent to n8n and PDFs are archived automatically

### Manual Mode

Run each script individually with a file picker:
```bash
python3.12 Scripts/clean_bank_statement.py   # Select PDF → outputs JSON
python3.12 Scripts/gemini_to_csv.py          # Select JSON → outputs CSV
```

---

## Supported Banks

| Bank | Account | Credit Card |
|------|---------|-------------|
| DBS / POSB | ✅ | ✅ |
| UOB | ✅ | ✅ |
| Citi | — | ✅ |
| OCBC | ✅ | ✅ |
| HSBC | ✅ | ✅ |
| Standard Chartered | ✅ | ✅ |

> Detection is text-based. Accuracy depends on the PDF being machine-readable (not scanned images).

---

## Roadmap

- [ ] Merchant-to-category override mapping for consistent categorisation
- [ ] Processing log for audit trail
- [ ] Interactive spending dashboard
- [ ] Support for CPF statements and IBKR investment reports

---

## Privacy

All PII scrubbing happens **locally on your machine** before any data is sent to an external API. The Gemini API only ever sees redacted text. API keys and sensitive terms are stored in `.env` which is gitignored and never committed.
