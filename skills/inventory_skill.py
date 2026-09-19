"""
Inventory Skill: Stock status, receiving stock, registering new SKUs, low-stock alerts.
"""
from typing import Dict, Any, Optional, List
from database.repository import StoreRepository, GuardrailError

def search_inventory(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Search products in store catalog by name, brand or category.
    Use this to look up prices, stock availability, units, and GST slabs.
    """
    items = StoreRepository.search_products(query, category)
    return {
        "count": len(items),
        "products": [
            {
                "sku_id": p["sku_id"],
                "name": p["name"],
                "brand": p["brand"],
                "category": p["category"],
                "unit": p["unit"],
                "is_loose": bool(p["is_loose"]),
                "cost_price": p["cost_price"],
                "mrp": p["mrp"],
                "sell_price": p["sell_price"],
                "stock_qty": p["stock_qty"],
                "reorder_level": p["reorder_level"],
                "gst_rate": f"{int(p['gst_rate'] * 100)}%",
                "hsn_code": p["hsn_code"]
            }
            for p in items
        ]
    }

def get_stock_status(item_name_or_sku: str) -> Dict[str, Any]:
    """
    Check current stock quantity, sell price, and reorder status for a specific item.
    """
    product = StoreRepository.get_product(item_name_or_sku)
    if not product:
        return {"status": "not_found", "message": f"Product '{item_name_or_sku}' not found in store catalog."}
    
    return {
        "status": "found",
        "sku_id": product["sku_id"],
        "name": product["name"],
        "current_stock": product["stock_qty"],
        "unit": product["unit"],
        "cost_price": product["cost_price"],
        "sell_price": product["sell_price"],
        "mrp": product["mrp"],
        "reorder_level": product["reorder_level"],
        "is_low_stock": product["stock_qty"] <= product["reorder_level"]
    }

def receive_inward_stock(
    item_name_or_sku: str,
    quantity: float,
    cost_price: Optional[float] = None,
    mrp: Optional[float] = None,
    sell_price: Optional[float] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record inbound stock arrival from suppliers (stock-in).
    Updates inventory quantity and optionally updates cost price and MRP.
    """
    try:
        return StoreRepository.receive_stock(
            sku_or_name=item_name_or_sku,
            quantity=quantity,
            cost_price=cost_price,
            mrp=mrp,
            sell_price=sell_price,
            idempotency_key=idempotency_key
        )
    except GuardrailError as e:
        return {"status": "error", "message": str(e)}

def add_new_product(
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
    """
    Register a brand new product SKU in the store catalog with GST slab and pricing.
    Enforces that sell price cannot be lower than cost price.
    """
    try:
        return StoreRepository.add_product(
            name=name,
            unit=unit,
            cost_price=cost_price,
            mrp=mrp,
            sell_price=sell_price,
            gst_rate=gst_rate,
            hsn_code=hsn_code,
            category=category,
            brand=brand,
            is_loose=is_loose,
            initial_stock=initial_stock,
            reorder_level=reorder_level
        )
    except GuardrailError as e:
        return {"status": "refused", "message": str(e)}

def check_low_stock_alerts() -> Dict[str, Any]:
    """
    Identify all SKUs that have breached their reorder threshold and need immediate procurement.
    """
    low_items = StoreRepository.get_low_stock_items()
    return {
        "low_stock_count": len(low_items),
        "items": [
            {
                "name": itm["name"],
                "stock_qty": itm["stock_qty"],
                "reorder_level": itm["reorder_level"],
                "unit": itm["unit"],
                "suggested_order_qty": max(itm["reorder_level"] * 3 - itm["stock_qty"], 10.0)
            }
            for itm in low_items
        ]
    }
