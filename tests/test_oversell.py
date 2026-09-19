"""
Unit tests for oversell guard and inventory constraints.
"""
import pytest
from database.db import init_db
from config.seed_data import seed_database
from database.repository import StoreRepository, OversellError

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    seed_database()

def test_oversell_guard_blocks_excess_checkout():
    prod = StoreRepository.get_product("Surf Excel 1kg")
    available = prod["stock_qty"]
    excess = available + 50.0

    bill = StoreRepository.get_or_create_draft_bill()
    StoreRepository.update_draft_bill_items(
        bill["bill_id"],
        items_to_add=[{"sku_or_name": "Surf Excel 1kg", "quantity": excess}]
    )

    with pytest.raises(OversellError) as exc_info:
        StoreRepository.finalize_bill(bill["bill_id"])

    assert "OVERSELL REFUSED" in str(exc_info.value)
    # Stock must remain unchanged
    after = StoreRepository.get_product("Surf Excel 1kg")
    assert after["stock_qty"] == available

def test_unit_normalization_grams_to_kg():
    normalized = StoreRepository.normalize_unit(500, "g", "kg")
    assert normalized == 0.5
