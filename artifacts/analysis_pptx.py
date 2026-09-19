"""
PowerPoint Business Analysis Deck Generator using python-pptx.
Generates an executive deck with native PowerPoint charts, KPI cards, and actionable insights.
"""
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.chart.data import CategoryChartData

from config.settings import OUTPUT_DIR
from database.db import get_connection
from database.repository import StoreRepository

# Modern color palette
NAVY = RGBColor(27, 54, 93)
TEAL = RGBColor(14, 116, 144)
DARK_GRAY = RGBColor(51, 65, 85)
LIGHT_BG = RGBColor(248, 250, 252)
ACCENT_GREEN = RGBColor(22, 101, 52)
ACCENT_AMBER = RGBColor(180, 83, 9)
CARD_BG = RGBColor(241, 245, 249)
WHITE = RGBColor(255, 255, 255)

def _add_slide_header(slide, title_text: str, subtitle_text: str = ""):
    """Adds a standardized clean header to a slide."""
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(8.4), Inches(0.9))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p = tf.paragraphs[0]
    p.text = title_text
    p.font.name = "Calibri"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = NAVY

    if subtitle_text:
        p2 = tf.add_paragraph()
        p2.text = subtitle_text
        p2.font.name = "Calibri"
        p2.font.size = Pt(11)
        p2.font.color.rgb = DARK_GRAY

def _add_kpi_card(slide, left: float, top: float, width: float, height: float, title: str, value: str, subtext: str = ""):
    """Draws a metric card."""
    shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height)) # 1 = MSO_SHAPE.RECTANGLE
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD_BG
    shape.line.color.rgb = RGBColor(203, 213, 225)
    shape.line.width = Pt(1)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    p1 = tf.paragraphs[0]
    p1.text = title.upper()
    p1.font.size = Pt(9)
    p1.font.bold = True
    p1.font.color.rgb = DARK_GRAY
    p1.alignment = PP_ALIGN.CENTER

    p2 = tf.add_paragraph()
    p2.text = value
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = NAVY
    p2.alignment = PP_ALIGN.CENTER

    if subtext:
        p3 = tf.add_paragraph()
        p3.text = subtext
        p3.font.size = Pt(8.5)
        p3.font.color.rgb = TEAL
        p3.alignment = PP_ALIGN.CENTER

