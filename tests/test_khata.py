"""
Unit tests for customer khata ledger and settlement guardrails.
"""
import pytest
from database.db import init_db
from config.seed_data import seed_database
from database.repository import StoreRepository, GuardrailError

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    seed_database()

def test_khata_balance_query():
    cust = StoreRepository.get_khata_customer("Ramesh")
    assert cust is not None
    assert cust["balance"] == 1200.0

def test_khata_settlement_reduces_balance():
    init_cust = StoreRepository.get_khata_customer("Ramesh")
    res = StoreRepository.record_khata_settlement("Ramesh", 300.0)
    assert res["amount_paid"] == 300.0
    assert res["new_balance"] == init_cust["balance"] - 300.0

def test_khata_refuses_non_existent_customer():
    with pytest.raises(GuardrailError) as exc:
        StoreRepository.record_khata_settlement("NonExistentCustomer", 500.0)
    assert "does not have an active Khata account" in str(exc.value)
