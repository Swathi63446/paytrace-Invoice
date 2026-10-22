import os
import sys
from pathlib import Path
from typing import List, Optional 
from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.genai import types

from config.settings import GEMINI_API_KEY, GEMINI_MODEL_NAME, SECRETS_DIR
from src.core.schema import InvoiceData

#credentials_path = SECRETS_DIR / "credentials.json"
#if credentials_path.exists():
#   os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "secrets/credentials.json"

PROJECT_ID = "project-2cbc8454-787c-4222-b43"
LOCATION = "us"
PROCESSOR_ID = "1bdbbc6be56a6c33"

genai_client = genai.Client(api_key=GEMINI_API_KEY)


def extract_raw_ocr_pdf(pdf_path: Path) -> str:
    """Step 1: Performs raw OCR on PDF files using Google Document AI."""
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{LOCATION}-documentai.googleapis.com"
        )
    )

    with open(pdf_path, "rb") as file_data:
        content = file_data.read()

    request = documentai.ProcessRequest(
        name=client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID),
        raw_document=documentai.RawDocument(
            content=content,
            mime_type="application/pdf",
        ),
    )

    result = client.process_document(request)
    return result.document.text


def extract_invoice_data(
    pdf_path: str, validation_errors: Optional[List[str]] = None
) -> InvoiceData:
    """Step 2: Takes raw OCR text from PDF and structures it into InvoiceData using Gemini."""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File '{path.name}' is not a PDF. Please provide a .pdf file.")

    print(f"1. Extracting raw text from PDF with Document AI: {path.name}...")
    raw_ocr_text = extract_raw_ocr_pdf(path)

    if not raw_ocr_text.strip():
        raise ValueError("Document AI returned no text from the PDF.")

    print(f"2. Structuring text into InvoiceData schema using {GEMINI_MODEL_NAME}...")

    prompt = (
        "You are a precise invoice extraction model. Extract structured data from the raw OCR text into the requested JSON schema.\n\n"
        "EXTRACTION RULES:\n"
        "1. Extract EXACTLY what is written on the document. Do NOT invent numbers.\n"
        "2. Convert all dates to YYYY-MM-DD format.\n"
        "3. Ensure all amounts (subtotal, tax, discount, shipping, total) are floats. If discount or shipping is not mentioned, set them to 0.0.\n"
        "4. Calculate amount for each line item as quantity * unit_price if omitted.\n\n"
        f"--- RAW OCR TEXT ---\n{raw_ocr_text}\n--------------------"
    )

    if validation_errors:
        prompt += (
            "\n\nATTENTION: Previous extraction attempt failed validation with these errors:\n"
            + "\n".join(f"- {err}" for err in validation_errors)
            + "\n\nPlease re-read the raw OCR text carefully to fix reading errors or missing fields."
        )

    response = genai_client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InvoiceData,
            temperature=0.0,
        ),
    )

    return response.parsed