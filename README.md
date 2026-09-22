# 🏪 Indian Supermarket & Kirana Ops Agent

> **Run an entire Indian kirana store from a chat window — with an agent, not a menu.**  
> *Nebula KnowLab · Engineering Take-Home Assignment*

Telegram Bot: **Supermarket Ops Agent** (`@Supermarketagent_bot`) *(Configure your token in `.env` to deploy or test instantly via interactive CLI)*

---

## 1. Executive Summary & Harness Selection

### Why an Autonomous ReAct Agent Harness?
Traditional bot architectures fall into two traps:
1. **The Chatbot-in-front-of-CRUD Trap:** Rigid regex/keyword routers (`if 'bill' in msg: ...`) that crumble when real shopkeepers type terse, colloquial phrasing with multi-item modifications.
2. **The LangGraph Node-per-Command State Machine Trap:** Imposing hardcoded graph transitions for every command misinterprets agentic autonomy. In real retail, conversations are fluid: an owner might check stock, add an item, ask about a customer balance, and modify a previous line item all within two turns.

**Our Harness Architecture:**
We authored an **Agent-First ReAct Control Loop** (`Observe → Reason → Act (Tool Call) → Feed Result Back → Continue`) powered natively by **Google Gemini (`gemini-3.6-flash` / `gemini-2.5-pro`)**. The model orchestrates modular domain skills, while **all financial invariants, tax mathematics, oversell guards, and data durability live strictly in the tool and database layer**.

```
                           +-------------------------------------+
                           | Telegram Chat / Interactive Terminal|
                           +-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
|                        AUTONOMOUS ReAct AGENT CONTROL LOOP                        |
|                                                                                   |
|  [OBSERVE]              [REASON]                   [ACT]               [FEEDBACK] |
|   User Msg      -->   Model Ingests System   -->   Dispatches Tools   -->  Results Fed|
|   + Session           Prompt + DB Memory           (Multi-tool Chaining)   Back to LLM|
+-----------------------------------------------------------------------------------+
           |                     |                      |                     |
           v                     v                      v                     v
   +---------------+    +------------------+    +---------------+    +---------------+
   | Inventory     |    | Billing / POS    |    | Khata Ledger  |    | Document &    |
   | Skill         |    | Skill            |    | Skill         |    | Analytics     |
   | • Stock In    |    | • Multi-turn     |    | • Balance     |    | • PDF Invoice |
   | • New SKU     |    | • Mid-build edit |    | • Credit sale |    | • PPTX Deck   |
   | • Low alert   |    | • Atomic checkout|    | • Settlement  |    | • Daily close |
   +---------------+    +------------------+    +---------------+    +---------------+
                                 |                      |
                                 v                      v
                +-----------------------------------------------+
                |     SQLite Database Engine (WAL Journal Mode) |
                |  • Atomic stock check & decrement (>= 0)       |
                |  • Persistent Owner Preferences Across /new   |
                |  • Idempotency Log for Retried Webhooks       |
                +-----------------------------------------------+
```

---

## 2. Solving the 9 Hard Parts

### 1. Grounding
- **Problem:** Models hallucinate prices, slabs, or invent products.
- **Solution:** Zero price or inventory information is hardcoded in prompts. Every item query, price check, and stock level is retrieved dynamically from SQLite (`products` table). If an item doesn't exist, the agent explicitly reports it missing from the catalog.

### 2. Oversell Guard
- **Problem:** Stock cannot go negative. The model might promise items the store does not have.
- **Solution:** Enforced at the database transaction layer (`StoreRepository.finalize_bill`):
  ```sql
  UPDATE products 
  SET stock_qty = stock_qty - :qty, updated_at = CURRENT_TIMESTAMP
  WHERE sku_id = :sku_id AND stock_qty >= :qty;
  ```
  If `requested_qty > stock_qty`, `OversellError` is raised immediately, and the transaction is aborted. Unit conversions (e.g. 500g loose sugar sold from kg inventory) are normalized prior to checking.

### 3. GST Correctness (Indian Retail Standard)
- **Problem:** In Indian retail, MRP is tax-inclusive. Slabs vary (0%, 5%, 12%, 18%), intra-state sales must be split 50/50 into CGST and SGST, and rounding must not lose paise.
- **Solution:** Implemented in `core/gst_engine.py`:
  - $\text{Taxable Value} = \text{round}\left(\frac{\text{Gross}}{1 + r}, 2\right)$
  - $\text{Total Tax} = \text{round}(\text{Gross} - \text{Taxable Value}, 2)$
  - $\text{CGST} = \text{round}\left(\frac{\text{Total Tax}}{2}, 2\right), \quad \text{SGST} = \text{Total Tax} - \text{CGST}$
  - Invoices calculate a full slab breakup table and round the final bill to the nearest integer rupee with a precise round-off adjustment.

### 4. Multi-Turn Bills with Mid-Build Edits
- **Problem:** Bills evolve over multiple messages ("drop the butter, make it 6 Maggi"). Stock must not be decremented during drafting.
- **Solution:** An active draft bill is tracked in the session (`bills` with `status='draft'`). The shopkeeper can freely add, modify quantities, or delete line items. **Stock is only decremented when the owner explicitly finalizes/cuts the bill** in an atomic transaction.

### 5. Idempotency
- **Problem:** Telegram redelivers updates on network hiccups, risking double-billing or double-decrementing stock.
- **Solution:** Every critical mutating action (`finalize_bill`, `receive_stock`) logs an `idempotency_key` into `idempotency_log`. If a redelivered webhook arrives, the system detects the existing execution and returns the cached bill result without altering stock.

