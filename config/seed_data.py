"""
Seed data populated with real Indian Kirana SKUs, Khata accounts, and preferences.
"""
from database.db import get_db_cursor
from config.settings import (
    DEFAULT_SHOP_NAME,
    DEFAULT_SHOP_ADDRESS,
    DEFAULT_SHOP_GSTIN
)

INITIAL_PRODUCTS = [
    {
        "sku_id": "SKU-ATTA-01",
        "name": "Aashirvaad Atta 5kg",
        "brand": "Aashirvaad",
        "category": "Staples",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 215.0,
        "mrp": 265.0,
        "sell_price": 255.0,
        "stock_qty": 20.0,
        "reorder_level": 5.0,
        "hsn_code": "1101",
        "gst_rate": 0.05
    },
    {
        "sku_id": "SKU-ATTA-LOOSE",
        "name": "Loose Chakki Atta",
        "brand": "Local",
        "category": "Staples",
        "unit": "kg",
        "is_loose": 1,
        "cost_price": 32.0,
        "mrp": 42.0,
        "sell_price": 40.0,
        "stock_qty": 100.0,
        "reorder_level": 25.0,
        "hsn_code": "1101",
        "gst_rate": 0.00
    },
    {
        "sku_id": "SKU-SALT-01",
        "name": "Tata Salt 1kg",
        "brand": "Tata",
        "category": "Staples",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 22.0,
        "mrp": 28.0,
        "sell_price": 28.0,
        "stock_qty": 40.0,
        "reorder_level": 10.0,
        "hsn_code": "2501",
        "gst_rate": 0.05
    },
    {
        "sku_id": "SKU-SUGAR-LOOSE",
        "name": "Loose Sugar",
        "brand": "Local",
        "category": "Staples",
        "unit": "kg",
        "is_loose": 1,
        "cost_price": 38.0,
        "mrp": 46.0,
        "sell_price": 44.0,
        "stock_qty": 85.0,
        "reorder_level": 20.0,
        "hsn_code": "1701",
        "gst_rate": 0.00
    },
    {
        "sku_id": "SKU-BUTTER-01",
        "name": "Amul Butter 100g",
        "brand": "Amul",
        "category": "Dairy",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 50.0,
        "mrp": 62.0,
        "sell_price": 60.0,
        "stock_qty": 25.0,
        "reorder_level": 8.0,
        "hsn_code": "0405",
        "gst_rate": 0.12
    },
    {
        "sku_id": "SKU-OIL-01",
        "name": "Fortune Sunflower Oil 1L",
        "brand": "Fortune",
        "category": "Oils",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 125.0,
        "mrp": 150.0,
        "sell_price": 145.0,
        "stock_qty": 30.0,
        "reorder_level": 6.0,
        "hsn_code": "1512",
        "gst_rate": 0.05
    },
    {
        "sku_id": "SKU-MAGGI-01",
        "name": "Maggi 70g",
        "brand": "Nestle",
        "category": "Instant Food",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 11.5,
        "mrp": 14.0,
        "sell_price": 14.0,
        "stock_qty": 50.0,
        "reorder_level": 15.0,
        "hsn_code": "1902",
        "gst_rate": 0.18
    },
    {
        "sku_id": "SKU-PARLEG-01",
        "name": "Parle-G 250g",
        "brand": "Parle",
        "category": "Biscuits",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 25.0,
        "mrp": 30.0,
        "sell_price": 30.0,
        "stock_qty": 35.0,
        "reorder_level": 10.0,
        "hsn_code": "1905",
        "gst_rate": 0.18
    },
    {
        "sku_id": "SKU-SURF-01",
        "name": "Surf Excel 1kg",
        "brand": "Surf Excel",
        "category": "Household & Cleaning",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 120.0,
        "mrp": 145.0,
        "sell_price": 140.0,
        "stock_qty": 15.0,
        "reorder_level": 5.0,
        "hsn_code": "3402",
        "gst_rate": 0.18
    },
    {
        "sku_id": "SKU-RICE-LOOSE",
        "name": "Loose Basmati Rice",
        "brand": "Local",
        "category": "Staples",
        "unit": "kg",
        "is_loose": 1,
        "cost_price": 75.0,
        "mrp": 95.0,
        "sell_price": 90.0,
        "stock_qty": 60.0,
        "reorder_level": 15.0,
        "hsn_code": "1006",
        "gst_rate": 0.00
    },
    {
        "sku_id": "SKU-DAL-LOOSE",
        "name": "Loose Toor Dal",
        "brand": "Local",
        "category": "Staples",
        "unit": "kg",
        "is_loose": 1,
        "cost_price": 130.0,
        "mrp": 165.0,
        "sell_price": 160.0,
        "stock_qty": 40.0,
        "reorder_level": 10.0,
        "hsn_code": "0713",
        "gst_rate": 0.00
    },
    {
        "sku_id": "SKU-SOAP-01",
        "name": "Dettol Soap 75g",
        "brand": "Dettol",
        "category": "Personal Care",
        "unit": "piece",
        "is_loose": 0,
        "cost_price": 32.0,
        "mrp": 40.0,
        "sell_price": 38.0,
        "stock_qty": 30.0,
        "reorder_level": 8.0,
        "hsn_code": "3401",
        "gst_rate": 0.18
    },
    {
        "sku_id": "SKU-MILK-01",
        "name": "Amul Taaza Milk 500ml",
        "brand": "Amul",
        "category": "Dairy",
        "unit": "packet",
        "is_loose": 0,
        "cost_price": 25.0,
        "mrp": 28.0,
        "sell_price": 28.0,
        "stock_qty": 20.0,
        "reorder_level": 6.0,
        "hsn_code": "0401",
        "gst_rate": 0.05
    }
]

