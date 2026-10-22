from typing import List, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(..., description="Description of item or service")
    quantity: float = Field(default=1.0, ge=0.0)
    unit_price: float = Field(default=0.0, ge=0.0)
    amount: float = Field(..., ge=0.0)


class InvoiceData(BaseModel):
    # Mandatory / Core Attributes
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    vendor_name: Optional[str] = Field(None, description="Vendor or supplier name")
    invoice_date: Optional[str] = Field(None, description="Issue date in YYYY-MM-DD")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD")
    total_amount: float = Field(default=0.0, ge=0.0, description="Total amount payable")
    currency: Optional[str] = Field("INR", description="Currency code (e.g., INR, USD)")
    payment_terms: Optional[str] = Field(None, description="Payment terms")

    # Financial Breakdown (Default to 0.0 to prevent None values during validation)
    subtotal: float = Field(default=0.0, ge=0.0, description="Subtotal before taxes/fees")
    tax_amount: float = Field(default=0.0, ge=0.0, description="Tax or GST amount")
    discount_amount: float = Field(default=0.0, ge=0.0, description="Discount amount")
    shipping_amount: float = Field(default=0.0, ge=0.0, description="Shipping or freight fee")

    # Optional Metadata
    vendor_tax_id: Optional[str] = Field(None, description="Vendor Tax ID or GSTIN")
    po_number: Optional[str] = Field(None, description="Purchase Order number")
    bill_to_name: Optional[str] = Field(None, description="Billed customer name")
    vendor_address: Optional[str] = Field(None, description="Vendor address")
    line_items: List[LineItem] = Field(default_factory=list)