"""
Professional Indian GST Tax Invoice Generator using ReportLab.
Produces a crisp, compliant, printable GST invoice document.
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from config.settings import OUTPUT_DIR, DEFAULT_CURRENCY
from core.gst_engine import GSTEngine
from database.repository import StoreRepository

def number_to_words_inr(num: float) -> str:
    """Converts a numerical amount into Indian currency words representation."""
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_below_thousand(n: int) -> str:
        res = ""
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            res += tens[n // 10] + " "
            n %= 10
        if n > 0:
            res += units[n] + " "
        return res.strip()

    n = int(round(num))
    if n == 0:
        return "Rupees Zero Only"

    parts = []
    # Crores
    crores = n // 10000000
    n %= 10000000
    if crores > 0:
        parts.append(convert_below_thousand(crores) + " Crore")

    # Lakhs
    lakhs = n // 100000
    n %= 100000
    if lakhs > 0:
        parts.append(convert_below_thousand(lakhs) + " Lakh")

    # Thousands
    thousands = n // 1000
    n %= 1000
    if thousands > 0:
        parts.append(convert_below_thousand(thousands) + " Thousand")

    # Remainder
    if n > 0:
        parts.append(convert_below_thousand(n))

    return "Rupees " + " ".join(parts).strip() + " Only"

def generate_invoice_pdf(bill_data: Dict[str, Any]) -> str:
    """
    Generates a GST compliant invoice PDF file from bill dictionary.
    Returns the absolute path of the generated PDF file.
    """
    invoices_dir = OUTPUT_DIR / "invoices"
    invoices_dir.mkdir(parents=True, exist_ok=True)

    bill_num = bill_data.get("bill_number", "INV-0000")
    filename = f"{bill_num.replace('/', '_')}.pdf"
    pdf_path = str(invoices_dir / filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'StoreTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1B365D')
    )
    subtitle_style = ParagraphStyle(
        'StoreSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4A5568')
    )
    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0F5132')
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10
    )
    cell_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT
    )
    cell_right_bold = ParagraphStyle(
        'CellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT
    )

    story = []

    # Retrieve store preferences
    shop_name = StoreRepository.get_preference("shop_name", "ABC Super Market")
    shop_address = StoreRepository.get_preference("shop_address", "ABC Super Market, Coimbatore, Tamil Nadu")
    shop_gstin = StoreRepository.get_preference("shop_gstin", "XXX")
    shop_state = StoreRepository.get_preference("shop_state", "Tamil Nadu")
    shop_state_code = StoreRepository.get_preference("shop_state_code", "33")

    # Header
    story.append(Paragraph(shop_name.upper(), title_style))
    story.append(Paragraph(shop_address, subtitle_style))
    story.append(Paragraph(f"<b>GSTIN:</b> {shop_gstin} | <b>State:</b> {shop_state} (Code: {shop_state_code})", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("TAX INVOICE (RETAIL)", badge_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1B365D'), spaceBefore=2, spaceAfter=8))

    # Meta Info Table: Invoice No, Date, Customer, Payment Mode
    created_at_raw = bill_data.get("finalized_at") or bill_data.get("created_at")
    if isinstance(created_at_raw, str):
        try:
            created_dt = datetime.fromisoformat(created_at_raw)
            date_str = created_dt.strftime("%d-%b-%Y %I:%M %p")
        except Exception:
            date_str = created_at_raw
    else:
        date_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    cust_name = bill_data.get("customer_name") or "Walk-in Customer"
    pay_mode = (bill_data.get("payment_mode") or "Cash").upper()
    pay_ref = bill_data.get("payment_ref") or "N/A"

    meta_data = [
        [
            Paragraph(f"<b>Invoice No:</b> {bill_data.get('bill_number')}", cell_style),
            Paragraph(f"<b>Customer Name:</b> {cust_name}", cell_style)
        ],
        [
            Paragraph(f"<b>Date & Time:</b> {date_str}", cell_style),
            Paragraph(f"<b>Payment Mode:</b> {pay_mode} ({pay_ref})", cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Line Items Table
    headers = [
        Paragraph("<b>#</b>", cell_bold),
        Paragraph("<b>Item Description</b>", cell_bold),
        Paragraph("<b>HSN</b>", cell_bold),
        Paragraph("<b>Qty</b>", cell_bold),
        Paragraph("<b>Rate (Rs.)</b>", cell_right_bold),
        Paragraph("<b>Taxable (Rs.)</b>", cell_right_bold),
        Paragraph("<b>CGST (Rs.)</b>", cell_right_bold),
        Paragraph("<b>SGST (Rs.)</b>", cell_right_bold),
        Paragraph("<b>Total (Rs.)</b>", cell_right_bold),
    ]

    items_rows = [headers]
    items = bill_data.get("items", [])

    for idx, itm in enumerate(items, 1):
        items_rows.append([
            Paragraph(str(idx), cell_style),
            Paragraph(itm.get("product_name", ""), cell_style),
            Paragraph(itm.get("hsn_code", ""), cell_style),
            Paragraph(f"{itm.get('quantity')} {itm.get('unit')}", cell_style),
            Paragraph(f"{itm.get('unit_price', 0):.2f}", cell_right),
            Paragraph(f"{itm.get('taxable_value', 0):.2f}", cell_right),
            Paragraph(f"{itm.get('cgst', 0):.2f}", cell_right),
            Paragraph(f"{itm.get('sgst', 0):.2f}", cell_right),
            Paragraph(f"{itm.get('total_price', 0):.2f}", cell_right_bold),
        ])

    items_table = Table(items_rows, colWidths=[20, 150, 45, 45, 50, 60, 48, 48, 54])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # Tax Slabs Breakup & Invoice Totals Table
    tax_summary = GSTEngine.calculate_invoice_summary(items)
    
    # Left: Tax Slab Summary
    slab_rows = [
        [Paragraph("<b>GST Slab</b>", cell_bold), Paragraph("<b>Taxable (Rs.)</b>", cell_right_bold), Paragraph("<b>CGST (Rs.)</b>", cell_right_bold), Paragraph("<b>SGST (Rs.)</b>", cell_right_bold), Paragraph("<b>Total Tax (Rs.)</b>", cell_right_bold)]
    ]
    for s in tax_summary.slab_breakup:
        slab_rows.append([
            Paragraph(f"GST {s.slab_name}", cell_style),
            Paragraph(f"{s.taxable_value:.2f}", cell_right),
            Paragraph(f"{s.cgst_amount:.2f}", cell_right),
            Paragraph(f"{s.sgst_amount:.2f}", cell_right),
            Paragraph(f"{s.total_tax:.2f}", cell_right_bold)
        ])

    slab_table = Table(slab_rows, colWidths=[55, 65, 55, 55, 65])
    slab_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
    ]))

    # Right: Invoice Summary
    totals_data = [
        [Paragraph("Taxable Subtotal:", cell_style), Paragraph(f"Rs. {tax_summary.subtotal:.2f}", cell_right)],
        [Paragraph("Total CGST:", cell_style), Paragraph(f"Rs. {tax_summary.cgst_amount:.2f}", cell_right)],
        [Paragraph("Total SGST:", cell_style), Paragraph(f"Rs. {tax_summary.sgst_amount:.2f}", cell_right)],
        [Paragraph("Total GST:", cell_bold), Paragraph(f"Rs. {tax_summary.total_tax:.2f}", cell_right_bold)],
        [Paragraph("Round Off:", cell_style), Paragraph(f"Rs. {tax_summary.round_off:+.2f}", cell_right)],
        [Paragraph("<b>Net Payable Amount:</b>", cell_bold), Paragraph(f"<b>Rs. {tax_summary.rounded_total:,.2f}</b>", cell_right_bold)],
    ]
    totals_table = Table(totals_data, colWidths=[120, 95])
    totals_table.setStyle(TableStyle([
        ('BACKGROUND', (0,5), (-1,5), colors.HexColor('#E0F2FE')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
    ]))

    combined_summary_table = Table([[slab_table, totals_table]], colWidths=[305, 215])
    combined_summary_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(combined_summary_table)
    story.append(Spacer(1, 10))

    # Amount in words
    amt_words = number_to_words_inr(tax_summary.rounded_total)
    story.append(Paragraph(f"<b>Amount in Words:</b> <i>{amt_words}</i>", cell_style))
    story.append(Spacer(1, 20))

    # Signatory and Footer Note
    footer_data = [
        [
            Paragraph("<b>Terms & Conditions:</b><br/>1. Goods once sold will not be taken back.<br/>2. Subject to local jurisdiction.<br/><i>Thank you for shopping with us!</i>", subtitle_style),
            Paragraph(f"For <b>{shop_name}</b><br/><br/><br/><b>Authorised Signatory</b>", ParagraphStyle('Sign', parent=cell_style, alignment=TA_CENTER))
        ]
    ]
    footer_table = Table(footer_data, colWidths=[320, 200])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))
    story.append(KeepTogether(footer_table))

    # Build PDF
    doc.build(story)
    return pdf_path