### 6. Concurrency
- **Problem:** Simultaneous sales or stock-in operations could corrupt inventory.
- **Solution:** SQLite is configured in **WAL (Write-Ahead Logging)** mode with `PRAGMA busy_timeout = 30000;`. All mutations run inside `BEGIN IMMEDIATE` transaction blocks, guaranteeing ACID isolation.

### 7. Guardrails
- **Below Cost Price:** `add_new_product` rejects registrations where sell price < cost price (`sell_price < cost_price`).
- **Non-Existent Khata Settle:** Settle payments (`record_khata_payment`) check if the customer has an active account. If unknown, the tool refuses the transaction and informs the shopkeeper.

### 8. Real Artifacts (PDF & PPTX)
- **PDF Invoices (`artifacts/invoice_pdf.py`):** Generates an authentic Indian GST tax invoice using ReportLab: Store Name, GSTIN, HSN codes, taxable base, CGST/SGST breakdown, round-off, amount in words, and authorized signatory box.
- **PPTX Analysis Deck (`artifacts/analysis_pptx.py`):** Generates a 6-slide widescreen presentation using `python-pptx` with **native PowerPoint charts** (Daily Sales Velocity Clustered Column, Payment Mode Distribution Pie/Donut Chart, Top Revenue Drivers Table, Inventory Reorder Priority Table, and Actionable AI Procurement Insights).

### 9. Memory Across Sessions
- **Problem:** Starting `/new` must clear the active conversational context and draft bill, but retain standing owner preferences.
- **Solution:** Standing preferences are stored in the SQLite `owner_preferences` table (outside the context window). When `/new` is issued, session history and draft bills are cleared, but persistent preferences (`default_payment_mode=UPI`, `default_atta=Aashirvaad 5kg`, `shop_gstin`, `shop_name`) are re-injected into the agent system instructions.

---

## 3. Ambiguity Resolution

When a request is genuinely ambiguous (e.g. *"add atta"* when both *Aashirvaad Atta 5kg* and *Loose Chakki Atta* exist in the store):
- The agent **does not guess** or use hardcoded regexes.
- The model inspects inventory via `search_inventory`, recognizes multiple candidates without an existing preference, and asks a terse clarifying question:
  > *"Which atta would you like to add — Aashirvaad Atta 5kg or Loose Chakki Atta?"*
- If the owner previously configured a standing preference (`default atta = Aashirvaad 5kg`), the model utilizes it directly.

---

## 4. Setup & Running Instructions

### Step 1: Clone & Install Dependencies
```bash
git clone <repo-url>
cd Nebula-Supermarket-Agent
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_MODEL=gemini-3.6-flash
```

### Step 3: Run the Verification Suite (All 9 Hard Parts)
```bash
python test_scenarios.py
```
*Output: Verifies grounding, oversell refusal, GST calculations, multi-turn editing, idempotency, concurrency, guardrails, PDF/PPTX generation, and session memory.*

### Step 4: Run the Unit Tests
```bash
python -m pytest tests/
```

### Step 5: Run the Interactive Terminal (No Telegram Token Required!)
```bash
python run_cli.py
```

### Step 6: Launch the Live Telegram Bot
```bash
python run_bot.py
```

---

## 5. Walkthrough & Recording Script (4-5 Minutes)

For reviewing the system end-to-end, execute this sequence:

| Step | Shopkeeper Input | Expected Agent Behavior & Tool |
| :--- | :--- | :--- |
| **1. Stock-In** | `50 packets of Maggi came in, cost ₹12, MRP ₹14` | Calls `receive_inward_stock`. Increments stock and updates prices. |
| **2. Ambiguity** | `add atta` | Calls `search_inventory`, notices packaged vs loose, asks: *"Which atta — Aashirvaad 5kg or Loose?"* |
| **3. Multi-Turn Bill** | `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI` | Calls `build_or_update_bill`. Creates draft bill, computes GST. Stock untouched. |
| **4. Edit Mid-Build** | `drop the butter, make it 6 Maggi` | Calls `build_or_update_bill`. Removes butter, updates Maggi to 6. |
| **5. Finalize Bill** | `finalize the bill` | Calls `finalize_current_bill`. Decrements stock atomically. |
| **6. Oversell Guard** | `bill 100 packets of Surf Excel` followed by `cut bill` | Calls `finalize_current_bill`. Refuses: *"OVERSELL REFUSED: Only 15 available. Stock cannot go negative."* |
| **7. Khata Cycle** | `what's Ramesh's balance?` | Calls `check_customer_khata_balance` -> reports ₹1,200.00. |
| **7b. Khata Settle** | `Ramesh paid ₹300` | Calls `record_khata_payment` -> reduces balance to ₹900.00. |
| **8. Real PDF** | `send me that bill as a PDF` | Calls `generate_gst_invoice_pdf` -> sends clean GST PDF invoice document. |
| **9. Real PPTX** | `make this week's sales analysis deck` | Calls `generate_business_analysis_deck` -> sends PPTX with native charts. |
| **10. Memory & Reset** | `default atta = Aashirvaad 5kg` | Calls `set_standing_preference`. |
| **10b. /new Chat** | `/new` followed by `bill 1 atta` | Context resets, but standing preference is recalled: bills *Aashirvaad 5kg* automatically! |

---

## 6. Repository Collaborators

Per submission guidelines, the following collaborators are invited to the private repository:
- `Aswath363`
- `akshaiP`
- `ashwanthnebula`
