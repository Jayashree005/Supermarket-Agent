# 🏪 How to Run Supermarket & Kirana Ops Agent

This guide provides step-by-step instructions to configure, test, and run the autonomous agent via the **Interactive Terminal (CLI)** or as a **Live Telegram Bot**.

---

## 1. Store Profile & Configuration

- **Store Name:** `ABC Super Market`
- **Location:** `ABC Super Market, Coimbatore, Tamil Nadu`
- **GSTIN:** `XXX`
- **State / Code:** `Tamil Nadu (Code: 33)`
- **Telegram Bot Name:** `Supermarket Ops Agent`
- **Telegram Bot Username:** `@Supermarketagent_bot`

---

## 2. Prerequisites

- **Python 3.10+** (Tested on Python 3.12)
- **Google Gemini API Key**: [Get a free API key at Google AI Studio](https://aistudio.google.com/)
- **Telegram Bot Token** *(Optional, only required if running the Telegram Bot)*: Obtained from `@BotFather`.

---

## 3. Installation & Environment Setup

### Step 1: Open Terminal in the Project Directory

```bash
cd Nebula-Supermarket-Agent
```

### Step 2: Install Required Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure `.env` File

Create or verify your `.env` file in the project root directory:

```env
# Required: Google Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here

# Required only for Telegram Bot (leave blank if using CLI only)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Recommended model
GEMINI_MODEL=gemini-3.6-flash
```

---

## 4. Verify System Health & Core Invariants

### Run Unit Tests (Pytest)

```bash
python -m pytest tests/
```

*Expected: 10 passed tests covering billing, GST calculation, khata ledger, and oversell guard.*

### Run Comprehensive 9-Point Verification Suite

```bash
python test_scenarios.py
```

*Validates Grounding, Oversell Refusal, GST Engine, Multi-turn Drafts, Idempotency, Concurrency, Guardrails, Real PDF/PPTX generation, and Cross-session Memory.*

---

## 5. Running the Project

### Option A: Interactive Terminal CLI (Fastest for Testing)

No Telegram setup or token is needed. You can chat with the agent directly in your console:

```bash
python run_cli.py
```

**Terminal Controls:**

- Type any natural shopkeeper query directly at `Shopkeeper > `
- `/new` or `/reset`: Clears conversational context & active draft bill (retains store inventory, stock, and preferences)
- `/reset-db` or `/reset-stock`: Wipes transactions and restores all stock levels, Khata balances, and catalog to pristine initial seed values
- `/exit` or `quit`: Exits the terminal

> [!TIP]
> You can also reset the database anytime from outside the CLI by running:
>
> ```bash
> python reset_db.py
> ```

---

### Option B: Live Telegram Bot

The bot is configured with:

- **Bot Name**: `Supermarket Ops Agent`
- **Username / Handle**: `@Supermarketagent_bot`

#### 1. Setup your Bot with `@BotFather`

1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot`.
3. Set the Display Name to: `Supermarket Ops Agent`.
4. Set the username to: `Supermarketagent_bot`.
5. Copy the HTTP API token provided by BotFather into your `.env` file under `TELEGRAM_BOT_TOKEN`.

#### 2. Start the Bot Server

```bash
python run_bot.py
```

#### 3. Start Chatting

Open Telegram, search for **`@Supermarketagent_bot`**, click **Start** (or send `/start`), and send your commands!
*(You can also use `/reset_db` in Telegram anytime to restore stock levels).*

---

## 6. Example Conversation Walkthrough

| Scenario                            | Input Command                                                             | What the Agent Does                                                          |
| :---------------------------------- | :------------------------------------------------------------------------ | :--------------------------------------------------------------------------- |
| **1. Stock Inward**           | `50 packets of Maggi came in, cost ₹12, MRP ₹14`                      | Updates stock count and updates unit pricing                                 |
| **2. Ambiguity Handling**     | `add atta`                                                              | Asks whether you mean packaged Aashirvaad 5kg or Loose Chakki Atta           |
| **3. Draft Multi-Item Bill**  | `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI`           | Creates draft bill and calculates GST without altering stock                 |
| **4. Mid-Build Modification** | `drop the butter, make it 6 Maggi`                                      | Updates the active bill in real-time                                         |
| **5. Finalize Bill**          | `finalize the bill`                                                     | Deducts stock atomically and completes the transaction                       |
| **6. Oversell Refusal**       | `bill 100 packets of Surf Excel` followed by `cut bill`               | Rejects order because inventory is insufficient                              |
| **7. Khata Ledger**           | `what is Ramesh's balance?`                                             | Checks customer balance (₹1,200.00)                                         |
| **8. Khata Settlement**       | `Ramesh paid ₹300`                                                     | Records payment and brings balance down to ₹900.00                          |
| **9. GST Invoice PDF**        | `send me that bill as a PDF`                                            | Generates a tax invoice in`output/invoices/` with ABC Super Market details |
| **10. Business Analytics**    | `make this week's sales analysis deck`                                  | Generates a 6-slide PPTX with charts in`output/decks/`                     |
| **11. Memory & Reset**        | `default atta = Aashirvaad 5kg`followed by `/new`then `bill 1 atta` | Resets conversation context but remembers your preference                    |
