"""
Analytics Skill: Daily close summaries, tax reconciliation, cash vs UPI breakdowns, top items.
"""
from typing import Dict, Any, Optional
from database.repository import StoreRepository

def get_daily_close(date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate end-of-day daily close report:
    Gross sales, total statutory GST collected (CGST + SGST), payment split (Cash vs UPI vs Card),
    and top selling products.
    """
    data = StoreRepository.get_daily_close_data(date_str)
    t = data["totals"]
    
    pay_summary = ", ".join([
        f"{p['payment_mode'].upper()}: ₹{p['amount']:,.2f} ({p['count']} bills)"
        for p in data["payment_breakdown"]
    ]) or "No transactions recorded yet today."

    top_summary = [
        f"{idx}. {item['product_name']}: {item['total_qty']} {item['unit']} (₹{item['total_revenue']:,.2f})"
        for idx, item in enumerate(data["top_items"], 1)
    ]

    return {
        "status": "success",
        "date": data["date"],
        "bills_count": t["bill_count"],
        "gross_sales": f"₹{t['gross_sales']:,.2f}",
        "taxable_amount": f"₹{t['total_taxable']:,.2f}",
        "cgst_collected": f"₹{t['total_cgst']:,.2f}",
        "sgst_collected": f"₹{t['total_sgst']:,.2f}",
        "total_tax_collected": f"₹{t['total_tax']:,.2f}",
        "payment_modes": pay_summary,
        "top_selling_items": top_summary,
        "formatted_summary": (
            f"📊 **Daily Close Summary ({data['date']})**\n"
            f"• **Gross Sales:** ₹{t['gross_sales']:,.2f} ({t['bill_count']} bills)\n"
            f"• **GST Collected:** ₹{t['total_tax']:,.2f} (CGST: ₹{t['total_cgst']:,.2f} | SGST: ₹{t['total_sgst']:,.2f})\n"
            f"• **Payment Channels:** {pay_summary}\n"
            f"• **Top Items:**\n  " + ("\n  ".join(top_summary) if top_summary else "None")
        )
    }
