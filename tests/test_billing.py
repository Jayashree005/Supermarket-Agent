"""
Unit tests for multi-turn billing, editing, and atomic stock decrements.
"""
import pytest
from database.db import init_db
from config.seed_data import seed_database
from database.repository import StoreRepository

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    seed_database()

def test_draft_bill_deferred_decrement():
    magg = StoreRepository.get_product("Maggi 70g")
    init_stock = magg["stock_qty"]

    # Draft bill
    b = StoreRepository.get_or_create_draft_bill()
    StoreRepository.update_draft_bill_items(
        b["bill_id"],
        items_to_add=[{"sku_or_name": "Maggi 70g", "quantity": 4}]
    )

    # Stock should remain untouched
    after_draft = StoreRepository.get_product("Maggi 70g")
    assert after_draft["stock_qty"] == init_stock

    # Edit draft
    StoreRepository.update_draft_bill_items(
        b["bill_id"],
        items_to_update=[{"sku_or_name": "Maggi 70g", "quantity": 6}]
    )
    full = StoreRepository.get_full_bill(b["bill_id"])
    assert full["items"][0]["quantity"] == 6.0

    # Finalize
    StoreRepository.finalize_bill(b["bill_id"])
    after_finalize = StoreRepository.get_product("Maggi 70g")
    assert after_finalize["stock_qty"] == init_stock - 6.0
