import time
import pytest
from pathlib import Path

from src.core.extract import extract_invoice_data
from src.core.schema import InvoiceData, LineItem
from src.core.validate import validate_invoice_data
from tests.eval_metrics import InvoiceEvaluator


# --- UNIT TESTS ---

def test_pydantic_schema_structure():
    """Unit test for schema defaults and validation constraints."""
    item = LineItem(description="Software Subscription", quantity=1.0, unit_price=100.0, amount=100.0)
    assert item.amount == 100.0

    invoice = InvoiceData(invoice_number="INV-001", vendor_name="Vendor Inc", total_amount=100.0)
    assert invoice.currency == "INR"
    assert invoice.subtotal == 0.0


def test_validation_logic_success():
    """Unit test for validation arithmetic pass."""
    invoice = InvoiceData(
        invoice_number="INV-100",
        vendor_name="Test Corp",
        subtotal=100.0,
        tax_amount=10.0,
        discount_amount=0.0,
        shipping_amount=0.0,
        total_amount=110.0,
    )
    is_valid, errors = validate_invoice_data(invoice)
    assert is_valid is True
    assert len(errors) == 0


def test_validation_logic_financial_mismatch():
    """Unit test catching corrupted invoice total."""
    invoice = InvoiceData(
        invoice_number="INV-100",
        vendor_name="Test Corp",
        subtotal=100.0,
        tax_amount=10.0,
        total_amount=500.0,  # Math error
    )
    is_valid, errors = validate_invoice_data(invoice)
    assert is_valid is False
    assert any("Financial math mismatch" in err for err in errors)


# --- LIVE INTEGRATION EVALUATION TEST ---

def test_live_pipeline_metrics():
    """Runs live model extraction on samples/sample_invoice.pdf and evaluates all 14 metrics."""
    pdf_path = Path("samples/sample_invoice.pdf")
    assert pdf_path.exists(), "samples/sample_invoice.pdf must exist for live testing"

    ground_truth = {
        "vendor_name": "ACME SUPPLIES LTD.",
        "invoice_number": "INV-1042",
        "invoice_date": "2025-01-15",
        "due_date": "2025-02-15",
        "total_amount": "115.0",
        "subtotal": "100.0",
        "tax_amount": "10.0",
        "currency": "INR",
    }

    evaluator = InvoiceEvaluator()

    start_time = time.time()
    is_failure = False
    extracted_dict = {}

    try:
        extracted_data = extract_invoice_data(str(pdf_path))
        latency = time.time() - start_time
        extracted_dict = extracted_data.model_dump()
    except Exception as e:
        latency = time.time() - start_time
        is_failure = True
        print(f"\n[Extraction Failure]: {e}")

    metrics = evaluator.evaluate([ground_truth], [extracted_dict], [latency], [is_failure])

    print("\n\n================ LIVE EVALUATION METRICS ================")
    for metric_name, score in metrics.items():
        print(f"  {metric_name:<30}: {score}")
    print("=========================================================\n")

    assert metrics["12_processing_failure_rate"] == 0.0, "Pipeline failed during live processing"
    assert metrics["1_field_level_accuracy"] > 0.7, "Accuracy below acceptable threshold"