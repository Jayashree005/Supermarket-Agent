"""
FastAPI Server for Nebula Indian Supermarket Operations Agent.
Provides REST APIs, WebSocket real-time event broadcasting,
Chatbot interface, and static file serving for the Premium Web Dashboard.
"""
import os
import sys
import glob
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, date

# UTF-8 fix for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.db import get_connection, init_db
from database.repository import StoreRepository, GuardrailError, OversellError
from core.agent_loop import KiranaOpsAgent
from config.settings import DB_PATH, OUTPUT_DIR
from config.seed_data import seed_database, reset_database
from bot.session_manager import SessionManager
from skills.document_skill import generate_gst_invoice_pdf, generate_business_analysis_deck

app = FastAPI(
    title="Supermarket Operations Dashboard",
    description="Real-time Autonomous Operations & Assistant Web Application",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Global Agent Instance
ops_agent: Optional[KiranaOpsAgent] = None

def get_agent() -> KiranaOpsAgent:
    global ops_agent
    if ops_agent is None:
        ops_agent = KiranaOpsAgent()
    return ops_agent

# Lifespan / Startup
@app.on_event("startup")
async def startup_event():
    init_db()
    seed_database()
    try:
        get_agent()
    except Exception as e:
        print(f"Warning: Could not initialize KiranaOpsAgent: {e}")

# Base Models
class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = "web_shopkeeper_session"

class AddProductRequest(BaseModel):
    name: str
    unit: str = "packet"
    cost_price: float
    mrp: float
    sell_price: Optional[float] = None
    gst_rate: float = 0.0
    hsn_code: str = "9999"
    category: str = "General"
    brand: Optional[str] = None
    is_loose: bool = False
    initial_stock: float = 0.0
    reorder_level: float = 5.0

class ReceiveStockRequest(BaseModel):
    sku_or_name: str
    quantity: float
    cost_price: Optional[float] = None
    mrp: Optional[float] = None
    sell_price: Optional[float] = None

class AddDraftItemRequest(BaseModel):
    bill_id: Optional[str] = None
    item_name: str
    quantity: float = 1.0
    unit: Optional[str] = None

class FinalizeBillRequest(BaseModel):
    bill_id: str
    payment_mode: str = "cash"
    customer_name: Optional[str] = None
    payment_ref: Optional[str] = None

class KhataActionRequest(BaseModel):
    customer_name: str
    amount: float
    payment_mode: Optional[str] = "cash"
    notes: Optional[str] = None

class PreferenceRequest(BaseModel):
    key: str
    value: str

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial connected ping
        await websocket.send_json({"type": "connected", "timestamp": datetime.now().isoformat()})
        while True:
            data = await websocket.receive_text()
            # client heartbeat
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# --- Chatbot API ---
@app.post("/api/chat")
async def chat_with_agent(req: ChatMessageRequest):
    agent = get_agent()
    session_id = req.session_id or "web_shopkeeper_session"
    
    # Process turn with AI agent
    try:
        turn = await asyncio.to_thread(agent.process_message, session_id, req.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Format response and artifacts for frontend
    formatted_artifacts = []
    for art_path in turn.artifacts:
        filename = os.path.basename(art_path)
        art_type = "pdf" if filename.endswith(".pdf") else "pptx"
        url = f"/api/artifacts/download?filename={filename}&type={art_type}"
        formatted_artifacts.append({
            "filename": filename,
            "type": art_type,
            "path": art_path,
            "url": url
        })

    # Broadcast event so dashboard widgets (stocks, bills, stats) update live
    await manager.broadcast({
        "type": "conversation_event",
        "user_message": req.message,
        "agent_reply": turn.text,
        "tools_executed": turn.tools_executed,
        "artifacts": formatted_artifacts,
        "timestamp": datetime.now().isoformat()
    })

    return {
        "reply": turn.text,
        "tools_executed": turn.tools_executed,
        "artifacts": formatted_artifacts
    }

@app.post("/api/chat/reset")
async def reset_chat_context(session_id: Optional[str] = "web_shopkeeper_session"):
    agent = get_agent()
    msg = agent.reset_chat(session_id)
    await manager.broadcast({
        "type": "chat_reset",
        "message": msg,
        "timestamp": datetime.now().isoformat()
    })
    return {"message": msg}

# --- Inventory & Stocks API ---
@app.get("/api/products")
async def get_products(query: str = "", category: Optional[str] = None):
    products = StoreRepository.search_products(query=query, category=category)
    return {"products": products, "count": len(products)}

@app.get("/api/products/low-stock")
async def get_low_stock():
    items = StoreRepository.get_low_stock_items()
    return {"low_stock_items": items, "count": len(items)}

@app.post("/api/products/receive-stock")
async def receive_stock(req: ReceiveStockRequest):
    try:
        res = StoreRepository.receive_stock(
            sku_or_name=req.sku_or_name,
            quantity=req.quantity,
            cost_price=req.cost_price,
            mrp=req.mrp,
            sell_price=req.sell_price
        )
        await manager.broadcast({
            "type": "stock_updated",
            "item": req.sku_or_name,
            "quantity_added": req.quantity,
            "new_stock": res["new_stock"]
        })
        return res
    except (GuardrailError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/products")
async def add_product(req: AddProductRequest):
    try:
        res = StoreRepository.add_product(
            name=req.name,
            unit=req.unit,
            cost_price=req.cost_price,
            mrp=req.mrp,
            sell_price=req.sell_price,
            gst_rate=req.gst_rate,
            hsn_code=req.hsn_code,
            category=req.category,
            brand=req.brand,
            is_loose=req.is_loose,
            initial_stock=req.initial_stock,
            reorder_level=req.reorder_level
        )
        await manager.broadcast({
            "type": "product_added",
            "product": res
        })
        return res
    except (GuardrailError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Bills & POS API ---
@app.get("/api/bills")
async def list_bills(status: Optional[str] = None, limit: int = 50):
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM bills WHERE status = ? ORDER BY created_at DESC LIMIT ?;", (status, limit))
    else:
        cursor.execute("SELECT * FROM bills ORDER BY created_at DESC LIMIT ?;", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    return {"bills": rows, "count": len(rows)}

@app.get("/api/bills/{bill_id}")
async def get_bill_detail(bill_id: str):
    try:
        return StoreRepository.get_full_bill(bill_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/draft-bill")
async def get_active_draft(session_id: Optional[str] = "web_shopkeeper_session", bill_id: Optional[str] = None):
    target_id = bill_id
    if not target_id and session_id:
        target_id = SessionManager.get_active_bill_id(session_id)
    draft = StoreRepository.get_or_create_draft_bill(target_id)
    if session_id and not SessionManager.get_active_bill_id(session_id):
        SessionManager.set_active_bill_id(session_id, draft["bill_id"])
    return draft

@app.post("/api/draft-bill/items")
async def add_draft_item(req: AddDraftItemRequest, session_id: Optional[str] = "web_shopkeeper_session"):
    active_id = req.bill_id or SessionManager.get_active_bill_id(session_id)
    draft = StoreRepository.get_or_create_draft_bill(active_id)
    SessionManager.set_active_bill_id(session_id, draft["bill_id"])
    res = StoreRepository.update_draft_bill_items(
        bill_id=draft["bill_id"],
        items_to_add=[{"sku_or_name": req.item_name, "quantity": req.quantity, "unit": req.unit}]
    )
    await manager.broadcast({
        "type": "draft_updated",
        "bill": res
    })
    return res

@app.delete("/api/draft-bill/items/{item_name}")
async def remove_draft_item(item_name: str, session_id: Optional[str] = "web_shopkeeper_session", bill_id: Optional[str] = None):
    active_id = bill_id or SessionManager.get_active_bill_id(session_id)
    draft = StoreRepository.get_or_create_draft_bill(active_id)
    res = StoreRepository.update_draft_bill_items(
        bill_id=draft["bill_id"],
        items_to_remove=[item_name]
    )
    await manager.broadcast({
        "type": "draft_updated",
        "bill": res
    })
    return res

@app.post("/api/bills/finalize")
async def finalize_bill(req: FinalizeBillRequest):
    try:
        res = StoreRepository.finalize_bill(
            bill_id=req.bill_id,
            payment_mode=req.payment_mode,
            customer_name=req.customer_name,
            payment_ref=req.payment_ref
        )
        # Automatically generate PDF invoice
        pdf_res = generate_gst_invoice_pdf(req.bill_id)
        
        await manager.broadcast({
            "type": "bill_finalized",
            "bill": res,
            "invoice_pdf": pdf_res.get("file_path")
        })
        return {"bill": res, "invoice": pdf_res}
    except (OversellError, GuardrailError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Khata (Credit Ledger) API ---
@app.get("/api/khata")
async def list_khatas():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM khata_customers ORDER BY balance DESC;")
    customers = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM khata_ledger ORDER BY timestamp DESC LIMIT 30;")
    recent_transactions = [dict(r) for r in cursor.fetchall()]

    return {"customers": customers, "transactions": recent_transactions}

@app.post("/api/khata/credit")
async def add_khata_credit(req: KhataActionRequest):
    try:
        res = StoreRepository.add_khata_credit(req.customer_name, req.amount, req.notes)
        await manager.broadcast({
            "type": "khata_updated",
            "action": "credit",
            "customer": req.customer_name,
            "amount": req.amount,
            "new_balance": res["new_balance"]
        })
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/khata/settlement")
async def record_khata_settlement(req: KhataActionRequest):
    try:
        res = StoreRepository.record_khata_settlement(
            req.customer_name, req.amount, req.payment_mode or "cash", req.notes
        )
        await manager.broadcast({
            "type": "khata_updated",
            "action": "settlement",
            "customer": req.customer_name,
            "amount": req.amount,
            "new_balance": res["new_balance"]
        })
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Analytics & Summary API ---
@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    today = date.today().strftime("%Y-%m-%d")
    daily_close = StoreRepository.get_daily_close_data(today)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total products count & total items out of stock
    cursor.execute("SELECT COUNT(*) FROM products;")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE stock_qty <= reorder_level;")
    low_stock_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE stock_qty = 0;")
    out_of_stock_count = cursor.fetchone()[0]

    # Total Khata credit owed to store
    cursor.execute("SELECT COALESCE(SUM(balance), 0.0) FROM khata_customers WHERE balance > 0;")
    total_khata_owed = cursor.fetchone()[0]

    # Total finalized bills all time
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(rounded_total), 0.0) FROM bills WHERE status = 'finalized';")
    all_time_bills_row = cursor.fetchone()
    all_time_bills = all_time_bills_row[0]
    all_time_sales = all_time_bills_row[1]

    # Recent 5 finalized bills
    cursor.execute("SELECT * FROM bills WHERE status = 'finalized' ORDER BY created_at DESC LIMIT 5;")
    recent_bills = [dict(r) for r in cursor.fetchall()]

    return {
        "today_stats": daily_close["totals"],
        "payment_breakdown": daily_close["payment_breakdown"],
        "top_items_today": daily_close["top_items"],
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_khata_owed": total_khata_owed,
        "all_time_bills": all_time_bills,
        "all_time_sales": all_time_sales,
        "recent_bills": recent_bills,
        "date": today
    }

# --- Artifacts (PDF & PPTX Decks) API ---
@app.get("/api/artifacts")
async def list_artifacts():
    invoices_dir = OUTPUT_DIR / "invoices"
    decks_dir = OUTPUT_DIR / "decks"

    invoices = []
    for f in sorted(glob.glob(str(invoices_dir / "*.pdf")), reverse=True):
        fname = os.path.basename(f)
        size_kb = round(os.path.getsize(f) / 1024, 1)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        invoices.append({
            "filename": fname,
            "type": "pdf",
            "size_kb": size_kb,
            "modified": mtime,
            "url": f"/api/artifacts/download?filename={fname}&type=pdf"
        })

    decks = []
    for f in sorted(glob.glob(str(decks_dir / "*.pptx")), reverse=True):
        fname = os.path.basename(f)
        size_kb = round(os.path.getsize(f) / 1024, 1)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        decks.append({
            "filename": fname,
            "type": "pptx",
            "size_kb": size_kb,
            "modified": mtime,
            "url": f"/api/artifacts/download?filename={fname}&type=pptx"
        })

    return {"invoices": invoices, "decks": decks}

@app.get("/api/artifacts/download")
async def download_artifact(filename: str, type: str):
    if type == "pdf":
        file_path = OUTPUT_DIR / "invoices" / filename
        media_type = "application/pdf"
    elif type == "pptx":
        file_path = OUTPUT_DIR / "decks" / filename
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        raise HTTPException(status_code=400, detail="Invalid artifact type")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)

@app.post("/api/artifacts/generate-pptx")
async def generate_pptx_deck(days: int = 7):
    res = generate_business_analysis_deck(days=days)
    if res.get("status") == "success":
        fname = os.path.basename(res["file_path"])
        await manager.broadcast({
            "type": "artifact_created",
            "artifact_type": "pptx",
            "filename": fname,
            "url": f"/api/artifacts/download?filename={fname}&type=pptx"
        })
    return res

@app.post("/api/artifacts/generate-pdf")
async def generate_pdf(bill_number: Optional[str] = None):
    res = generate_gst_invoice_pdf(bill_number)
    if res.get("status") == "success":
        fname = os.path.basename(res["file_path"])
        await manager.broadcast({
            "type": "artifact_created",
            "artifact_type": "pdf",
            "filename": fname,
            "url": f"/api/artifacts/download?filename={fname}&type=pdf"
        })
    return res

# --- System / Admin API ---
@app.post("/api/system/reset-db")
async def reset_store_database():
    reset_database()
    agent = get_agent()
    agent.reset_chat("web_shopkeeper_session")
    await manager.broadcast({
        "type": "store_reset",
        "message": "Store database and inventory restored to pristine state."
    })
    return {"message": "Store database reset successfully."}

@app.get("/api/preferences")
async def get_preferences():
    return StoreRepository.get_all_preferences()

@app.post("/api/preferences")
async def set_preference(req: PreferenceRequest):
    StoreRepository.set_preference(req.key, req.value)
    return {"status": "success", "key": req.key, "value": req.value}

# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve Index UI
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
