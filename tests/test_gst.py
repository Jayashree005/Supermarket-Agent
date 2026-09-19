"""
Unit tests for GST Engine and intra-state tax split.
"""
from core.gst_engine import GSTEngine

def test_gst_line_calculation_zero():
    line = GSTEngine.calculate_line_item(quantity=2, unit_price=44.0, gst_rate=0.0)
    assert line.line_total == 88.0
    assert line.taxable_value == 88.0
    assert line.cgst == 0.0
    assert line.sgst == 0.0
    assert line.total_tax == 0.0

def test_gst_line_calculation_5_percent():
    # MRP 255 inclusive of 5% GST
    line = GSTEngine.calculate_line_item(quantity=1, unit_price=255.0, gst_rate=0.05)
    assert line.line_total == 255.0
    assert line.taxable_value == 242.86
    assert line.total_tax == 12.14
    assert line.cgst == 6.07
    assert line.sgst == 6.07
    assert line.cgst + line.sgst == line.total_tax

def test_gst_line_calculation_18_percent():
    # 4 packets of Maggi at 14.0 = 56.0 gross, 18% GST
    line = GSTEngine.calculate_line_item(quantity=4, unit_price=14.0, gst_rate=0.18)
    assert line.line_total == 56.0
    assert line.taxable_value == 47.46
    assert line.total_tax == 8.54
    assert line.cgst == 4.27
    assert line.sgst == 4.27
    assert line.cgst + line.sgst == line.total_tax

def test_gst_invoice_summary_slabs():
    items = [
        {"quantity": 1, "unit_price": 255.0, "gst_rate": 0.05},
        {"quantity": 4, "unit_price": 14.0, "gst_rate": 0.18}
    ]
    summary = GSTEngine.calculate_invoice_summary(items)
    assert summary.grand_total == 311.0
    assert summary.rounded_total == 311.0
    assert len(summary.slab_breakup) == 2