INITIAL_KHATA_CUSTOMERS = [
    {
        "name": "Ramesh",
        "phone": "9876543210",
        "balance": 1200.0,
        "initial_entry": "Monthly grocery credit balance"
    },
    {
        "name": "Suresh",
        "phone": "9812345678",
        "balance": 350.0,
        "initial_entry": "Previous week dairy credit"
    },
    {
        "name": "Priya",
        "phone": "9900112233",
        "balance": 0.0,
        "initial_entry": "Regular customer account"
    }
]

INITIAL_PREFERENCES = {
    "shop_name": DEFAULT_SHOP_NAME,
    "shop_address": DEFAULT_SHOP_ADDRESS,
    "shop_gstin": DEFAULT_SHOP_GSTIN,
    "default_payment_mode": "UPI",
    "default_atta": "Aashirvaad Atta 5kg"
}

def seed_database():
    """Populates products, customers, and default preferences if table is empty."""
    with get_db_cursor() as cursor:
        # Check if products already seeded
        cursor.execute("SELECT COUNT(*) FROM products;")
        count = cursor.fetchone()[0]
        if count == 0:
            for p in INITIAL_PRODUCTS:
                cursor.execute("""
                    INSERT INTO products (
                        sku_id, name, brand, category, unit, is_loose,
                        cost_price, mrp, sell_price, stock_qty, reorder_level,
                        hsn_code, gst_rate
                    ) VALUES (
                        :sku_id, :name, :brand, :category, :unit, :is_loose,
                        :cost_price, :mrp, :sell_price, :stock_qty, :reorder_level,
                        :hsn_code, :gst_rate
                    )
                """, p)

        # Check if customers seeded
        cursor.execute("SELECT COUNT(*) FROM khata_customers;")
        cust_count = cursor.fetchone()[0]
        if cust_count == 0:
            for c in INITIAL_KHATA_CUSTOMERS:
                cursor.execute("""
                    INSERT INTO khata_customers (name, phone, balance)
                    VALUES (:name, :phone, :balance)
                """, c)
                if c["balance"] > 0:
                    cursor.execute("""
                        INSERT INTO khata_ledger (customer_name, entry_type, amount, balance_after, notes)
                        VALUES (?, 'debit', ?, ?, ?)
                    """, (c["name"], c["balance"], c["balance"], c["initial_entry"]))

        # Seed preferences
        for k, v in INITIAL_PREFERENCES.items():
            cursor.execute("""
                INSERT OR IGNORE INTO owner_preferences (key, value)
                VALUES (?, ?)
            """, (k, str(v)))
