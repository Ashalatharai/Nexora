from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ConversationSession(BaseModel):
    session_id: str
    last_item_name: Optional[str] = None
    last_customer_name: Optional[str] = None
    pending_action: Optional[Dict[str, Any]] = None
    pending_description: Optional[str] = None
    last_clarification: Optional[str] = None
    history: List[Dict[str, str]] = []


class ContextManager:
    """
    Lightweight, thread-safe in-memory session scoped conversation manager.
    Maintains active entities, pending confirmations, and recent conversation turns.
    """
    _sessions: Dict[str, ConversationSession] = {}

    @classmethod
    def get_session(cls, session_id: Optional[str]) -> ConversationSession:
        sid = session_id or "default"
        if sid not in cls._sessions:
            cls._sessions[sid] = ConversationSession(session_id=sid)
        return cls._sessions[sid]

    @classmethod
    def set_last_item(cls, session_id: str, item_name: str):
        session = cls.get_session(session_id)
        session.last_item_name = item_name.strip().lower()

    @classmethod
    def set_last_customer(cls, session_id: str, customer_name: str):
        session = cls.get_session(session_id)
        session.last_customer_name = customer_name.strip().title()

    @classmethod
    def set_pending(cls, session_id: str, action_data: Dict[str, Any], description: str):
        session = cls.get_session(session_id)
        session.pending_action = action_data
        session.pending_description = description

    @classmethod
    def clear_pending(cls, session_id: str) -> Optional[Dict[str, Any]]:
        session = cls.get_session(session_id)
        action = session.pending_action
        session.pending_action = None
        session.pending_description = None
        return action

    @classmethod
    def add_history(cls, session_id: str, role: str, text: str):
        session = cls.get_session(session_id)
        session.history.append({"role": role, "text": text})
        # Keep maximum 20 recent messages in memory per session
        if len(session.history) > 20:
            session.history.pop(0)

    @classmethod
    def reset_session(cls, session_id: str):
        if session_id in cls._sessions:
            del cls._sessions[session_id]
