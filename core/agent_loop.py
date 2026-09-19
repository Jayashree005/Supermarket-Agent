"""
Autonomous ReAct Agent Loop for Indian Supermarket & Kirana Store Ops.
Orchestrates domain skills, enforces tool-level business rules, resolves ambiguities,
manages session state, and yields real artifacts (PDF invoices & PPTX decks).
"""
import os
import re
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from database.repository import StoreRepository
from bot.session_manager import SessionManager

# Skills
from skills.inventory_skill import (
    search_inventory,
    get_stock_status,
    receive_inward_stock,
    add_new_product,
    check_low_stock_alerts
)
from skills.billing_skill import (
    build_or_update_bill,
    view_draft_bill,
    finalize_current_bill
)
from skills.khata_skill import (
    check_customer_khata_balance,
    add_credit_to_khata,
    record_khata_payment,
    list_active_khata_accounts
)
from skills.analytics_skill import (
    get_daily_close
)
from skills.document_skill import (
    generate_gst_invoice_pdf,
    generate_business_analysis_deck
)
from skills.memory_skill import (
    set_standing_preference,
    get_standing_preferences
)

@dataclass
class AgentTurnResult:
    text: str
    artifacts: List[str] = field(default_factory=list) # Generated PDF / PPTX file paths
    tools_executed: List[str] = field(default_factory=list)

