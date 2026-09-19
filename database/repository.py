"""
Repository layer enforcing business rules, atomic stock updates, oversell guards,
idempotency, and khata financial integrity.
"""
import json
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from database.db import get_connection
from core.gst_engine import GSTEngine, InvoiceTaxSummary

class OversellError(Exception):
    """Raised when an attempt is made to sell more items than in stock."""
    pass

class GuardrailError(Exception):
    """Raised when a business constraint is violated (e.g. selling below cost, settling non-existent khata)."""
    pass

class StoreRepository:
    """Encapsulates all database operations with transactional guarantees."""

    @staticmethod
    def normalize_unit(qty: float, unit_str: Optional[str], product_unit: str) -> float:
        """
        Normalizes quantity if user requested in grams or ml when stock is in kg or litres.
        e.g., 500g loose sugar from kg stock -> 0.5 kg.
        """
        if not unit_str:
            return qty
        unit_str = unit_str.strip().lower()
        product_unit = product_unit.strip().lower()

        if unit_str in ["g", "gm", "gram", "grams"] and product_unit in ["kg", "kilogram"]:
            return qty / 1000.0
        if unit_str in ["ml", "millilitre"] and product_unit in ["l", "litre", "liter"]:
            return qty / 1000.0
        return qty

    # --- Idempotency ---
    @staticmethod
    def get_idempotent_result(key: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT result_json FROM idempotency_log WHERE idempotency_key = ?;", (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["result_json"])
        return None

    @staticmethod
    def save_idempotent_result(key: str, action: str, result: Dict[str, Any]):
        conn = get_connection()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO idempotency_log (idempotency_key, action, result_json)
                VALUES (?, ?, ?);
            """, (key, action, json.dumps(result)))

    # --- Products & Inventory ---
    @staticmethod
    def search_products(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        query_pattern = f"%{query.strip()}%"
        if category:
            cursor.execute("""
                SELECT * FROM products 
                WHERE (name LIKE ? OR brand LIKE ? OR category LIKE ?)
                AND category LIKE ?
                ORDER BY name ASC;
            """, (query_pattern, query_pattern, query_pattern, f"%{category.strip()}%"))
        else:
            cursor.execute("""
                SELECT * FROM products 
                WHERE name LIKE ? OR brand LIKE ? OR category LIKE ?
                ORDER BY name ASC;
            """, (query_pattern, query_pattern, query_pattern))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_product(sku_or_name: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        # Direct SKU match
        cursor.execute("SELECT * FROM products WHERE sku_id = ? COLLATE NOCASE;", (sku_or_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        # Exact Name match
        cursor.execute("SELECT * FROM products WHERE name = ? COLLATE NOCASE;", (sku_or_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        # Partial match
        cursor.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1;", (f"%{sku_or_name}%",))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    @staticmethod
    def get_low_stock_items() -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM products 
            WHERE stock_qty <= reorder_level 
            ORDER BY (stock_qty / reorder_level) ASC;
        """)
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def receive_stock(
        sku_or_name: str,
        quantity: float,
        cost_price: Optional[float] = None,
        mrp: Optional[float] = None,
        sell_price: Optional[float] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Atomically increments stock and records stock ledger entry."""
        if idempotency_key:
            cached = StoreRepository.get_idempotent_result(idempotency_key)
            if cached:
                return cached

        conn = get_connection()
        with conn:
            # Immediate transaction for concurrency
            cursor = conn.cursor()
            product = StoreRepository.get_product(sku_or_name)
            if not product:
                raise GuardrailError(f"Product '{sku_or_name}' not found in catalog. Please add it first.")

            sku_id = product["sku_id"]
            new_cost = cost_price if cost_price is not None else product["cost_price"]
            new_mrp = mrp if mrp is not None else product["mrp"]
            new_sell = sell_price if sell_price is not None else (new_mrp if mrp else product["sell_price"])

            cursor.execute("""
                UPDATE products
                SET stock_qty = stock_qty + ?,
                    cost_price = ?,
                    mrp = ?,
                    sell_price = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE sku_id = ?;
            """, (quantity, new_cost, new_mrp, new_sell, sku_id))

            cursor.execute("SELECT stock_qty FROM products WHERE sku_id = ?;", (sku_id,))
            updated_stock = cursor.fetchone()["stock_qty"]

            cursor.execute("""
                INSERT INTO stock_ledger (sku_id, entry_type, qty_change, stock_after, cost_price, mrp, notes)
                VALUES (?, 'stock_in', ?, ?, ?, ?, ?);
            """, (sku_id, quantity, updated_stock, new_cost, new_mrp, f"Received {quantity} {product['unit']}"))

            result = {
                "status": "success",
                "sku_id": sku_id,
                "name": product["name"],
                "quantity_added": quantity,
                "new_stock": updated_stock,
                "cost_price": new_cost,
                "mrp": new_mrp,
                "unit": product["unit"]
            }

            if idempotency_key:
                StoreRepository.save_idempotent_result(idempotency_key, "receive_stock", result)

            return result

    @staticmethod
    def add_product(
        name: str,
        unit: str,
        cost_price: float,
        mrp: float,
        sell_price: Optional[float] = None,
        gst_rate: float = 0.0,
        hsn_code: str = "9999",
        category: str = "General",
        brand: Optional[str] = None,
        is_loose: bool = False,
        initial_stock: float = 0.0,
        reorder_level: float = 5.0
    ) -> Dict[str, Any]:
        """Registers a new SKU with price and tax slab validation."""
        sell_price = sell_price or mrp
        if sell_price < cost_price:
            raise GuardrailError(f"Guardrail violation: Sell price (₹{sell_price}) cannot be lower than cost price (₹{cost_price}).")

        # Generate a clean SKU code
        sku_clean = name.upper().replace(" ", "-")[:12]
        sku_id = f"SKU-{sku_clean}-{uuid.uuid4().hex[:4].upper()}"

        conn = get_connection()
        with conn:
            conn.execute("""
                INSERT INTO products (
                    sku_id, name, brand, category, unit, is_loose,
                    cost_price, mrp, sell_price, stock_qty, reorder_level,
                    hsn_code, gst_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sku_id, name, brand, category, unit, 1 if is_loose else 0,
                cost_price, mrp, sell_price, initial_stock, reorder_level,
                hsn_code, gst_rate
            ))

        return {
            "status": "success",
            "sku_id": sku_id,
            "name": name,
            "unit": unit,
            "cost_price": cost_price,
            "mrp": mrp,
            "sell_price": sell_price,
            "gst_rate": gst_rate,
            "stock_qty": initial_stock
        }

    # --- Billing & POS (Multi-turn draft & atomic finalize) ---
    @staticmethod
    def get_or_create_draft_bill(bill_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetches active draft bill or initializes a new draft bill."""
        conn = get_connection()
        cursor = conn.cursor()
        if bill_id:
            cursor.execute("SELECT * FROM bills WHERE bill_id = ? AND status = 'draft';", (bill_id,))
            row = cursor.fetchone()
            if row:
                return StoreRepository.get_full_bill(bill_id)

        # Generate new draft bill
        new_bill_id = str(uuid.uuid4())
        today_str = date.today().strftime("%Y%m%d")
        cursor.execute("SELECT COUNT(*) FROM bills WHERE bill_number LIKE ?;", (f"INV-{today_str}%",))
        seq = cursor.fetchone()[0] + 1
        bill_number = f"INV-{today_str}-{seq:04d}"

        with conn:
            conn.execute("""
                INSERT INTO bills (bill_id, bill_number, status, payment_mode)
                VALUES (?, ?, 'draft', 'cash');
            """, (new_bill_id, bill_number))

        return StoreRepository.get_full_bill(new_bill_id)

    @staticmethod
    def get_full_bill(bill_id: str) -> Dict[str, Any]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bills WHERE bill_id = ?;", (bill_id,))
        bill_row = cursor.fetchone()
        if not bill_row:
            raise ValueError(f"Bill with ID {bill_id} not found.")

        cursor.execute("SELECT * FROM bill_items WHERE bill_id = ? ORDER BY item_id ASC;", (bill_id,))
        items = [dict(r) for r in cursor.fetchall()]

        bill_dict = dict(bill_row)
        bill_dict["items"] = items
        return bill_dict

    @staticmethod
    def update_draft_bill_items(
        bill_id: str,
        items_to_add: Optional[List[Dict[str, Any]]] = None,
        items_to_remove: Optional[List[str]] = None,
        items_to_update: Optional[List[Dict[str, Any]]] = None,
        payment_mode: Optional[str] = None,
        customer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Modifies line items on a draft bill.
        NOTE: Does NOT decrement stock yet! Stock decrement only occurs upon finalize.
        """
        conn = get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM bills WHERE bill_id = ?;", (bill_id,))
            row = cursor.fetchone()
            if not row or row["status"] != "draft":
                raise GuardrailError("Cannot modify a bill that is already finalized or cancelled.")

            # Update customer / payment mode if specified
            if payment_mode:
                conn.execute("UPDATE bills SET payment_mode = ? WHERE bill_id = ?;", (payment_mode.lower(), bill_id))
            if customer_name:
                conn.execute("UPDATE bills SET customer_name = ? WHERE bill_id = ?;", (customer_name.strip(), bill_id))

            # Remove items
            if items_to_remove:
                for target in items_to_remove:
                    # Target can be sku_id or product name pattern
                    conn.execute("""
                        DELETE FROM bill_items 
                        WHERE bill_id = ? AND (sku_id = ? OR product_name LIKE ?);
                    """, (bill_id, target, f"%{target}%"))

            # Update items
            if items_to_update:
                for item in items_to_update:
                    target = item.get("sku_or_name", "")
                    new_qty = float(item.get("quantity", 1.0))
                    conn.execute("""
                        DELETE FROM bill_items 
                        WHERE bill_id = ? AND (sku_id = ? OR product_name LIKE ?);
                    """, (bill_id, target, f"%{target}%"))
                    # Re-add with new quantity
                    items_to_add = (items_to_add or []) + [{"sku_or_name": target, "quantity": new_qty, "unit": item.get("unit")}]

            # Add items
            if items_to_add:
                for item in items_to_add:
                    sku_or_name = item.get("sku_or_name", "")
                    requested_qty = float(item.get("quantity", 1.0))
                    requested_unit = item.get("unit")

                    product = StoreRepository.get_product(sku_or_name)
                    if not product:
                        raise GuardrailError(f"Item '{sku_or_name}' was not found in store database.")

                    normalized_qty = StoreRepository.normalize_unit(requested_qty, requested_unit, product["unit"])
                    
                    # Compute line GST and totals
                    rate = product["sell_price"]
                    gst_rate = product["gst_rate"]
                    line_tax = GSTEngine.calculate_line_item(normalized_qty, rate, gst_rate)

                    # Check if line item already exists on this draft bill -> aggregate
                    cursor.execute("""
                        SELECT item_id, quantity FROM bill_items 
                        WHERE bill_id = ? AND sku_id = ?;
                    """, (bill_id, product["sku_id"]))
                    existing = cursor.fetchone()
                    if existing:
                        combined_qty = existing["quantity"] + normalized_qty
                        recalc = GSTEngine.calculate_line_item(combined_qty, rate, gst_rate)
                        cursor.execute("""
                            UPDATE bill_items
                            SET quantity = ?,
                                taxable_value = ?,
                                cgst = ?,
                                sgst = ?,
                                total_price = ?
                            WHERE item_id = ?;
                        """, (combined_qty, recalc.taxable_value, recalc.cgst, recalc.sgst, recalc.line_total, existing["item_id"]))
                    else:
                        cursor.execute("""
                            INSERT INTO bill_items (
                                bill_id, sku_id, product_name, unit, quantity,
                                unit_price, cost_price, hsn_code, gst_rate,
                                taxable_value, cgst, sgst, total_price
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            bill_id, product["sku_id"], product["name"], product["unit"],
                            normalized_qty, rate, product["cost_price"], product["hsn_code"],
                            gst_rate, line_tax.taxable_value, line_tax.cgst, line_tax.sgst,
                            line_tax.line_total
                        ))

            # Recalculate bill header totals
            cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?;", (bill_id,))
            current_items = [dict(r) for r in cursor.fetchall()]
            summary = GSTEngine.calculate_invoice_summary(current_items)

            cursor.execute("""
                UPDATE bills
                SET subtotal = ?,
                    cgst_amount = ?,
                    sgst_amount = ?,
                    total_tax = ?,
                    grand_total = ?,
                    round_off = ?,
                    rounded_total = ?
                WHERE bill_id = ?;
            """, (
                summary.subtotal, summary.cgst_amount, summary.sgst_amount,
                summary.total_tax, summary.grand_total, summary.round_off,
                summary.rounded_total, bill_id
            ))

        return StoreRepository.get_full_bill(bill_id)

    @staticmethod
    def finalize_bill(
        bill_id: str,
        payment_mode: Optional[str] = None,
        payment_ref: Optional[str] = None,
        customer_name: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomically commits the bill, enforces oversell guard at the DB level,
        decrements stock atomically, records Khata if credit, and logs idempotency.
        """
        if idempotency_key:
            cached = StoreRepository.get_idempotent_result(idempotency_key)
            if cached:
                return cached

        conn = get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bills WHERE bill_id = ?;", (bill_id,))
            bill_row = cursor.fetchone()
            if not bill_row:
                raise GuardrailError(f"Bill ID '{bill_id}' does not exist.")

            if bill_row["status"] == "finalized":
                # Already finalized — return existing bill (idempotent safety)
                return StoreRepository.get_full_bill(bill_id)

            cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?;", (bill_id,))
            items = [dict(r) for r in cursor.fetchall()]
            if not items:
                raise GuardrailError("Cannot finalize an empty bill with no items.")

            # --- 1. OVERSELL GUARD (Enforced at DB Layer) ---
            # Verify stock for every item before making any modifications
            for item in items:
                cursor.execute("SELECT name, stock_qty, unit FROM products WHERE sku_id = ?;", (item["sku_id"],))
                prod = cursor.fetchone()
                if not prod:
                    raise GuardrailError(f"Product {item['product_name']} does not exist in store inventory.")
                
                avail = prod["stock_qty"]
                req = item["quantity"]
                if req > avail:
                    raise OversellError(
                        f"OVERSELL REFUSED: Insufficient stock for '{prod['name']}'. "
                        f"Requested: {req} {prod['unit']}, Available: {avail} {prod['unit']}. "
                        f"Stock cannot go negative."
                    )

            # --- 2. ATOMIC STOCK DECREMENT ---
            for item in items:
                cursor.execute("""
                    UPDATE products 
                    SET stock_qty = stock_qty - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE sku_id = ? AND stock_qty >= ?;
                """, (item["quantity"], item["sku_id"], item["quantity"]))

                if cursor.rowcount == 0:
                    # Concurrency collision: another sale decremented stock concurrently
                    raise OversellError(
                        f"CONCURRENCY COLLISION: Stock changed during checkout for '{item['product_name']}'. "
                        "Cannot fulfill requested quantity."
                    )

                cursor.execute("SELECT stock_qty FROM products WHERE sku_id = ?;", (item["sku_id"],))
                stock_after = cursor.fetchone()["stock_qty"]

                cursor.execute("""
                    INSERT INTO stock_ledger (sku_id, entry_type, qty_change, stock_after, mrp, reference_id, notes)
                    VALUES (?, 'sale', ?, ?, ?, ?, ?);
                """, (item["sku_id"], -item["quantity"], stock_after, item["unit_price"], bill_row["bill_number"], f"Sold on {bill_row['bill_number']}"))

            # --- 3. KHATA HANDLING (If customer bought on credit) ---
            final_mode = (payment_mode or bill_row["payment_mode"] or "cash").lower()
            cust_name = customer_name or bill_row["customer_name"]

            if final_mode == "khata":
                if not cust_name:
                    raise GuardrailError("Khata (credit) billing requires a customer name.")
                
                # Check if customer exists in khata
                cursor.execute("SELECT customer_id, balance FROM khata_customers WHERE name = ? COLLATE NOCASE;", (cust_name.strip(),))
                cust = cursor.fetchone()
                if not cust:
                    # Auto-register new khata customer on credit sale
                    cursor.execute("INSERT INTO khata_customers (name, balance) VALUES (?, 0.0);", (cust_name.strip(),))
                    current_bal = 0.0
                else:
                    current_bal = cust["balance"]

                new_bal = round(current_bal + bill_row["rounded_total"], 2)
                cursor.execute("UPDATE khata_customers SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ? COLLATE NOCASE;", (new_bal, cust_name.strip()))
                cursor.execute("""
                    INSERT INTO khata_ledger (customer_name, entry_type, amount, balance_after, reference_bill_id, notes)
                    VALUES (?, 'debit', ?, ?, ?, ?);
                """, (cust_name.strip(), bill_row["rounded_total"], new_bal, bill_row["bill_number"], f"Bill {bill_row['bill_number']} charged to credit"))

            # --- 4. MARK BILL FINALIZED ---
            cursor.execute("""
                UPDATE bills 
                SET status = 'finalized',
                    finalized_at = CURRENT_TIMESTAMP,
                    payment_mode = ?,
                    payment_ref = ?,
                    customer_name = ?
                WHERE bill_id = ?;
            """, (final_mode, payment_ref, cust_name, bill_id))

        finalized_bill = StoreRepository.get_full_bill(bill_id)

        if idempotency_key:
            StoreRepository.save_idempotent_result(idempotency_key, "finalize_bill", finalized_bill)

        return finalized_bill

    # --- Khata (Customer Credit Ledger) ---
    @staticmethod
    def get_khata_customer(name: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM khata_customers WHERE name = ? COLLATE NOCASE;", (name.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_all_khatas() -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM khata_customers WHERE balance != 0.0 ORDER BY balance DESC;")
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def add_khata_credit(customer_name: str, amount: float, notes: Optional[str] = None) -> Dict[str, Any]:
        """Customer borrows money/goods on credit: adds to outstanding balance."""
        if amount <= 0:
            raise GuardrailError("Credit amount must be positive.")
        
        conn = get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM khata_customers WHERE name = ? COLLATE NOCASE;", (customer_name.strip(),))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO khata_customers (name, balance) VALUES (?, ?);", (customer_name.strip(), amount))
                new_balance = amount
            else:
                new_balance = round(row["balance"] + amount, 2)
                cursor.execute("UPDATE khata_customers SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ? COLLATE NOCASE;", (new_balance, customer_name.strip()))

            cursor.execute("""
                INSERT INTO khata_ledger (customer_name, entry_type, amount, balance_after, notes)
                VALUES (?, 'debit', ?, ?, ?);
            """, (customer_name.strip(), amount, new_balance, notes or "Credit added"))

        return {
            "status": "success",
            "customer_name": customer_name.strip(),
            "amount_added": amount,
            "new_balance": new_balance
        }

    @staticmethod
    def record_khata_settlement(customer_name: str, amount: float, payment_mode: str = "cash", notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Customer pays/settles credit.
        GUARDRAIL: Rejects settlement for non-existent customers!
        """
        if amount <= 0:
            raise GuardrailError("Payment amount must be greater than zero.")

        conn = get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT customer_id, balance FROM khata_customers WHERE name = ? COLLATE NOCASE;", (customer_name.strip(),))
            cust = cursor.fetchone()
            if not cust:
                raise GuardrailError(
                    f"GUARDRAIL REFUSAL: Customer '{customer_name}' does not have an active Khata account. "
                    "Cannot record settlement for a non-existent customer."
                )

            current_balance = cust["balance"]
            new_balance = round(current_balance - amount, 2)

            cursor.execute("""
                UPDATE khata_customers 
                SET balance = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE customer_id = ?;
            """, (new_balance, cust["customer_id"]))

            cursor.execute("""
                INSERT INTO khata_ledger (customer_name, entry_type, amount, balance_after, payment_mode, notes)
                VALUES (?, 'credit', ?, ?, ?, ?);
            """, (customer_name.strip(), amount, new_balance, payment_mode, notes or "Khata repayment"))

        return {
            "status": "success",
            "customer_name": customer_name.strip(),
            "amount_paid": amount,
            "previous_balance": current_balance,
            "new_balance": new_balance,
            "payment_mode": payment_mode
        }

    # --- Analytics & Daily Close ---
    @staticmethod
    def get_daily_close_data(target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes total sales, tax collected (CGST + SGST), payment mode breakdown,
        and top selling items for today or specified date (YYYY-MM-DD).
        """
        day = target_date or date.today().strftime("%Y-%m-%d")
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                COUNT(*) as bill_count,
                COALESCE(SUM(subtotal), 0.0) as total_taxable,
                COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
                COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
                COALESCE(SUM(total_tax), 0.0) as total_tax,
                COALESCE(SUM(rounded_total), 0.0) as gross_sales
            FROM bills
            WHERE status = 'finalized' AND DATE(created_at) = DATE(?);
        """, (day,))
        totals = dict(cursor.fetchone())

        # Payment mode breakdown
        cursor.execute("""
            SELECT payment_mode, COUNT(*) as count, COALESCE(SUM(rounded_total), 0.0) as amount
            FROM bills
            WHERE status = 'finalized' AND DATE(created_at) = DATE(?)
            GROUP BY payment_mode;
        """, (day,))
        payments = [dict(r) for r in cursor.fetchall()]

        # Top 5 items sold
        cursor.execute("""
            SELECT bi.product_name, SUM(bi.quantity) as total_qty, bi.unit, SUM(bi.total_price) as total_revenue
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.bill_id
            WHERE b.status = 'finalized' AND DATE(b.created_at) = DATE(?)
            GROUP BY bi.sku_id
            ORDER BY total_revenue DESC
            LIMIT 5;
        """, (day,))
        top_items = [dict(r) for r in cursor.fetchall()]

        return {
            "date": day,
            "totals": totals,
            "payment_breakdown": payments,
            "top_items": top_items
        }

    # --- Durable Preferences (Outside context window) ---
    @staticmethod
    def set_preference(key: str, value: str):
        conn = get_connection()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO owner_preferences (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP);
            """, (key.strip().lower(), str(value).strip()))

    @staticmethod
    def get_preference(key: str, default: Optional[str] = None) -> Optional[str]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM owner_preferences WHERE key = ? COLLATE NOCASE;", (key.strip(),))
        row = cursor.fetchone()
        return row["value"] if row else default

    @staticmethod
    def get_all_preferences() -> Dict[str, str]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM owner_preferences;")
        return {r["key"]: r["value"] for r in cursor.fetchall()}
