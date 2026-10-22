import os
from typing import List, Tuple
import gspread
from google.oauth2.service_account import Credentials

from config.settings import SECRETS_DIR, SHEET_ID
from src.core.schema import InvoiceData

# Required API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SERVICE_ACCOUNT_PATH = SECRETS_DIR / "service_account.json"
OAUTH_CREDENTIALS_PATH = SECRETS_DIR / "credentials.json"
AUTHORIZED_USER_PATH = SECRETS_DIR / "authorized_user.json"


def get_gspread_client() -> gspread.Client:
    """
    Authenticates gspread client using Service Account if available,
    otherwise falls back to OAuth Desktop credentials.
    """
    if SERVICE_ACCOUNT_PATH.exists():
        creds = Credentials.from_service_account_file(
            str(SERVICE_ACCOUNT_PATH), scopes=SCOPES
        )
        return gspread.authorize(creds)
    elif OAUTH_CREDENTIALS_PATH.exists() or AUTHORIZED_USER_PATH.exists():
        return gspread.oauth(
            scopes=SCOPES,
            credentials_filename=str(OAUTH_CREDENTIALS_PATH),
            authorized_user_filename=str(AUTHORIZED_USER_PATH),
        )
    else:
        raise FileNotFoundError(
            "No valid Google credentials found in 'secrets/'. "
            "Please provide either 'service_account.json' or 'credentials.json'."
        )


def initialize_tab(worksheet: gspread.Worksheet, headers: List[str]) -> None:
    """Ensures the header row exists if the tab is empty."""
    existing_rows = worksheet.get_all_values()
    if not any(existing_rows):
        worksheet.append_row(headers, table_range="A1")


def is_duplicate(worksheet: gspread.Worksheet, vendor_name: str, invoice_number: str) -> bool:
    """Checks vendor name and invoice number to prevent duplicate rows."""
    records = worksheet.get_all_values()
    if len(records) <= 1:
        return False

    for row in records[1:]:
        if len(row) >= 2:
            row_vendor = row[0].strip().lower()
            row_inv_num = row[1].strip().lower()
            if row_vendor == vendor_name.strip().lower() and row_inv_num == invoice_number.strip().lower():
                return True
    return False


def append_valid_invoice(invoice: InvoiceData, file_path: str) -> Tuple[bool, str]:
    """Appends one row per valid invoice to the primary 'Invoices' sheet tab."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)

        try:
            worksheet = sheet.worksheet("Invoices")
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="Invoices", rows="100", cols="20")

        headers = [
            "Vendor Name",
            "Invoice Number",
            "Invoice Date",
            "Due Date",
            "Total Amount",
            "Currency",
            "Subtotal",
            "Tax Amount",
            "Discount Amount",
            "Shipping Amount",
            "Vendor Tax ID",
            "PO Number",
            "Bill To Name",
            "Line Items Summary",
            "File Path",
        ]
        initialize_tab(worksheet, headers)

        vendor = invoice.vendor_name or "Unknown Vendor"
        inv_num = invoice.invoice_number or "N/A"

        # Prevent duplicate insertion
        if is_duplicate(worksheet, vendor, inv_num):
            msg = f"Duplicate invoice skipped: '{inv_num}' from '{vendor}' already exists."
            print(f"[Sheets] {msg}")
            return False, msg

        # Flatten line items into a clean summary string
        items_summary = "; ".join(
            [f"{item.description} (Qty: {item.quantity}, Price: {item.unit_price}, Amt: {item.amount})" for item in invoice.line_items]
        )

        row_data = [
            vendor,
            inv_num,
            invoice.invoice_date or "",
            invoice.due_date or "",
            invoice.total_amount,
            invoice.currency or "INR",
            invoice.subtotal,
            invoice.tax_amount,
            invoice.discount_amount,
            invoice.shipping_amount,
            invoice.vendor_tax_id or "",
            invoice.po_number or "",
            invoice.bill_to_name or "",
            items_summary,
            file_path,
        ]

        worksheet.append_row(row_data, table_range="A1")
        msg = f"Successfully appended invoice '{inv_num}' to 'Invoices' tab."
        print(f"[Sheets] {msg}")
        return True, msg

    except Exception as e:
        err_msg = f"Failed to append to Google Sheet: {str(e)}"
        print(f"[Sheets Error] {err_msg}")
        return False, err_msg


def append_needs_review(file_path: str, errors: List[str]) -> Tuple[bool, str]:
    """Appends failed/invalid invoices to the 'Needs Review' tab."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)

        try:
            worksheet = sheet.worksheet("Needs Review")
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="Needs Review", rows="100", cols="10")

        headers = ["File Path", "Failure Reason", "Logged At"]
        initialize_tab(worksheet, headers)

        from datetime import datetime
        logged_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_summary = " | ".join(errors) if errors else "Validation failed out of retries."

        row_data = [file_path, error_summary, logged_at]
        worksheet.append_row(row_data, table_range="A1")

        msg = f"Logged invalid invoice '{file_path}' to 'Needs Review' tab."
        print(f"[Sheets] {msg}")
        return True, msg

    except Exception as e:
        err_msg = f"Failed to log to 'Needs Review' tab: {str(e)}"
        print(f"[Sheets Error] {err_msg}")
        return False, err_msg