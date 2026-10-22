from typing import List, Optional, TypedDict
from src.core.schema import InvoiceData


class InvoiceState(TypedDict):
    file_path: str
    invoice_data: Optional[InvoiceData]
    errors: List[str]
    retries: int
    status: str  # "valid", "needs_review", or "pending"