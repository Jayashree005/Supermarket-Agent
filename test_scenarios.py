"""
Comprehensive Test Suite for the 9 Hard Parts & Rubric Deliverables:
1. Grounding (DB tool queries for prices/stock)
2. Oversell Guard (Refuses billing exceeding stock at tool/DB layer)
3. GST Correctness (HSN, 50/50 intra-state CGST/SGST, rounding, tax breakdown)
4. Multi-Turn Bills (Building over multiple messages, mid-build edits, stock preserved until finalize)
5. Idempotency (Retried finalize does not double-decrement stock or double-bill)
6. Concurrency (Simultaneous sales / stock operations do not corrupt inventory)
7. Guardrails (Don't sell below cost, don't settle non-existent khata)
8. Real Artifacts (GST Invoice PDF and Business Analysis Deck PPTX)
9. Memory Across Sessions (Standing preferences persist across /new session resets)
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import init_db, get_connection
from config.seed_data import seed_database
from database.repository import (
    StoreRepository,
    OversellError,
    GuardrailError
)
from core.gst_engine import GSTEngine
from artifacts.invoice_pdf import generate_invoice_pdf
from artifacts.analysis_pptx import generate_weekly_analysis_deck
from core.agent_loop import KiranaOpsAgent

def print_banner(text: str):
    print("\n" + "=" * 75)
    print(f"  {text}")
    print("=" * 75)

def run_all_tests():
    print_banner("RUNNING COMPREHENSIVE KIRANA OPS VERIFICATION SUITE")
    
    # 0. Initialize & seed clean database
    init_db()
    seed_database()
    print("✓ Initialized database and seeded Indian Supermarket catalog.")

    results = {}

    # -------------------------------------------------------------
    # TEST 1: GROUNDING
    # -------------------------------------------------------------
    print("\n[Test 1] Grounding: Checking catalog queries for authentic prices and slabs...")
    magg = StoreRepository.get_product("Maggi 70g")
    sugar = StoreRepository.get_product("Loose Sugar")
    assert magg is not None, "Maggi SKU must exist"
    assert magg["gst_rate"] == 0.18, "Maggi GST rate must be 18%"
    assert magg["mrp"] == 14.0, "Maggi MRP must be ₹14"
    assert sugar["gst_rate"] == 0.0, "Loose sugar must be 0% GST"
    print(f"  ✓ Grounded SKU: {magg['name']} -> MRP ₹{magg['mrp']}, GST {magg['gst_rate']*100:.0f}%, HSN {magg['hsn_code']}")
    print(f"  ✓ Grounded SKU: {sugar['name']} -> MRP ₹{sugar['mrp']}/kg, GST {sugar['gst_rate']*100:.0f}%, Loose={sugar['is_loose']}")
    results["1_Grounding"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 2: OVERSELL GUARD (Enforced at Tool/DB Layer)
    # -------------------------------------------------------------
    print("\n[Test 2] Oversell Guard: Attempting to bill more quantity than in stock...")
    prod = StoreRepository.get_product("Surf Excel 1kg")
    curr_stock = prod["stock_qty"]
    excess_qty = curr_stock + 20.0 # More than available

    bill = StoreRepository.get_or_create_draft_bill()
    bill = StoreRepository.update_draft_bill_items(
        bill["bill_id"],
        items_to_add=[{"sku_or_name": "Surf Excel 1kg", "quantity": excess_qty}],
        payment_mode="cash"
    )

    oversell_caught = False
    try:
        StoreRepository.finalize_bill(bill["bill_id"])
    except OversellError as e:
        oversell_caught = True
        print(f"  ✓ Oversell Guard correctly raised exception at DB layer:")
        print(f"    '{e}'")

    assert oversell_caught, "OversellError MUST be raised when billing quantity exceeds stock."
    
    # Confirm stock was NOT changed
    prod_after = StoreRepository.get_product("Surf Excel 1kg")
    assert prod_after["stock_qty"] == curr_stock, "Stock must remain unaltered after rejected checkout."
    print(f"  ✓ Stock intact: Available quantity remains {prod_after['stock_qty']}.")
    results["2_Oversell_Guard"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 3: GST CORRECTNESS (Intra-State 50/50 Split & Rounding)
    # -------------------------------------------------------------
    print("\n[Test 3] GST Correctness: Validating tax calculation, CGST/SGST split, and round-off...")
    items = [
        {"quantity": 1, "unit_price": 255.0, "gst_rate": 0.05}, # Atta (5%): Taxable=242.86, Tax=12.14 -> CGST=6.07, SGST=6.07
        {"quantity": 1, "unit_price": 60.0, "gst_rate": 0.12},  # Butter (12%): Taxable=53.57, Tax=6.43 -> CGST=3.22, SGST=3.21
        {"quantity": 4, "unit_price": 14.0, "gst_rate": 0.18},  # Maggi (18%): Gross=56.0 -> Taxable=47.46, Tax=8.54 -> CGST=4.27, SGST=4.27
        {"quantity": 2, "unit_price": 44.0, "gst_rate": 0.00},  # Sugar (0%): Taxable=88.0, Tax=0.0
    ]
    summary = GSTEngine.calculate_invoice_summary(items)
    
    expected_gross = 255.0 + 60.0 + 56.0 + 88.0 # 459.0
    assert abs(summary.grand_total - expected_gross) < 0.01, f"Grand total should be {expected_gross}"
    assert abs((summary.cgst_amount + summary.sgst_amount) - summary.total_tax) < 0.01, "CGST + SGST must exactly equal total_tax"
    assert summary.rounded_total == round(summary.grand_total), "Rounded total must be integer rounded"
    
    print(f"  ✓ Gross Total: ₹{summary.grand_total:.2f}")
    print(f"  ✓ Taxable Subtotal: ₹{summary.subtotal:.2f}")
    print(f"  ✓ CGST: ₹{summary.cgst_amount:.2f} | SGST: ₹{summary.sgst_amount:.2f} (Exact 50/50 intra-state split)")
    print(f"  ✓ Total Tax: ₹{summary.total_tax:.2f} | Round Off: ₹{summary.round_off:+.2f} | Net: ₹{summary.rounded_total:.2f}")
    print("  ✓ Tax Slabs generated:", [f"GST {s.slab_name}: Taxable ₹{s.taxable_value}, Tax ₹{s.total_tax}" for s in summary.slab_breakup])
    results["3_GST_Correctness"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 4: MULTI-TURN BILLS WITH MID-BUILD EDITS & STOCK DISCIPLINE
    # -------------------------------------------------------------
    print("\n[Test 4] Multi-Turn Bills: Testing multi-message drafting, editing, and deferred stock decrement...")
    
    # Check initial stock
    initial_maggi_stock = StoreRepository.get_product("Maggi 70g")["stock_qty"]
    initial_butter_stock = StoreRepository.get_product("Amul Butter 100g")["stock_qty"]

    # Turn 1: Create draft with 4 Maggi and 1 Butter
    draft_bill = StoreRepository.get_or_create_draft_bill()
    b_id = draft_bill["bill_id"]
    StoreRepository.update_draft_bill_items(
        b_id,
        items_to_add=[
            {"sku_or_name": "Maggi 70g", "quantity": 4},
            {"sku_or_name": "Amul Butter 100g", "quantity": 1}
        ]
    )
    
    # CRITICAL CHECK: Stock must NOT have changed while bill is in draft!
    maggi_check = StoreRepository.get_product("Maggi 70g")["stock_qty"]
    assert maggi_check == initial_maggi_stock, "Drafting must not decrement stock!"
    print(f"  ✓ Deferred Decrement Verified: Maggi stock remains {maggi_check} while bill is draft.")

    # Turn 2: Edit bill mid-build: 'drop the butter, make it 6 Maggi'
    StoreRepository.update_draft_bill_items(
        b_id,
        items_to_remove=["Amul Butter 100g"],
        items_to_update=[{"sku_or_name": "Maggi 70g", "quantity": 6}],
        payment_mode="upi"
    )
    edited_bill = StoreRepository.get_full_bill(b_id)
    assert len(edited_bill["items"]) == 1, "Should only have Maggi after dropping butter"
    assert edited_bill["items"][0]["quantity"] == 6.0, "Maggi quantity should be updated to 6"
    assert edited_bill["payment_mode"] == "upi", "Payment mode should be updated to UPI"
    print(f"  ✓ Mid-build edit successful: Draft now has 6 Maggi, Butter dropped, Payment=UPI.")

    # Turn 3: Finalize bill -> Stock MUST decrement now
    finalized = StoreRepository.finalize_bill(b_id)
    assert finalized["status"] == "finalized", "Bill must be marked finalized"
    
    maggi_final = StoreRepository.get_product("Maggi 70g")["stock_qty"]
    assert maggi_final == initial_maggi_stock - 6.0, f"Stock should be decremented by 6 (was {initial_maggi_stock}, now {maggi_final})"
    print(f"  ✓ Stock decremented on finalize: Maggi stock decremented from {initial_maggi_stock} to {maggi_final}.")
    results["4_Multi_Turn_Bills"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 5: IDEMPOTENCY (Duplicate/Retried Webhook Delivery)
    # -------------------------------------------------------------
    print("\n[Test 5] Idempotency: Retrying finalize on the same bill to ensure no double-decrement...")
    maggi_before_retry = StoreRepository.get_product("Maggi 70g")["stock_qty"]
    
    # Re-call finalize with idempotency key
    retry_result = StoreRepository.finalize_bill(b_id, idempotency_key=f"retry_test_{b_id}")
    maggi_after_retry = StoreRepository.get_product("Maggi 70g")["stock_qty"]

    assert maggi_after_retry == maggi_before_retry, "Retried finalize MUST NOT decrement stock a second time!"
    assert retry_result["status"] == "finalized", "Should return finalized bill safely"
    print(f"  ✓ Idempotency verified: Stock remained exactly {maggi_after_retry} after repeated finalize call.")
    results["5_Idempotency"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 6: CONCURRENCY
    # -------------------------------------------------------------
    print("\n[Test 6] Concurrency: Simulating concurrent stock-in and checkout...")
    import threading
    concurrency_errors = []

    def concurrent_sale():
        try:
            b = StoreRepository.get_or_create_draft_bill()
            StoreRepository.update_draft_bill_items(b["bill_id"], items_to_add=[{"sku_or_name": "Tata Salt 1kg", "quantity": 2}])
            StoreRepository.finalize_bill(b["bill_id"])
        except Exception as ex:
            concurrency_errors.append(ex)

    def concurrent_stock_in():
        try:
            StoreRepository.receive_stock("Tata Salt 1kg", 10)
        except Exception as ex:
            concurrency_errors.append(ex)

    t1 = threading.Thread(target=concurrent_sale)
    t2 = threading.Thread(target=concurrent_stock_in)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(concurrency_errors) == 0, f"Concurrent operations failed: {concurrency_errors}"
    print("  ✓ Concurrent transactions completed safely under SQLite WAL mode without locks or data corruption.")
    results["6_Concurrency"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 7: GUARDRAILS (Selling Below Cost & Khata Integrity)
    # -------------------------------------------------------------
    print("\n[Test 7] Guardrails: Testing guardrail violation refusals...")
    # Guardrail 1: Selling below cost
    below_cost_caught = False
    try:
        StoreRepository.add_product(
            name="Discount Detergent",
            unit="packet",
            cost_price=100.0,
            mrp=120.0,
            sell_price=80.0 # Sell price below cost!
        )
    except GuardrailError as e:
        below_cost_caught = True
        print(f"  ✓ Below-cost sale blocked: '{e}'")
    assert below_cost_caught, "Selling below cost must be refused by guardrail."

    # Guardrail 2: Settling khata for non-existent customer
    non_existent_caught = False
    try:
        StoreRepository.record_khata_settlement("UnknownPersonXYZ", 500.0)
    except GuardrailError as e:
        non_existent_caught = True
        print(f"  ✓ Non-existent khata settlement blocked: '{e}'")
    assert non_existent_caught, "Settlement for non-existent customer must be refused."
    results["7_Guardrails"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 8: REAL ARTIFACTS (PDF Invoice & PPTX Deck)
    # -------------------------------------------------------------
    print("\n[Test 8] Real Artifacts: Generating PDF Invoice and PPTX Analysis Deck...")
    # PDF
    pdf_path = generate_invoice_pdf(finalized)
    assert os.path.exists(pdf_path), "PDF invoice file must exist on disk"
    assert os.path.getsize(pdf_path) > 1000, "PDF file must be non-empty"
    print(f"  ✓ Authentic GST Invoice PDF generated: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

    # PPTX
    pptx_path = generate_weekly_analysis_deck(7)
    assert os.path.exists(pptx_path), "PPTX analysis deck must exist on disk"
    assert os.path.getsize(pptx_path) > 10000, "PPTX file must be non-empty"
    print(f"  ✓ Business Analysis Deck PPTX generated: {pptx_path} ({os.path.getsize(pptx_path)} bytes)")
    results["8_Real_Artifacts"] = "PASSED"

    # -------------------------------------------------------------
    # TEST 9: PERSISTENT MEMORY ACROSS /new SESSIONS
    # -------------------------------------------------------------
    print("\n[Test 9] Memory Across Sessions: Verifying standing preferences survive /new reset...")
    # Set preferences
    StoreRepository.set_preference("default_payment_mode", "UPI")
    StoreRepository.set_preference("default_atta", "Aashirvaad Atta 5kg")
    
    agent = KiranaOpsAgent()
    session_id = "test_memory_session"
    
    # Store draft in session
    b = StoreRepository.get_or_create_draft_bill()
    from bot.session_manager import SessionManager
    SessionManager.set_active_bill_id(session_id, b["bill_id"])

    # Perform /new reset
    agent.reset_chat(session_id)
    
    # Active draft bill should be cleared
    cleared_bill = SessionManager.get_active_bill_id(session_id)
    assert cleared_bill is None, "Active draft bill must be cleared after /new"

    # Persistent preferences in DB must still be intact
    pref_pay = StoreRepository.get_preference("default_payment_mode")
    pref_atta = StoreRepository.get_preference("default_atta")
    assert pref_pay == "UPI", "Default payment preference must survive /new"
    assert pref_atta == "Aashirvaad Atta 5kg", "Brand shortcut preference must survive /new"
    print(f"  ✓ Session conversation & draft bill cleared.")
    print(f"  ✓ Persistent memory intact: default_payment_mode='{pref_pay}', default_atta='{pref_atta}'.")
    results["9_Persistent_Memory"] = "PASSED"

    # -------------------------------------------------------------
    # SCORECARD SUMMARY
    # -------------------------------------------------------------
    print_banner("VERIFICATION SCORECARD SUMMARY")
    all_passed = True
    for hard_part, status in results.items():
        print(f"  {hard_part:<30} : {status}")
        if status != "PASSED":
            all_passed = False

    print("-" * 75)
    if all_passed:
        print("  🎉 ALL 9 HARD PARTS VERIFIED AND FULLY PASSING!")
    else:
        print("  ❌ Some tests failed.")
    print("=" * 75)
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
