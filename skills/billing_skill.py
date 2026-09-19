"""
Billing & POS Skill: Multi-turn drafting, mid-build edits, atomic checkout, oversell guard.
"""
from typing import Dict, Any, Optional, List
from database.repository import StoreRepository, OversellError, GuardrailError

def build_or_update_bill(
    items_to_add: Optional[List[Dict[str, Any]]] = None,
    items_to_remove: Optional[List[str]] = None,
    items_to_update: Optional[List[Dict[str, Any]]] = None,
    payment_mode: Optional[str] = None,
    customer_name: Optional[str] = None,
    bill_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create or update an active draft bill.
    - items_to_add: list of dicts with {"sku_or_name": str, "quantity": float, "unit": Optional[str]}
    - items_to_remove: list of product names or SKUs to remove
    - items_to_update: list of dicts with {"sku_or_name": str, "quantity": float}
    - payment_mode: "cash", "upi", "card", or "khata"
    - customer_name: name of the customer
    
    IMPORTANT: Stock is NOT decremented during drafting. Stock is only decremented on finalize_bill.
    """
    try:
        bill = StoreRepository.get_or_create_draft_bill(bill_id)
        current_id = bill["bill_id"]

        # Default payment mode preference if not specified
        if not payment_mode and not bill.get("payment_mode"):
            pref_pay = StoreRepository.get_preference("default_payment_mode", "cash")
            payment_mode = pref_pay

        updated_bill = StoreRepository.update_draft_bill_items(
            bill_id=current_id,
            items_to_add=items_to_add,
            items_to_remove=items_to_remove,
            items_to_update=items_to_update,
            payment_mode=payment_mode,
            customer_name=customer_name
        )

        return {
            "status": "draft_updated",
            "bill_id": updated_bill["bill_id"],
            "bill_number": updated_bill["bill_number"],
            "customer_name": updated_bill["customer_name"] or "Walk-in",
            "payment_mode": updated_bill["payment_mode"],
            "item_count": len(updated_bill["items"]),
            "items": [
                {
                    "name": i["product_name"],
                    "qty": f"{i['quantity']} {i['unit']}",
                    "unit_price": f"₹{i['unit_price']:.2f}",
                    "total": f"₹{i['total_price']:.2f}"
                }
                for i in updated_bill["items"]
            ],
            "taxable_subtotal": f"₹{updated_bill['subtotal']:.2f}",
            "cgst": f"₹{updated_bill['cgst_amount']:.2f}",
            "sgst": f"₹{updated_bill['sgst_amount']:.2f}",
            "total_tax": f"₹{updated_bill['total_tax']:.2f}",
            "round_off": f"₹{updated_bill['round_off']:+.2f}",
            "net_payable": f"₹{updated_bill['rounded_total']:.2f}"
        }
    except (OversellError, GuardrailError, Exception) as e:
        return {"status": "error", "message": str(e)}

def add_single_item_to_bill(
    item_name: str,
    quantity: float = 1.0,
    unit: Optional[str] = None,
    payment_mode: Optional[str] = None,
    customer_name: Optional[str] = None,
    bill_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add an individual product to the active draft bill.
    Example: add_single_item_to_bill("sugar", 2.0, "kg")
    """
    return build_or_update_bill(
        items_to_add=[{"sku_or_name": item_name, "quantity": quantity, "unit": unit}],
        payment_mode=payment_mode,
        customer_name=customer_name,
        bill_id=bill_id
    )

def remove_single_item_from_bill(item_name: str, bill_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove an item from the draft bill.
    Example: remove_single_item_from_bill("butter")
    """
    return build_or_update_bill(
        items_to_remove=[item_name],
        bill_id=bill_id
    )

def update_single_item_quantity(item_name: str, new_quantity: float, bill_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Update the quantity of an item already on the draft bill.
    Example: update_single_item_quantity("Maggi", 6.0)
    """
    return build_or_update_bill(
        items_to_update=[{"sku_or_name": item_name, "quantity": new_quantity}],
        bill_id=bill_id
    )


def view_draft_bill(bill_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspect the current active draft bill line items, taxes, and grand total.
    """
    try:
        bill = StoreRepository.get_or_create_draft_bill(bill_id)
        return {
            "bill_id": bill["bill_id"],
            "bill_number": bill["bill_number"],
            "status": bill["status"],
            "customer_name": bill["customer_name"] or "Walk-in",
            "payment_mode": bill["payment_mode"],
            "items": [
                {
                    "name": i["product_name"],
                    "qty": f"{i['quantity']} {i['unit']}",
                    "rate": f"₹{i['unit_price']:.2f}",
                    "gst_rate": f"{int(i['gst_rate'] * 100)}%",
                    "total": f"₹{i['total_price']:.2f}"
                }
                for i in bill["items"]
            ],
            "subtotal": f"₹{bill['subtotal']:.2f}",
            "cgst": f"₹{bill['cgst_amount']:.2f}",
            "sgst": f"₹{bill['sgst_amount']:.2f}",
            "total_tax": f"₹{bill['total_tax']:.2f}",
            "grand_total": f"₹{bill['grand_total']:.2f}",
            "rounded_total": f"₹{bill['rounded_total']:.2f}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def finalize_current_bill(
    bill_id: str,
    payment_mode: Optional[str] = None,
    payment_ref: Optional[str] = None,
    customer_name: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finalize and checkout the draft bill.
    - Enforces DB-level OVERSELL GUARD (fails if stock < quantity).
    - Decrements stock atomically.
    - Charges to customer's Khata if payment_mode is 'khata'.
    - Idempotency protected: duplicate calls with same idempotency_key return previous result.
    """
    try:
        finalized = StoreRepository.finalize_bill(
            bill_id=bill_id,
            payment_mode=payment_mode,
            payment_ref=payment_ref,
            customer_name=customer_name,
            idempotency_key=idempotency_key
        )
        return {
            "status": "finalized",
            "bill_id": finalized["bill_id"],
            "bill_number": finalized["bill_number"],
            "customer_name": finalized["customer_name"] or "Walk-in",
            "payment_mode": finalized["payment_mode"].upper(),
            "payment_ref": finalized["payment_ref"] or "N/A",
            "items_count": len(finalized["items"]),
            "items": [
                {
                    "name": i["product_name"],
                    "qty": f"{i['quantity']} {i['unit']}",
                    "total": f"₹{i['total_price']:.2f}"
                }
                for i in finalized["items"]
            ],
            "taxable_subtotal": f"₹{finalized['subtotal']:.2f}",
            "cgst": f"₹{finalized['cgst_amount']:.2f}",
            "sgst": f"₹{finalized['sgst_amount']:.2f}",
            "net_payable": f"₹{finalized['rounded_total']:.2f}",
            "message": f"Bill {finalized['bill_number']} finalized successfully. Stock has been decremented."
        }
    except OversellError as e:
        return {
            "status": "oversell_refused",
            "error_type": "OversellGuard",
            "message": str(e)
        }
    except GuardrailError as e:
        return {
            "status": "guardrail_refused",
            "error_type": "GuardrailViolation",
            "message": str(e)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
