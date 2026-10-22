# AI Invoice Processor Agent

An automated, agentic invoice processing pipeline powered by Google Document AI, Gemini 3.5 Flash, and LangGraph. The pipeline ingests PDF invoices, extracts structured financial data, runs validation checks, logs entries to Google Sheets, and dispatches automated summary emails via the Gmail API.

---

## 🏗️ Architecture & Workflow

```
[PDF Input] ──> [Node 1: Extract (Document AI + Gemini)]
                       │
                       ▼
             [Node 2: Validate] ────(Validation Failed & Retries < MAX)──┐
                       │                                                 │
            (Validation Passed)                                 (Retry Loop)
                       │                                                 │
                       ├───> [Node 3: Save to Google Sheets] <──────────┘
                       │
                       └───> [Node 4: Send Summary Email via Gmail]
                       │
              (Out of Retries)
                       │
                       ▼
             [Node 5: Needs Review Sheet]
```

### Pipeline Nodes Breakdown

1. **Extract Node (`src/core/extract.py`)**: Uses Google Document AI to run OCR on input invoice PDFs, then prompts `gemini-3.5-flash` with strict structured output schema (`InvoiceData`) to parse fields cleanly.
2. **Validate Node (`src/core/validate.py`)**: Executes deterministic financial arithmetic logic (`Subtotal - Discount + Tax + Shipping = Total Amount`), line items sum verification, required fields presence, and chronological date rules (`Invoice Date <= Due Date`).
3. **Save to Sheet Node (`src/integrations/sheets.py`)**: Authenticates via `gspread` and appends validated invoice data to the primary `Invoices` sheet tab, enforcing duplicate prevention across vendor names and invoice numbers.
4. **Send Summary Node (`src/integrations/email_service.py`)**: Formats an HTML summary table with extracted totals and dispatches an automated notification email attached with the original PDF via Gmail API.
5. **Needs Review Node**: Handles unreadable files or persistently failing validation attempts, logging error details directly to the `Needs Review` sheet tab for human inspection.

---

## 🚀 Quickstart Guide

### 1. Project Setup

```powershell
# Clone repository
git clone <your-repo-url>
cd "Invoice Processor Agent"

# Synchronize dependencies with uv
uv sync
```

### 2. Environment Configuration

Place your Google Cloud OAuth credentials and set up your `.env` file inside `secrets/`:

```env
GEMINI_API_KEY="your_gemini_api_key"
GEMINI_MODEL_NAME="gemini-3.5-flash"
SHEET_ID="your_google_sheet_id"
RECIPIENT_EMAIL="your_email@gmail.com"
```

Required secret files inside `secrets/`:
* `credentials.json` (Google Cloud OAuth Client ID)
* `authorized_user.json` / `gmail_token.json` (Saved OAuth tokens)

### 3. Running the Pipeline

To run the LangGraph invoice pipeline on a sample invoice:

```powershell
uv run python -m src.core.graph samples/sample_invoice.pdf
```

---

## 🧪 Evaluation & Testing

The project includes an end-to-end evaluation suite that measures live model extraction accuracy, financial validation rules, latency, API costs, and string edit distance metrics.

Run the test suite via `pytest`:

```powershell
uv run python -m pytest tests/test_pipeline.py -s
```

---

## 🐳 Docker Deployment

Build and run the agent container with `uv`:

```powershell
# Build Docker image
docker build -t invoice-processor .

# Run Docker container with secrets mounted
docker run --rm --env-file secrets/.env -v ${PWD}/secrets:/app/secrets invoice-processor
```

---

## 🛠️ Tech Stack

* **Workflow Engine**: LangGraph & LangChain
* **AI & Vision**: Gemini 3.5 Flash (`google-genai`), Google Document AI
* **Data Validation**: Pydantic v2
* **Integrations**: Google Sheets API (`gspread`), Gmail API (`google-api-python-client`)
* **Environment & Build**: `uv`, Docker, `pytest`