class KiranaOpsAgent:
    """Conversational Kirana Agent with autonomous tool orchestration and persistent memory."""

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured in environment or settings.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.active_chats: Dict[str, Any] = {} # chat_id -> Chat instance
        self.active_turn_artifacts: Dict[str, List[str]] = {}
        self.active_turn_tools: Dict[str, List[str]] = {}

    def _build_system_prompt(self) -> str:
        """Constructs system instructions incorporating durable preferences from SQLite DB."""
        prefs = StoreRepository.get_all_preferences()
        shop_name = prefs.get("shop_name", "Sri Krishna Supermarket & Kirana")
        shop_address = prefs.get("shop_address", "14, 100ft Road, Indiranagar, Bengaluru")
        shop_gstin = prefs.get("shop_gstin", "29ABCDE1234F1Z5")
        default_pay = prefs.get("default_payment_mode", "UPI")

        # Format custom shortcuts/preferences
        pref_lines = []
        for k, v in prefs.items():
            pref_lines.append(f"• {k}: {v}")
        pref_str = "\n".join(pref_lines) if pref_lines else "None configured"

        return f"""You are the autonomous Supermarket Operations Agent running '{shop_name}'.
The store owner interacts with you directly via Telegram in terse, real-world Indian shopkeeper language.

STORE IDENTITY & LOCATION:
• Store: {shop_name}
• Location: {shop_address}
• GSTIN: {shop_gstin} (Intra-state Karnataka, Code: 29)
• Default Payment Preference: {default_pay}

DURABLE PREFERENCES & STORE MEMORY:
{pref_str}

YOUR RESPONSIBILITIES:
1. RECEIVING STOCK: Record inbound inventory deliveries, update cost price and MRP with receive_inward_stock.
2. NEW PRODUCTS: Add newly stocked items to the catalog using add_new_product.
3. BILLING / POS:
   - Build bills incrementally over multi-turn conversations.
   - When owner asks to make a bill or adds items, call build_or_update_bill.
   - If owner says "drop X", "remove X", or "make it Y", call build_or_update_bill with modifications.
   - IMPORTANT: Stock is NOT decremented during drafting. It remains in draft until finalized.
   - When owner asks to cut the bill, finalize, or settle, call finalize_current_bill.
   - If payment mode is not mentioned, use the owner's standing default ({default_pay}) unless specified.
4. OVERSELL GUARD:
   - If stock is insufficient, finalize_current_bill will return an 'oversell_refused' status. Relate this refusal clearly to the owner. Stock CANNOT go negative.
5. KHATA (CREDIT LEDGER):
   - Check balances ("Ramesh's balance?"), record credit purchases ("put ₹500 on Ramesh's credit"), and record settlements ("Ramesh paid ₹300").
   - If a customer does not exist in Khata, settlement will be refused by the tool.
6. DAILY CLOSE:
   - Run end-of-day reconciliation ("today's sales?", "close the day") using get_daily_close.
7. ARTIFACTS:
   - "send me that bill as a PDF" -> call generate_gst_invoice_pdf.
   - "make this week's sales analysis deck" -> call generate_business_analysis_deck.
8. STANDING PREFERENCES:
   - When owner sets a preference ("always assume UPI unless I say cash", "default atta = Aashirvaad 5kg"), call set_standing_preference.

GROUNDING & AMBIGUITY RULES:
• NEVER invent products, prices, or stock. Ground all information via tools.
• AMBIGUITY: If the owner's request is ambiguous (e.g. "add atta" or "bill dal") and multiple products match in catalog (e.g. Aashirvaad Atta 5kg vs Loose Chakki Atta) without a standing preference, DO NOT GUESS. Call search_inventory to inspect options, and ask a concise clarifying question (e.g. "Which one — Aashirvaad 5kg or Loose Chakki Atta?").
• If a standing preference exists (e.g. default atta = Aashirvaad 5kg), use the preferred SKU directly.

TONE & PHRASING:
• Be prompt, crisp, and businesslike — speak like an efficient store manager / munshi.
• Use ₹ (INR) for amounts.
• Confirm actions clearly with item names, quantities, and totals.
"""

    def _wrap_tools(self, chat_id: str) -> List[Any]:
        """Wraps domain skills into callable tools that record execution context and artifacts."""
        
        def tool_search_inventory(query: str, category: Optional[str] = None):
            """Search products in store catalog by name, brand or category."""
            self.active_turn_tools[chat_id].append("search_inventory")
            return search_inventory(query, category)

        def tool_get_stock_status(item_name_or_sku: str):
            """Check current stock quantity, price, and reorder status for an item."""
            self.active_turn_tools[chat_id].append("get_stock_status")
            return get_stock_status(item_name_or_sku)

        def tool_receive_inward_stock(
            item_name_or_sku: str,
            quantity: float,
            cost_price: Optional[float] = None,
            mrp: Optional[float] = None,
            sell_price: Optional[float] = None,
            idempotency_key: Optional[str] = None
        ):
            """Record inbound stock arrival from suppliers."""
            self.active_turn_tools[chat_id].append("receive_inward_stock")
            return receive_inward_stock(
                item_name_or_sku, quantity, cost_price, mrp, sell_price, idempotency_key
            )

        def tool_add_new_product(
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
        ):
            """Register a brand new product SKU in the store catalog with GST slab."""
            self.active_turn_tools[chat_id].append("add_new_product")
            return add_new_product(
                name, unit, cost_price, mrp, sell_price, gst_rate,
                hsn_code, category, brand, is_loose, initial_stock, reorder_level
            )

        def tool_check_low_stock_alerts():
            """Identify all SKUs that have breached their reorder threshold."""
            self.active_turn_tools[chat_id].append("check_low_stock_alerts")
            return check_low_stock_alerts()

        def tool_build_or_update_bill(
            items_to_add: Optional[List[Dict[str, Any]]] = None,
            items_to_remove: Optional[List[str]] = None,
            items_to_update: Optional[List[Dict[str, Any]]] = None,
            payment_mode: Optional[str] = None,
            customer_name: Optional[str] = None
        ):
            """Create or modify items on the active draft bill mid-build."""
            self.active_turn_tools[chat_id].append("build_or_update_bill")
            active_id = SessionManager.get_active_bill_id(chat_id)
            res = build_or_update_bill(
                items_to_add=items_to_add,
                items_to_remove=items_to_remove,
                items_to_update=items_to_update,
                payment_mode=payment_mode,
                customer_name=customer_name,
                bill_id=active_id
            )
            if res.get("status") == "draft_updated" and res.get("bill_id"):
                SessionManager.set_active_bill_id(chat_id, res["bill_id"])
            return res

        def tool_view_draft_bill():
            """Inspect the current active draft bill line items, taxes, and grand total."""
            self.active_turn_tools[chat_id].append("view_draft_bill")
            active_id = SessionManager.get_active_bill_id(chat_id)
            return view_draft_bill(active_id)

        def tool_finalize_current_bill(
            payment_mode: Optional[str] = None,
            payment_ref: Optional[str] = None,
            customer_name: Optional[str] = None,
            idempotency_key: Optional[str] = None
        ):
            """Finalize, checkout, and atomically decrement stock for active draft bill."""
            self.active_turn_tools[chat_id].append("finalize_current_bill")
            active_id = SessionManager.get_active_bill_id(chat_id)
            if not active_id:
                draft = StoreRepository.get_or_create_draft_bill()
                active_id = draft["bill_id"]

            res = finalize_current_bill(
                bill_id=active_id,
                payment_mode=payment_mode,
                payment_ref=payment_ref,
                customer_name=customer_name,
                idempotency_key=idempotency_key
            )
            if res.get("status") == "finalized":
                SessionManager.clear_active_bill(chat_id)
            return res

        def tool_check_customer_khata_balance(customer_name: str):
            """Check the outstanding credit balance of a customer in the khata ledger."""
            self.active_turn_tools[chat_id].append("check_customer_khata_balance")
            return check_customer_khata_balance(customer_name)

        def tool_add_credit_to_khata(customer_name: str, amount: float, notes: Optional[str] = None):
            """Record a credit purchase on customer's khata ledger."""
            self.active_turn_tools[chat_id].append("add_credit_to_khata")
            return add_credit_to_khata(customer_name, amount, notes)

        def tool_record_khata_payment(customer_name: str, amount: float, payment_mode: str = "cash", notes: Optional[str] = None):
            """Record customer settling/paying their credit. Refuses non-existent customers."""
            self.active_turn_tools[chat_id].append("record_khata_payment")
            return record_khata_payment(customer_name, amount, payment_mode, notes)

        def tool_list_active_khata_accounts():
            """List all customers with outstanding unpaid credit balances."""
            self.active_turn_tools[chat_id].append("list_active_khata_accounts")
            return list_active_khata_accounts()

        def tool_get_daily_close(date_str: Optional[str] = None):
            """Generate end-of-day sales, GST, payment split, and top products report."""
            self.active_turn_tools[chat_id].append("get_daily_close")
            return get_daily_close(date_str)

        def tool_generate_gst_invoice_pdf(bill_id_or_number: Optional[str] = None):
            """Generate an authentic, GST-compliant PDF invoice."""
            self.active_turn_tools[chat_id].append("generate_gst_invoice_pdf")
            res = generate_gst_invoice_pdf(bill_id_or_number)
            if res.get("status") == "success" and res.get("file_path"):
                self.active_turn_artifacts[chat_id].append(res["file_path"])
            return res

        def tool_generate_business_analysis_deck(days: int = 7):
            """Generate a PowerPoint analysis presentation (PPTX) with native charts."""
            self.active_turn_tools[chat_id].append("generate_business_analysis_deck")
            res = generate_business_analysis_deck(days=days)
            if res.get("status") == "success" and res.get("file_path"):
                self.active_turn_artifacts[chat_id].append(res["file_path"])
            return res

        def tool_set_standing_preference(key: str, value: str):
            """Save a persistent store owner preference that endures across chats and restarts."""
            self.active_turn_tools[chat_id].append("set_standing_preference")
            return set_standing_preference(key, value)

        def tool_get_standing_preferences():
            """Retrieve all active persistent store preferences."""
            self.active_turn_tools[chat_id].append("get_standing_preferences")
            return get_standing_preferences()

        return [
            tool_search_inventory,
            tool_get_stock_status,
            tool_receive_inward_stock,
            tool_add_new_product,
            tool_check_low_stock_alerts,
            tool_build_or_update_bill,
            tool_view_draft_bill,
            tool_finalize_current_bill,
            tool_check_customer_khata_balance,
            tool_add_credit_to_khata,
            tool_record_khata_payment,
            tool_list_active_khata_accounts,
            tool_get_daily_close,
            tool_generate_gst_invoice_pdf,
            tool_generate_business_analysis_deck,
            tool_set_standing_preference,
            tool_get_standing_preferences
        ]

    def _get_or_create_chat(self, chat_id: str, model_name: Optional[str] = None):
        """Retrieves or creates an active Gemini Chat session for the chat_id."""
        target_model = model_name or GEMINI_MODEL
        if chat_id not in self.active_chats or (model_name and self.active_chats[chat_id].model != target_model):
            tools = self._wrap_tools(chat_id)
            system_instruction = self._build_system_prompt()
            chat = self.client.chats.create(
                model=target_model,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    temperature=0.2
                )
            )
            chat.model = target_model
            self.active_chats[chat_id] = chat
        return self.active_chats[chat_id]

    def reset_chat(self, chat_id: str) -> str:
        """
        Clears conversation history and active draft bill for /new chat.
        Durable preferences in SQLite remain intact.
        """
        if chat_id in self.active_chats:
            del self.active_chats[chat_id]
        SessionManager.reset_chat_session(chat_id)
        return "Conversation context reset. Ready for a new transaction. (Store preferences & memory preserved)"

    def process_message(self, chat_id: str, message_text: str, max_retries: int = 3) -> AgentTurnResult:
        """
        Processes a shopkeeper turn with automatic model fallback & rate-limit backoff handling.
        Observe -> Reason -> Act -> Feed back -> Return answer & artifacts.
        """
        self.active_turn_artifacts[chat_id] = []
        self.active_turn_tools[chat_id] = []

        current_model = GEMINI_MODEL
        chat = self._get_or_create_chat(chat_id, current_model)
        
        reply_text = ""
        for attempt in range(max_retries):
            try:
                response = chat.send_message(message_text)
                reply_text = response.text or "Done."
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # If on a heavy model, switch immediately to gemini-flash-lite-latest
                    if current_model != "gemini-flash-lite-latest":
                        current_model = "gemini-flash-lite-latest"
                        chat = self._get_or_create_chat(chat_id, current_model)
                        time.sleep(1.0)
                        continue

                    # Extract wait seconds if present, e.g. "retry in 21s"
                    delay = 5.0 * (attempt + 1)
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str)
                    if match:
                        delay = float(match.group(1)) + 1.0

                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    else:
                        reply_text = f"API rate limit exceeded. Please retry in a few moments. ({err_str[:120]}...)"
                else:
                    reply_text = f"Encountered an operational error: {err_str}"
                    break

        artifacts = list(self.active_turn_artifacts.get(chat_id, []))
        tools_called = list(self.active_turn_tools.get(chat_id, []))

        return AgentTurnResult(
            text=reply_text,
            artifacts=artifacts,
            tools_executed=tools_called
        )
