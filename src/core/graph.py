import os
import sys
from typing import Literal
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph, START

from config.settings import RECIPIENT_EMAIL
from src.core.extract import extract_invoice_data
from src.core.schema import InvoiceData
from src.core.state import InvoiceState
from src.core.validate import validate_invoice_data
from src.integrations.email_service import send_invoice_summary_email
from src.integrations.sheets import append_valid_invoice, append_needs_review

load_dotenv()

MAX_RETRIES = 2


# --- NODES ---
def extract_node(state: InvoiceState) -> dict:
    """Node 1: Extract structured invoice data with Gemini."""
    attempt = state.get("retries", 0) + 1
    print(f"\n[Node: Extract] Processing: {state['file_path']} (Attempt {attempt})")
    try:
        invoice = extract_invoice_data(
            pdf_path=state["file_path"],
            validation_errors=state.get("errors", []),
        )
        return {"invoice_data": invoice}
    except Exception as e:
        print(f"✗ Extraction Exception: {str(e)}")
        return {
            "invoice_data": None,
            "errors": [f"Extraction Error: {str(e)}"],
        }


def validate_node(state: InvoiceState) -> dict:
    """Node 2: Validate fields, formats, and financial totals."""
    print("[Node: Validate] Running financial and logic checks...")
    if not state.get("invoice_data"):
        return {
            "status": "failed",
            "errors": state.get("errors", ["No invoice data extracted."]),
            "retries": state["retries"] + 1,
        }

    is_valid, errors = validate_invoice_data(state["invoice_data"])

    if is_valid:
        print("✓ Validation Succeeded!")
        return {
            "errors": [],
            "status": "valid",
        }
    else:
        print(f"✗ Validation Failed: {errors}")
        return {
            "errors": errors,
            "retries": state["retries"] + 1,
            "status": "failed",
        }


def save_to_sheet_node(state: InvoiceState) -> dict:
    """Node 3: Append validated invoice row to Google Sheets."""
    print("[Node: Save to Sheet] Saving row to Google Sheets...")
    if state.get("invoice_data"):
        success, msg = append_valid_invoice(state["invoice_data"], state["file_path"])
        if success:
            print(f"✓ [Saved] {msg}")
        else:
            print(f"⚠ [Sheets Log] {msg}")
    return {"status": "saved"}


def send_summary_node(state: InvoiceState) -> dict:
    """Node 4: Send summary email via Gmail API with original file attached."""
    print("[Node: Send Summary] Sending email summary via Gmail API...")
    if state.get("invoice_data"):
        send_invoice_summary_email(state["invoice_data"], state["file_path"])
    return {"status": "completed"}


def needs_review_node(state: InvoiceState) -> dict:
    """Node 5: Route unreadable or invalid invoices to 'Needs Review' sheet tab."""
    print(f"[Node: Needs Review] Out of retries. Logging to 'Needs Review' tab...")
    append_needs_review(state["file_path"], state.get("errors", []))
    reasons = "; ".join(state["errors"]) if state.get("errors") else "Unreadable file"
    print(f"✗ Route: Needs Review -> {state['file_path']}")
    print(f"  Reason(s): {reasons}")
    return {"status": "needs_review"}


# --- CONDITIONAL ROUTER ---
def route_after_validation(
    state: InvoiceState,
) -> Literal["save_to_sheet", "extract", "needs_review"]:
    """Decides next node based on validation output and remaining retry count."""
    if state["status"] == "valid":
        return "save_to_sheet"

    if state["retries"] <= MAX_RETRIES:
        print(
            f"--> Decision: Validation failed. Retrying extraction (Retry {state['retries']}/{MAX_RETRIES})..."
        )
        return "extract"

    print("--> Decision: Out of retries. Routing to Needs Review...")
    return "needs_review"


# --- BUILD WORKFLOW GRAPH ---
workflow = StateGraph(InvoiceState)

# Add 5 Nodes
workflow.add_node("extract", extract_node)
workflow.add_node("validate", validate_node)
workflow.add_node("save_to_sheet", save_to_sheet_node)
workflow.add_node("send_summary", send_summary_node)
workflow.add_node("needs_review", needs_review_node)

# Add Standard Edges
workflow.add_edge(START, "extract")
workflow.add_edge("extract", "validate")
workflow.add_edge("save_to_sheet", "send_summary")
workflow.add_edge("send_summary", END)
workflow.add_edge("needs_review", END)

# Add Conditional Routing Edge
workflow.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "save_to_sheet": "save_to_sheet",
        "extract": "extract",
        "needs_review": "needs_review",
    },
)

# Compile LangGraph Application
app = workflow.compile()


# --- CLI ENTRYPOINT ---
if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "samples/sample_invoice.pdf"

    initial_state: InvoiceState = {
        "file_path": target_file,
        "invoice_data": None,
        "errors": [],
        "retries": 0,
        "status": "pending",
    }

    print(f"--- Initiating Pipeline for: {target_file} ---")
    final_state = app.invoke(initial_state)
    print(f"\n--- Pipeline Finished with Status: {final_state['status']} ---")