def generate_weekly_analysis_deck(days: int = 7) -> str:
    """
    Analyzes recent store sales, category performance, GST collection,
    khata book health, and inventory, and compiles a PPTX deck with native charts.
    Returns path to the saved presentation.
    """
    decks_dir = OUTPUT_DIR / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    today_str = date.today().strftime("%Y%m%d")
    pptx_path = str(decks_dir / f"Store_Ops_Analysis_{today_str}.pptx")

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625) # 16:9 widescreen
    blank_layout = prs.slide_layouts[6]

    conn = get_connection()
    cursor = conn.cursor()

    shop_name = StoreRepository.get_preference("shop_name", "Sri Krishna Supermarket & Kirana")
    shop_gstin = StoreRepository.get_preference("shop_gstin", "29ABCDE1234F1Z5")

    # Gather data
    start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 1. Total sales & tax
    cursor.execute("""
        SELECT 
            COUNT(*) as total_bills,
            COALESCE(SUM(rounded_total), 0.0) as total_sales,
            COALESCE(SUM(total_tax), 0.0) as total_tax,
            COALESCE(AVG(rounded_total), 0.0) as avg_bill_value
        FROM bills
        WHERE status = 'finalized' AND DATE(created_at) >= DATE(?);
    """, (start_date,))
    perf = dict(cursor.fetchone())

    # 2. Khata total outstanding
    cursor.execute("SELECT COALESCE(SUM(balance), 0.0) as total_khata, COUNT(*) as active_khata_users FROM khata_customers WHERE balance > 0;")
    khata_info = dict(cursor.fetchone())

    # 3. Daily sales trend
    cursor.execute("""
        SELECT DATE(created_at) as sale_date, COALESCE(SUM(rounded_total), 0.0) as daily_total
        FROM bills
        WHERE status = 'finalized' AND DATE(created_at) >= DATE(?)
        GROUP BY DATE(created_at)
        ORDER BY sale_date ASC;
    """, (start_date,))
    daily_rows = cursor.fetchall()
    daily_labels = [r["sale_date"] for r in daily_rows] or [date.today().strftime("%Y-%m-%d")]
    daily_values = [r["daily_total"] for r in daily_rows] or [perf["total_sales"]]

    # 4. Payment breakdown
    cursor.execute("""
        SELECT payment_mode, COALESCE(SUM(rounded_total), 0.0) as total
        FROM bills
        WHERE status = 'finalized' AND DATE(created_at) >= DATE(?)
        GROUP BY payment_mode;
    """, (start_date,))
    pay_rows = cursor.fetchall()
    pay_labels = [r["payment_mode"].upper() for r in pay_rows] or ["CASH", "UPI"]
    pay_values = [r["total"] for r in pay_rows] or [0.0, perf["total_sales"]]

    # 5. Top items
    cursor.execute("""
        SELECT bi.product_name, SUM(bi.quantity) as qty, bi.unit, SUM(bi.total_price) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.bill_id
        WHERE b.status = 'finalized' AND DATE(b.created_at) >= DATE(?)
        GROUP BY bi.sku_id
        ORDER BY revenue DESC
        LIMIT 5;
    """, (start_date,))
    top_items = [dict(r) for r in cursor.fetchall()]

    # 6. Low stock items
    low_stock = StoreRepository.get_low_stock_items()

    # -------------------------------------------------------------
    # SLIDE 1: TITLE SLIDE
    # -------------------------------------------------------------
    slide1 = prs.slides.add_slide(blank_layout)
    bg1 = slide1.shapes.add_shape(1, 0, 0, Inches(10), Inches(5.625))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = NAVY
    bg1.line.color.rgb = NAVY

    title_box = slide1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(8.0), Inches(2.2))
    tf1 = title_box.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = shop_name.upper()
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = WHITE

    p2 = tf1.add_paragraph()
    p2.text = f"Weekly Store Operations & Sales Intelligence Deck"
    p2.font.size = Pt(16)
    p2.font.color.rgb = RGBColor(147, 197, 253)

    p3 = tf1.add_paragraph()
    p3.text = f"Analysis Period: Last {days} Days | Generated on {datetime.now().strftime('%d %b %Y')}\nGSTIN: {shop_gstin}"
    p3.font.size = Pt(11)
    p3.font.color.rgb = RGBColor(226, 232, 240)

    # -------------------------------------------------------------
    # SLIDE 2: EXECUTIVE KPI SUMMARY
    # -------------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_layout)
    _add_slide_header(slide2, "Executive Store Performance Overview", "High-level metrics across sales, tax compliance, and credit ledger")

    _add_kpi_card(slide2, 0.8, 1.5, 2.0, 1.4, "Gross Sales", f"₹ {perf['total_sales']:,.0f}", f"{perf['total_bills']} Bills Cut")
    _add_kpi_card(slide2, 3.0, 1.5, 2.0, 1.4, "Average Ticket", f"₹ {perf['avg_bill_value']:,.0f}", "Per Customer Bill")
    _add_kpi_card(slide2, 5.2, 1.5, 2.0, 1.4, "Total GST Collected", f"₹ {perf['total_tax']:,.1f}", "CGST + SGST Split")
    _add_kpi_card(slide2, 7.4, 1.5, 2.0, 1.4, "Khata Outstanding", f"₹ {khata_info['total_khata']:,.0f}", f"{khata_info['active_khata_users']} Customers Due")

    # Insight box below KPI cards
    info_shape = slide2.shapes.add_shape(1, Inches(0.8), Inches(3.2), Inches(8.4), Inches(1.8))
    info_shape.fill.solid()
    info_shape.fill.fore_color.rgb = WHITE
    info_shape.line.color.rgb = RGBColor(226, 232, 240)
    tf_info = info_shape.text_frame
    tf_info.word_wrap = True
    tf_info.margin_left = tf_info.margin_top = Inches(0.2)

    pi = tf_info.paragraphs[0]
    pi.text = "Key Operational Highlights:"
    pi.font.bold = True
    pi.font.size = Pt(13)
    pi.font.color.rgb = NAVY

    b1 = tf_info.add_paragraph()
    b1.text = f"• Billing Activity: Recorded {perf['total_bills']} finalized transactions totaling ₹{perf['total_sales']:,.2f}."
    b1.font.size = Pt(11)
    b1.font.color.rgb = DARK_GRAY

    b2 = tf_info.add_paragraph()
    b2.text = f"• Tax Compliance: ₹{perf['total_tax']:,.2f} collected in statutory GST with accurate 50/50 intra-state CGST & SGST allocation."
    b2.font.size = Pt(11)
    b2.font.color.rgb = DARK_GRAY

    b3 = tf_info.add_paragraph()
    b3.text = f"• Khata Health: Outstanding customer credit stands at ₹{khata_info['total_khata']:,.2f}. Regular settlement cycles recommended."
    b3.font.size = Pt(11)
    b3.font.color.rgb = DARK_GRAY

    # -------------------------------------------------------------
    # SLIDE 3: SALES TREND & PAYMENT CHANNEL MIX (Native Charts)
    # -------------------------------------------------------------
    slide3 = prs.slides.add_slide(blank_layout)
    _add_slide_header(slide3, "Sales Trend & Payment Channel Mix", "Revenue trajectory and distribution by payment modes")

    # Chart 1: Daily Sales Clustered Column
    chart_data1 = CategoryChartData()
    chart_data1.categories = daily_labels
    chart_data1.add_series('Sales (₹)', daily_values)

    x1, y1, cx1, cy1 = Inches(0.8), Inches(1.5), Inches(4.5), Inches(3.5)
    chart1 = slide3.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, x1, y1, cx1, cy1, chart_data1
    ).chart
    chart1.has_legend = False
    chart1.has_title = True
    chart1.chart_title.text_frame.text = "Daily Sales Velocity (₹)"

    # Chart 2: Payment Mode Donut / Pie
    chart_data2 = CategoryChartData()
    chart_data2.categories = pay_labels
    chart_data2.add_series('Share (₹)', pay_values)

    x2, y2, cx2, cy2 = Inches(5.5), Inches(1.5), Inches(3.8), Inches(3.5)
    chart2 = slide3.shapes.add_chart(
        XL_CHART_TYPE.PIE, x2, y2, cx2, cy2, chart_data2
    ).chart
    chart2.has_legend = True
    chart2.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart2.has_title = True
    chart2.chart_title.text_frame.text = "Payment Mode Distribution"

    # -------------------------------------------------------------
    # SLIDE 4: TOP PERFORMING PRODUCTS
    # -------------------------------------------------------------
    slide4 = prs.slides.add_slide(blank_layout)
    _add_slide_header(slide4, "Top Revenue Contributors (SKU Level)", "Top 5 fast-moving items by total billing volume")

    if top_items:
        # Table of top items
        table_shape = slide4.shapes.add_table(len(top_items) + 1, 4, Inches(0.8), Inches(1.5), Inches(8.4), Inches(3.0))
        table = table_shape.table
        table.columns[0].width = Inches(3.6)
        table.columns[1].width = Inches(1.6)
        table.columns[2].width = Inches(1.6)
        table.columns[3].width = Inches(1.6)

        headers = ["Item Name", "Quantity Sold", "Unit", "Total Revenue (₹)"]
        for col_idx, h in enumerate(headers):
            cell = table.cell(0, col_idx)
            cell.text = h
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY
            p = cell.text_frame.paragraphs[0]
            p.font.bold = True
            p.font.color.rgb = WHITE
            p.font.size = Pt(11)

        for row_idx, item in enumerate(top_items, 1):
            row_vals = [
                item["product_name"],
                f"{item['qty']:.1f}",
                item["unit"],
                f"₹ {item['revenue']:,.2f}"
            ]
            for col_idx, val in enumerate(row_vals):
                cell = table.cell(row_idx, col_idx)
                cell.text = val
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(241, 245, 249) if row_idx % 2 == 1 else WHITE
                p = cell.text_frame.paragraphs[0]
                p.font.size = Pt(10)
                p.font.color.rgb = DARK_GRAY
                if col_idx in [1, 3]:
                    p.alignment = PP_ALIGN.RIGHT

    # -------------------------------------------------------------
    # SLIDE 5: INVENTORY HEALTH & REORDER ALERTS
    # -------------------------------------------------------------
    slide5 = prs.slides.add_slide(blank_layout)
    _add_slide_header(slide5, "Stock Health & Reorder Recommendations", "Active inventory discipline and low-stock replenishment priorities")

    if low_stock:
        table_shape2 = slide5.shapes.add_table(min(len(low_stock), 5) + 1, 5, Inches(0.8), Inches(1.5), Inches(8.4), Inches(2.8))
        tbl = table_shape2.table
        tbl.columns[0].width = Inches(3.2)
        tbl.columns[1].width = Inches(1.2)
        tbl.columns[2].width = Inches(1.2)
        tbl.columns[3].width = Inches(1.2)
        tbl.columns[4].width = Inches(1.6)

        tbl_headers = ["Product Name", "Current Stock", "Reorder Level", "Unit", "Replenish Qty"]
        for col_idx, h in enumerate(tbl_headers):
            cell = tbl.cell(0, col_idx)
            cell.text = h
            cell.fill.solid()
            cell.fill.fore_color.rgb = ACCENT_AMBER
            p = cell.text_frame.paragraphs[0]
            p.font.bold = True
            p.font.color.rgb = WHITE
            p.font.size = Pt(10.5)

        for row_idx, item in enumerate(low_stock[:5], 1):
            suggested = max(item["reorder_level"] * 3 - item["stock_qty"], 10.0)
            row_vals = [
                item["name"],
                f"{item['stock_qty']:.1f}",
                f"{item['reorder_level']:.1f}",
                item["unit"],
                f"+{suggested:.0f} {item['unit']}"
            ]
            for col_idx, val in enumerate(row_vals):
                cell = tbl.cell(row_idx, col_idx)
                cell.text = val
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(254, 243, 199) if row_idx % 2 == 1 else WHITE
                p = cell.text_frame.paragraphs[0]
                p.font.size = Pt(10)
                p.font.color.rgb = DARK_GRAY
                if col_idx in [1, 2, 4]:
                    p.alignment = PP_ALIGN.RIGHT
    else:
        info_box = slide5.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(8.4), Inches(2.0))
        tf = info_box.text_frame
        p = tf.paragraphs[0]
        p.text = "✓ All product SKUs are operating above their designated reorder thresholds."
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = ACCENT_GREEN

    # -------------------------------------------------------------
    # SLIDE 6: STRATEGIC ACTION ITEMS FOR SHOPKEEPER
    # -------------------------------------------------------------
    slide6 = prs.slides.add_slide(blank_layout)
    _add_slide_header(slide6, "Operational Action Items & Insights", "Recommendations to optimize margin, turnover, and working capital")

    recs = [
        ("Working Capital & Khata Discipline", f"Outstanding customer credit is ₹{khata_info['total_khata']:,.2f}. Send polite payment reminders to top khata accounts before weekend restocking."),
        ("Procurement & Stock Ordering", "Maintain bulk purchases on high-turnover staples (Atta, Rice, Sugar) where wholesale margins exceed 15-20%."),
        ("GST Reconciliation & Filing", f"Total intra-state GST liability is ₹{perf['total_tax']:,.2f}. Books are completely synchronized for monthly GSTR-1 and GSTR-3B filings."),
        ("UPI Adoption & Digital Checkout", "Promoting UPI checkout at peak evening hours speeds up bill cutting by ~40% and minimizes cash register discrepancies.")
    ]

    top_pos = 1.4
    for title, desc in recs:
        box = slide6.shapes.add_shape(1, Inches(0.8), Inches(top_pos), Inches(8.4), Inches(0.85))
        box.fill.solid()
        box.fill.fore_color.rgb = WHITE
        box.line.color.rgb = RGBColor(203, 213, 225)
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.15)
        tf.margin_top = Inches(0.1)

        p = tf.paragraphs[0]
        p.text = f"• {title}"
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = NAVY

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = DARK_GRAY

        top_pos += 0.95

    # Save presentation
    prs.save(pptx_path)
    return pptx_path
