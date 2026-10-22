import base64
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import RECIPIENT_EMAIL, SECRETS_DIR
from src.core.schema import InvoiceData

# Required Gmail scope for sending emails
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

OAUTH_CREDENTIALS_PATH = SECRETS_DIR / "credentials.json"
GMAIL_TOKEN_PATH = SECRETS_DIR / "gmail_token.json"


def get_gmail_service():
    """Authenticates and returns the Gmail API client service."""
    creds = None

    if GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(
            str(GMAIL_TOKEN_PATH), SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing OAuth credentials file at '{OAUTH_CREDENTIALS_PATH}'"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(OAUTH_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save authorized Gmail tokens
        with open(GMAIL_TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_email_message(
    invoice: InvoiceData, file_path: str, recipient_email: str
) -> MIMEMultipart:
    """Builds an HTML formatted email with the original invoice file attached."""
    msg = MIMEMultipart()
    msg["To"] = recipient_email

    vendor = invoice.vendor_name or "Unknown Vendor"
    inv_num = invoice.invoice_number or "N/A"
    total = f"{invoice.total_amount:,.2f}"
    currency = invoice.currency or "INR"
    due_date = invoice.due_date or "N/A"

    # Exact Subject line structure required by specification:
    # e.g., "Invoice INV 1042 from Acme Supplies, 4,250.00 INR due 30 Oct"
    msg["Subject"] = (
        f"Invoice {inv_num} from {vendor}, {total} {currency} due {due_date}"
    )

    # HTML Body Summary
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Invoice Processing Summary</h2>
        <p>A new supplier invoice has been processed and logged to Google Sheets.</p>
        
        <table style="border-collapse: collapse; width: 100%; max-width: 600px; margin-top: 10px;">
          <tr style="background-color: #f2f2f2;">
            <th style="padding: 8px; border: 1px solid #dddddd; text-align: left;">Field</th>
            <th style="padding: 8px; border: 1px solid #dddddd; text-align: left;">Value</th>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>Vendor Name</strong></td>
            <td style="padding: 8px; border: 1px solid #dddddd;">{vendor}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>Invoice Number</strong></td>
            <td style="padding: 8px; border: 1px solid #dddddd;">{inv_num}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>Invoice Date</strong></td>
            <td style="padding: 8px; border: 1px solid #dddddd;">{invoice.invoice_date or 'N/A'}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>Due Date</strong></td>
            <td style="padding: 8px; border: 1px solid #dddddd;">{due_date}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>Total Payable</strong></td>
            <td style="padding: 8px; border: 1px solid #dddddd;"><strong>{total} {currency}</strong></td>
          </tr>
        </table>

        <p style="margin-top: 15px;">The original invoice file is attached to this email.</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    # Attach original PDF invoice file
    path = Path(file_path)
    if path.exists():
        with open(path, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=path.name,
            )
            msg.attach(attachment)

    return msg


def send_invoice_summary_email(
    invoice: InvoiceData, file_path: str
) -> Tuple[bool, str]:
    """Sends the summary email using Gmail API."""
    try:
        service = get_gmail_service()
        recipient = RECIPIENT_EMAIL or "your_email@gmail.com"

        message = create_email_message(invoice, file_path, recipient)
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent_message = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

        msg = f"Email summary sent to {recipient} (Message ID: {sent_message['id']})"
        print(f"[Gmail] {msg}")
        return True, msg

    except Exception as e:
        err_msg = f"Failed to send email summary: {repr(e)}"
        print(f"[Gmail Error] {err_msg}")
        return False, err_msg