from datetime import datetime
from typing import List, Tuple
from src.core.schema import InvoiceData


def validate_invoice_data(data: InvoiceData) -> Tuple[bool, List[str]]:
    """Validates extracted invoice data using strict deterministic logic."""
    errors: List[str] = []

    # 1. Mandatory Fields
    if not data.invoice_number:
        errors.append("Missing required field: 'invoice_number'.")

    if not data.vendor_name:
        errors.append("Missing required field: 'vendor_name'.")

    if data.total_amount <= 0:
        errors.append(f"Invalid total_amount: {data.total_amount}. Must be greater than 0.")

    # 2. Line Items Sum vs Subtotal
    if data.line_items:
        items_sum = sum(item.amount for item in data.line_items)
        if round(items_sum, 2) != round(data.subtotal, 2):
            errors.append(
                f"Line items sum ({round(items_sum, 2)}) does not match subtotal ({round(data.subtotal, 2)})."
            )

    # 3. Overall Financial Arithmetic Check
    # Formula: Subtotal - Discount + Tax + Shipping = Total Amount
    subtotal = data.subtotal or 0.0
    discount = data.discount_amount or 0.0
    tax = data.tax_amount or 0.0
    shipping = data.shipping_amount or 0.0

    calculated_total = round(subtotal - discount + tax + shipping, 2)
    actual_total = round(data.total_amount, 2)

    if calculated_total != actual_total:
        errors.append(
            f"Financial math mismatch: Subtotal ({subtotal}) - Discount ({discount}) "
            f"+ Tax ({tax}) + Shipping ({shipping}) = {calculated_total:.2f}, "
            f"but total_amount is {actual_total:.2f}."
        )

    # 4. Date Logic Check
    if data.invoice_date and data.due_date:
        try:
            inv_date = datetime.strptime(data.invoice_date, "%Y-%m-%d")
            due_dt = datetime.strptime(data.due_date, "%Y-%m-%d")
            if due_dt < inv_date:
                errors.append(
                    f"Due date ({data.due_date}) cannot be earlier than invoice date ({data.invoice_date})."
                )
        except ValueError:
            errors.append("Date format mismatch. Dates must be in YYYY-MM-DD format.")

    is_valid = len(errors) == 0
    return is_valid, errors


if __name__ == "__main__":
    # Test validation using extract.py on the sample PDF
    from src.core.extract import extract_invoice_data

    sample_pdf = "samples/sample_invoice.pdf"
    print(f"--- Running Validation Test on {sample_pdf} ---")

    try:
        extracted_data = extract_invoice_data(sample_pdf)
        is_valid, validation_errors = validate_invoice_data(extracted_data)

        if is_valid:
            print("\n✓ Validation PASSED! All financial and logical rules satisfied.")
        else:
            print("\n✗ Validation FAILED with the following errors:")
            for err in validation_errors:
                print(f"  - {err}")

    except Exception as e:
        print(f"\n✗ Error running validation test: {e}")