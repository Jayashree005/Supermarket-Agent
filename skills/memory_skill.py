"""
Memory Skill: Standing preferences persisted across chats and /new sessions.
"""
from typing import Dict, Any
from database.repository import StoreRepository

def set_standing_preference(key: str, value: str) -> Dict[str, Any]:
    """
    Save a persistent store owner preference that endures across chats, restarts, and /new resets.
    Examples:
    - default_payment_mode: 'UPI' or 'cash'
    - default_atta: 'Aashirvaad Atta 5kg'
    - shop_name: 'Sri Krishna Supermarket & Kirana'
    - shop_gstin: '29ABCDE1234F1Z5'
    """
    StoreRepository.set_preference(key, value)
    return {
        "status": "success",
        "key": key,
        "value": value,
        "message": f"Saved preference: '{key}' is now set to '{value}'. This will be remembered across all future conversations."
    }

def get_standing_preferences() -> Dict[str, Any]:
    """
    Retrieve all active persistent store preferences.
    """
    prefs = StoreRepository.get_all_preferences()
    return {
        "status": "success",
        "preferences": prefs
    }
