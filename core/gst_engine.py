"""
GST Engine for Indian Supermarket / Kirana Store.
Handles intra-state CGST/SGST 50-50 splits, HSN tax slabs, and exact decimal rounding.
"""
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class LineTaxResult:
    taxable_value: float
    cgst: float
    sgst: float
    total_tax: float
    line_total: float

@dataclass
class SlabBreakup:
    slab_rate: float        # e.g. 0.05 for 5%
    slab_name: str         # e.g. "5%"
    taxable_value: float
    cgst_rate: float       # e.g. 0.025
    cgst_amount: float
    sgst_rate: float       # e.g. 0.025
    sgst_amount: float
    total_tax: float

@dataclass
class InvoiceTaxSummary:
    subtotal: float        # Taxable value total
    cgst_amount: float
    sgst_amount: float
    total_tax: float
    grand_total: float
    round_off: float
    rounded_total: float
    slab_breakup: List[SlabBreakup]

class GSTEngine:
    """Computes Indian retail GST where MRP is inclusive of taxes."""

    @staticmethod
    def calculate_line_item(quantity: float, unit_price: float, gst_rate: float) -> LineTaxResult:
        """
        Calculates taxable value, CGST, SGST from tax-inclusive unit price.
        Intra-state split: 50% CGST + 50% SGST.
        """
        gross = round(quantity * unit_price, 2)
        if gst_rate <= 0:
            return LineTaxResult(
                taxable_value=gross,
                cgst=0.0,
                sgst=0.0,
                total_tax=0.0,
                line_total=gross
            )
        
        # In retail, MRP includes GST: Gross = Taxable * (1 + Rate)
        taxable_value = round(gross / (1.0 + gst_rate), 2)
        total_tax = round(gross - taxable_value, 2)
        
        # Intra-state CGST & SGST 50/50 split
        cgst = round(total_tax / 2.0, 2)
        sgst = round(total_tax - cgst, 2) # Ensures sum of split matches total_tax exactly
        
        return LineTaxResult(
            taxable_value=taxable_value,
            cgst=cgst,
            sgst=sgst,
            total_tax=total_tax,
            line_total=gross
        )

    @staticmethod
    def calculate_invoice_summary(items: List[Dict[str, Any]]) -> InvoiceTaxSummary:
        """
        Aggregates invoice totals and computes slab-wise tax breakdown.
        Each item dict expects: quantity, unit_price, gst_rate.
        """
        slab_data: Dict[float, Dict[str, float]] = {}
        total_taxable = 0.0
        total_cgst = 0.0
        total_sgst = 0.0
        total_tax = 0.0
        grand_total = 0.0

        for item in items:
            qty = float(item["quantity"])
            rate = float(item["unit_price"])
            gst_rate = float(item.get("gst_rate", 0.0))

            line = GSTEngine.calculate_line_item(qty, rate, gst_rate)
            total_taxable += line.taxable_value
            total_cgst += line.cgst
            total_sgst += line.sgst
            total_tax += line.total_tax
            grand_total += line.line_total

            if gst_rate not in slab_data:
                slab_data[gst_rate] = {
                    "taxable": 0.0,
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "tax": 0.0
                }
            slab_data[gst_rate]["taxable"] += line.taxable_value
            slab_data[gst_rate]["cgst"] += line.cgst
            slab_data[gst_rate]["sgst"] += line.sgst
            slab_data[gst_rate]["tax"] += line.total_tax

        total_taxable = round(total_taxable, 2)
        total_cgst = round(total_cgst, 2)
        total_sgst = round(total_sgst, 2)
        total_tax = round(total_tax, 2)
        grand_total = round(grand_total, 2)

        rounded_total = round(grand_total)
        round_off = round(rounded_total - grand_total, 2)

        # Build sorted slab breakup list
        slabs: List[SlabBreakup] = []
        for rate in sorted(slab_data.keys()):
            data = slab_data[rate]
            slabs.append(SlabBreakup(
                slab_rate=rate,
                slab_name=f"{int(rate * 100)}%",
                taxable_value=round(data["taxable"], 2),
                cgst_rate=rate / 2.0,
                cgst_amount=round(data["cgst"], 2),
                sgst_rate=rate / 2.0,
                sgst_amount=round(data["sgst"], 2),
                total_tax=round(data["tax"], 2)
            ))

        return InvoiceTaxSummary(
            subtotal=total_taxable,
            cgst_amount=total_cgst,
            sgst_amount=total_sgst,
            total_tax=total_tax,
            grand_total=grand_total,
            round_off=round_off,
            rounded_total=float(rounded_total),
            slab_breakup=slabs
        )
