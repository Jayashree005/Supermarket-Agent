"""
Khata Skill: Customer credit ledger, balance inquiry, credit additions, and settlement payments.
"""
from typing import Dict, Any, Optional
from database.repository import StoreRepository, GuardrailError

def check_customer_khata_balance(customer_name: str) -> Dict[str, Any]:
    """
    Check the outstanding credit balance of a customer in the khata ledger.
    """
    cust = StoreRepository.get_khata_customer(customer_name)
    if not cust:
        return {
            "status": "not_found",
            "customer_name": customer_name,
            "balance": 0.0,
            "message": f"No Khata account found for '{customer_name}'. Customer has no past credit transactions."
        }
    return {
        "status": "found",
        "customer_name": cust["name"],
        "balance": cust["balance"],
        "phone": cust["phone"] or "N/A",
        "formatted_balance": f"₹{cust['balance']:,.2f}",
        "summary": f"{cust['name']}'s outstanding khata balance is ₹{cust['balance']:,.2f}."
    }

def add_credit_to_khata(customer_name: str, amount: float, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Record a credit purchase on customer's khata account ("Put ₹500 on Ramesh's credit").
    Increases the balance owed by the customer.
    """
    try:
        res = StoreRepository.add_khata_credit(customer_name, amount, notes)
        return {
            "status": "success",
            "customer_name": res["customer_name"],
            "amount_added": f"₹{res['amount_added']:,.2f}",
            "new_balance": f"₹{res['new_balance']:,.2f}",
            "message": f"Added ₹{res['amount_added']:,.2f} to {res['customer_name']}'s credit. Total balance is now ₹{res['new_balance']:,.2f}."
        }
    except GuardrailError as e:
        return {"status": "error", "message": str(e)}

def record_khata_payment(customer_name: str, amount: float, payment_mode: str = "cash", notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Record customer settling/paying their credit ("Ramesh paid ₹300").
    GUARDRAIL: Refuses payment if customer does not exist in khata.
    """
    try:
        res = StoreRepository.record_khata_settlement(customer_name, amount, payment_mode, notes)
        return {
            "status": "success",
            "customer_name": res["customer_name"],
            "amount_paid": f"₹{res['amount_paid']:,.2f}",
            "previous_balance": f"₹{res['previous_balance']:,.2f}",
            "new_balance": f"₹{res['new_balance']:,.2f}",
            "payment_mode": res["payment_mode"].upper(),
            "message": f"Received payment of ₹{res['amount_paid']:,.2f} from {res['customer_name']}. Outstanding balance is now ₹{res['new_balance']:,.2f}."
        }
    except GuardrailError as e:
        return {
            "status": "guardrail_refused",
            "error_type": "KhataNonExistent",
            "message": str(e)
        }

def list_active_khata_accounts() -> Dict[str, Any]:
    """
    List all customers with outstanding unpaid credit balances.
    """
    khatas = StoreRepository.list_all_khatas()
    total_due = sum(k["balance"] for k in khatas)
    return {
        "count": len(khatas),
        "total_outstanding": f"₹{total_due:,.2f}",
        "customers": [
            {
                "name": k["name"],
                "balance": f"₹{k['balance']:,.2f}",
                "phone": k["phone"] or "N/A"
            }
            for k in khatas
        ]
    }
