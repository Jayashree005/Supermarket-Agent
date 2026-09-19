"""
Document Skill: Dispatches generation of clean GST PDF invoices and PowerPoint analysis decks.
"""
from typing import Dict, Any, Optional
from database.db import get_connection
from database.repository import StoreRepository
from artifacts.invoice_pdf import generate_invoice_pdf
from artifacts.analysis_pptx import generate_weekly_analysis_deck

def generate_gst_invoice_pdf(bill_id_or_number: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate an authentic, GST-compliant PDF invoice for a bill.
    If no bill ID is provided, automatically uses the most recent bill.
    """
    conn = get_connection()
    cursor = conn.cursor()

    target_id = None
    if bill_id_or_number:
        cursor.execute("SELECT bill_id FROM bills WHERE bill_id = ? OR bill_number = ?;", (bill_id_or_number, bill_id_or_number))
        row = cursor.fetchone()
        if row:
            target_id = row["bill_id"]
    
    if not target_id:
        # Fall back to latest bill
        cursor.execute("SELECT bill_id FROM bills ORDER BY created_at DESC LIMIT 1;")
        row = cursor.fetchone()
        if row:
            target_id = row["bill_id"]

    if not target_id:
        return {"status": "error", "message": "No bills found in the store database to generate an invoice for."}

    bill_data = StoreRepository.get_full_bill(target_id)
    if not bill_data["items"]:
        return {"status": "error", "message": f"Bill {bill_data['bill_number']} has no line items."}

    pdf_path = generate_invoice_pdf(bill_data)

    return {
        "status": "success",
        "file_path": pdf_path,
        "bill_number": bill_data["bill_number"],
        "customer_name": bill_data["customer_name"] or "Walk-in",
        "total_amount": f"₹{bill_data['rounded_total']:.2f}",
        "message": f"GST Invoice PDF for {bill_data['bill_number']} generated successfully at: {pdf_path}"
    }

def generate_business_analysis_deck(days: int = 7) -> Dict[str, Any]:
    """
    Generate an executive PowerPoint presentation (PPTX) analyzing weekly store performance,
    sales velocity, payment channels, top products, stock reorder alerts, and tax liability.
    """
    try:
        pptx_path = generate_weekly_analysis_deck(days=days)
        return {
            "status": "success",
            "file_path": pptx_path,
            "period_days": days,
            "message": f"Store Operations Analysis Deck (PPTX) generated successfully at: {pptx_path}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
