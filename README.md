# 🏬 Supermarket Operations Management System & Web Dashboard

> **Manage an entire supermarket operations workflow from a clean web dashboard and interactive assistant — powered by an autonomous ReAct agent.**

---

## 🌟 Key Highlights & Features

### 1. 🖥️ Clean Real-Time Web Dashboard (`run_web.py`)
- **Live Inventory & Stocks:** Complete SKU catalog with real-time stock levels, reorder thresholds, MRP, cost price, and GST slabs.
- **Bi-directional WebSocket Telemetry (`/ws`):** Any action taken in the chat (adding items, deleting items, receiving stock, finalizing bills, or recording credit payments) instantly updates the web UI and live event feed without page refreshes.
- **Embedded Store Assistant:** Built-in floating/docked chat panel where operators can manage tasks using plain English commands with one-click quick action chips.
- **Interactive Point of Sale (POS) & Draft Billing:** Visual multi-turn draft cart. Add or remove items via chat or UI buttons, inspect GST calculations (CGST/SGST), and finalize with oversell guards.
- **Customer Credit Ledger:** Real-time ledger of outstanding customer debt, payment settlements, and audit transaction log with business guardrails.
- **Artifact Downloads:** One-click viewing and downloading of authentic **GST Tax Invoices (PDF)** and **Executive Strategy Presentations (PPTX)**.
- **Store Preferences & Memory:** Configure durable preferences (e.g. `default_payment_mode = UPI`, `shop_name`, `default_flour`) that endure across restarts.

### 2. 🤖 Autonomous ReAct Agent Loop (`core/agent_loop.py`)

- **Agent-First Control Loop:** `Observe → Reason → Act (Tools) → Feed Back → Respond`.
- **Intelligent Tool Orchestration:** Automatically dispatches domain skills (`inventory_skill`, `billing_skill`, `khata_skill`, `analytics_skill`, `document_skill`, `memory_skill`).
- **Zero Hallucination:** Prices, stock levels, and calculations are strictly resolved against SQLite database records.
- **Rate-limit Resilience:** Automatic exponential backoff and fallback model switching when API limits are reached.

### 3. 🛡️ Industrial Business Logic & Guardrails

- **Oversell Guard:** Strict database-level transaction prevents stock from ever going negative. Unit-normalized quantities (e.g., 500g loose sugar from kg stock).
- **GST Compliance:** MRP tax-inclusive reverse calculations, intra-state 50/50 CGST & SGST splits, and round-off adjustments.
- **Pricing Safeguards:** Rejects any product registration where sell price is below cost price.
- **Khata Guardrails:** Rejects credit settlements for non-existent customers.
- **Idempotency Log:** Prevents duplicate billing or double stock receiving during network retries.

---

## 🚀 Quick Start Guide

### Prerequisites

- Python 3.10+
- Google Gemini API Key (`GEMINI_API_KEY`)

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone <repo-url>
cd Nebula-Supermarket-Agent
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the root directory (or copy from `.env.example`):

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
# Optional: TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### 3. Launch the Application

#### Option A: Web-Based UI & AI Copilot (Recommended)

Launch the FastAPI server and open your browser:

```bash
python run_web.py
```

Open **`http://localhost:8000`** in your browser to access the complete interactive dashboard.

#### Option B: Terminal CLI

Run the interactive shopkeeper terminal:

```bash
python run_cli.py
```

#### Option C: Telegram Bot

Run the Telegram bot daemon:

```bash
python run_bot.py
```

---

## 💬 Sample Conversations & Commands

You can speak to the agent in natural, terse shopkeeper English in either the **Web Copilot**, **Terminal**, or **Telegram**:

### 1. Stock Checks & Inquiries

- **User:** `how much sugar is left?`**Agent:** `Loose Sugar: 80 kg in stock (₹44/kg).`
- **User:** `what's running out?`
  **Agent:** `Low stock alerts: Amul Butter 100g (3 packets left, reorder at 5).`

### 2. Multi-Turn Billing & Mid-Build Modifications

- **User:** `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi`**Agent:** `Draft bill created: 2kg Loose Sugar, 1 packet Aashirvaad Atta 5kg, 4 packets Maggi 70g. Total: ₹399.00. Ready to finalize.`
- **User:** `drop the atta and make it 6 Maggi`**Agent:** `Draft bill updated: 2kg Loose Sugar, 6 packets Maggi 70g. Total: ₹172.00.`
- **User:** `finalize the bill UPI`
  **Agent:** `Bill INV-20261011-0001 finalized! Total: ₹172.00 paid via UPI. Stock updated.`

### 3. Inward Stock Receipt

