-- SQLite Schema for Indian Supermarket Ops Agent

PRAGMA foreign_keys = ON;

-- Products / SKU Catalog
CREATE TABLE IF NOT EXISTS products (
    sku_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    unit TEXT NOT NULL,          -- kg, g, litre, ml, packet, piece, dozen
    is_loose INTEGER NOT NULL DEFAULT 0, -- 1 = loose (sold by weight/vol), 0 = packaged
    cost_price REAL NOT NULL,
    mrp REAL NOT NULL,
    sell_price REAL NOT NULL,
    stock_qty REAL NOT NULL CHECK(stock_qty >= 0),
    reorder_level REAL NOT NULL DEFAULT 5.0,
    hsn_code TEXT NOT NULL,
    gst_rate REAL NOT NULL DEFAULT 0.0, -- 0.0, 0.05, 0.12, 0.18, 0.28
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Bills / Sales Invoices
CREATE TABLE IF NOT EXISTS bills (
    bill_id TEXT PRIMARY KEY,
    bill_number TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'finalized', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMP,
    customer_name TEXT,
    customer_phone TEXT,
    payment_mode TEXT DEFAULT 'cash' CHECK(payment_mode IN ('cash', 'upi', 'card', 'khata')),
    payment_ref TEXT,
    subtotal REAL NOT NULL DEFAULT 0.0,
    cgst_amount REAL NOT NULL DEFAULT 0.0,
    sgst_amount REAL NOT NULL DEFAULT 0.0,
    total_tax REAL NOT NULL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    round_off REAL NOT NULL DEFAULT 0.0,
    rounded_total REAL NOT NULL DEFAULT 0.0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status);
CREATE INDEX IF NOT EXISTS idx_bills_created_at ON bills(created_at);

-- Bill Line Items
CREATE TABLE IF NOT EXISTS bill_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id TEXT NOT NULL REFERENCES bills(bill_id) ON DELETE CASCADE,
    sku_id TEXT NOT NULL REFERENCES products(sku_id),
    product_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL,
    cost_price REAL NOT NULL,
    hsn_code TEXT NOT NULL,
    gst_rate REAL NOT NULL,
    taxable_value REAL NOT NULL,
    cgst REAL NOT NULL,
    sgst REAL NOT NULL,
    total_price REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bill_items_bill_id ON bill_items(bill_id);

-- Khata Customers
CREATE TABLE IF NOT EXISTS khata_customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL COLLATE NOCASE,
    phone TEXT,
    balance REAL NOT NULL DEFAULT 0.0, -- Positive means customer owes store
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_khata_customers_name ON khata_customers(name);

-- Khata Ledger Transactions
CREATE TABLE IF NOT EXISTS khata_ledger (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL COLLATE NOCASE,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('debit', 'credit')), -- debit = credit purchase (+owed), credit = payment made (-owed)
    amount REAL NOT NULL CHECK(amount > 0),
    balance_after REAL NOT NULL,
    reference_bill_id TEXT,
    payment_mode TEXT DEFAULT 'cash',
    notes TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_khata_ledger_customer ON khata_ledger(customer_name);

-- Stock Movement Audit Ledger
CREATE TABLE IF NOT EXISTS stock_ledger (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL REFERENCES products(sku_id),
    entry_type TEXT NOT NULL CHECK(entry_type IN ('stock_in', 'sale', 'adjustment', 'return')),
    qty_change REAL NOT NULL,
    stock_after REAL NOT NULL,
    cost_price REAL,
    mrp REAL,
    reference_id TEXT,
    notes TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Owner Preferences (Durable Memory outside context window)
CREATE TABLE IF NOT EXISTS owner_preferences (
    key TEXT PRIMARY KEY COLLATE NOCASE,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Session State (Persisted active bill & conversation session)
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id TEXT PRIMARY KEY,
    active_bill_id TEXT,
    history_json TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Idempotency Registry (Prevents double billing / double stock receiving on retried webhooks)
CREATE TABLE IF NOT EXISTS idempotency_log (
    idempotency_key TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
