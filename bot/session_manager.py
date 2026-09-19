"""
Session manager for Telegram and CLI chat sessions.
Manages active draft bills, per-chat state, and durable memory synchronization.
"""
from typing import Optional, Dict, Any
from database.db import get_connection

class SessionManager:
    """Tracks active draft bills and session states per chat ID."""

    @staticmethod
    def get_active_bill_id(chat_id: str) -> Optional[str]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT active_bill_id FROM chat_sessions WHERE chat_id = ?;", (str(chat_id),))
        row = cursor.fetchone()
        return row["active_bill_id"] if row and row["active_bill_id"] else None

    @staticmethod
    def set_active_bill_id(chat_id: str, bill_id: Optional[str]):
        conn = get_connection()
        with conn:
            conn.execute("""
                INSERT INTO chat_sessions (chat_id, active_bill_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    active_bill_id = excluded.active_bill_id,
                    updated_at = CURRENT_TIMESTAMP;
            """, (str(chat_id), bill_id))

    @staticmethod
    def clear_active_bill(chat_id: str):
        conn = get_connection()
        with conn:
            conn.execute("UPDATE chat_sessions SET active_bill_id = NULL WHERE chat_id = ?;", (str(chat_id),))

    @staticmethod
    def reset_chat_session(chat_id: str):
        """
        Clears conversation state and active draft bill for /new chat.
        NOTE: Long-term store preferences (in owner_preferences) are NOT touched.
        """
        conn = get_connection()
        with conn:
            conn.execute("""
                INSERT INTO chat_sessions (chat_id, active_bill_id, history_json, updated_at)
                VALUES (?, NULL, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    active_bill_id = NULL,
                    history_json = NULL,
                    updated_at = CURRENT_TIMESTAMP;
            """, (str(chat_id),))
