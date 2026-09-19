"""
Pydantic Domain Models for Indian Kirana & Supermarket Agent.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

class Product(BaseModel):
    sku_id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    unit: str  # kg, g, litre, ml, packet, piece, dozen
    is_loose: bool = False
    cost_price: float
    mrp: float
    sell_price: float
    stock_qty: float
    reorder_level: float = 5.0
    hsn_code: str
    gst_rate: float  # e.g., 0.05 for 5%

class BillItemDraft(BaseModel):
    sku_id: str
    quantity: float
    unit: Optional[str] = None

class BillItem(BaseModel):
    item_id: Optional[int] = None
    bill_id: str
    sku_id: str
    product_name: str
    unit: str
    quantity: float
    cost_price: float
    unit_price: float
    hsn_code: str
    gst_rate: float
    taxable_value: float
    cgst: float
    sgst: float
    total_price: float

class Bill(BaseModel):
    bill_id: str
    bill_number: str
    status: Literal["draft", "finalized", "cancelled"] = "draft"
    created_at: datetime
    finalized_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_mode: Literal["cash", "upi", "card", "khata"] = "cash"
    payment_ref: Optional[str] = None
    subtotal: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    total_tax: float = 0.0
    grand_total: float = 0.0
    round_off: float = 0.0
    rounded_total: float = 0.0
    notes: Optional[str] = None
    items: List[BillItem] = Field(default_factory=list)

class KhataEntry(BaseModel):
    entry_id: Optional[int] = None
    customer_name: str
    entry_type: Literal["debit", "credit"]
    amount: float
    balance_after: float
    reference_bill_id: Optional[str] = None
    payment_mode: str = "cash"
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None

class StockLedgerEntry(BaseModel):
    entry_id: Optional[int] = None
    sku_id: str
    entry_type: Literal["stock_in", "sale", "adjustment", "return"]
    qty_change: float
    stock_after: float
    cost_price: Optional[float] = None
    mrp: Optional[float] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None