- **User:** `50 packets of Maggi came in, cost ₹12, MRP ₹14`
  **Agent:** `Stock received: 50 packets of Maggi 70g added. New stock: 75 packets.`

### 4. Khata (Credit Ledger)

- **User:** `what's Ramesh's balance?`**Agent:** `Ramesh currently owes ₹600.00.`
- **User:** `Ramesh paid ₹300 cash`
  **Agent:** `Recorded payment of ₹300.00 from Ramesh. New balance: ₹300.00.`

### 5. Automated PDF Invoices & PowerPoint Decks

- **User:** `send me that bill as a PDF`**Agent:** `GST Invoice PDF generated: INV-20261011-0001.pdf` *(Direct download link provided)*
- **User:** `make this week's sales analysis deck`
  **Agent:** `Generated executive PowerPoint presentation with native charts: Store_Ops_Analysis_20261011.pptx`

### 6. Durable Store Preferences

- **User:** `always assume UPI unless I say cash`
  **Agent:** `Stored preference: default_payment_mode = UPI.`

---

## 📁 Project Architecture

```
Nebula-Supermarket-Agent/
├── web/                         # Web Application Layer
│   ├── server.py                # FastAPI REST API + WebSocket Broadcaster
│   ├── templates/
│   │   └── index.html           # Single-Page Premium UI Dashboard
│   └── static/
│       ├── css/styles.css       # Glassmorphism Dark Theme Styling
│       └── js/app.js            # Reactive Web Controller & Real-Time Sync
├── core/                        # Core Agent Engine
│   ├── agent_loop.py            # ReAct Loop & Gemini Chat Orchestration
│   └── gst_engine.py            # Indian Retail GST Calculations & Rounding
├── database/                    # SQLite Data Layer (WAL Mode)
│   ├── db.py                    # Connection Pool & Initialization
│   ├── repository.py            # Transactional Repository & Business Rules
│   └── schema.sql               # Relational Schema & Indexes
├── skills/                      # Modular Domain Skills
│   ├── inventory_skill.py       # Stock Queries, Inward Shipments & Alerts
│   ├── billing_skill.py         # Multi-turn Draft POS & Finalization
│   ├── khata_skill.py           # Customer Credit Ledger & Settlements
│   ├── analytics_skill.py       # Daily Close & Revenue Telemetry
│   ├── document_skill.py        # ReportLab PDF & python-pptx Generator
│   └── memory_skill.py          # Persistent Owner Preferences
├── artifacts/                   # Document Compilers
│   ├── invoice_pdf.py           # Authentic ReportLab Indian GST Tax Invoice
│   └── analysis_pptx.py         # 6-Slide Executive Deck with Native Charts
├── output/                      # Generated Files
│   ├── invoices/                # Generated PDF Invoices
│   └── decks/                   # Generated PowerPoint Presentations (.pptx)
├── config/                      # Configuration & Seed Data
│   ├── settings.py              # Paths, Keys, and Constants
│   └── seed_data.py             # Pre-seeded Indian Grocery Catalog
├── run_web.py                   # Web Dashboard Launcher
├── run_cli.py                   # Terminal CLI Launcher
├── run_bot.py                   # Telegram Bot Daemon
└── reset_db.py                  # Database Reset Utility
```

---

## 🧪 Testing

Run the test suite covering GST math, oversell guards, khata validations, and multi-turn billing:

```bash
pytest
```

To run full end-to-end conversation scenario tests:

```bash
python test_scenarios.py
```

---

## 🛠️ REST & WebSocket API Reference

| Endpoint                        | Method            | Description                                       |
| ------------------------------- | ----------------- | ------------------------------------------------- |
| `/ws`                         | `WebSocket`     | Real-time bi-directional telemetry broadcast      |
| `/api/chat`                   | `POST`          | Send natural language message to AI Copilot       |
| `/api/chat/reset`             | `POST`          | Reset conversation context and draft cart         |
| `/api/products`               | `GET / POST`    | Search catalog / Register new SKU                 |
| `/api/products/receive-stock` | `POST`          | Receive inward supplier stock                     |
| `/api/draft-bill`             | `GET`           | View active draft bill                            |
| `/api/draft-bill/items`       | `POST / DELETE` | Add or remove items from draft cart               |
| `/api/bills/finalize`         | `POST`          | Atomically commit bill, decrement stock & cut PDF |
| `/api/khata`                  | `GET`           | List customer balances & ledger entries           |
| `/api/artifacts`              | `GET`           | List generated PDF invoices and PPTX decks        |
| `/api/artifacts/download`     | `GET`           | Download PDF or PPTX file                         |
| `/api/system/reset-db`        | `POST`          | Reset store database to seed state                |
