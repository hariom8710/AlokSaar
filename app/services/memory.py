"""
Memory — conversation history storage and retrieval.

Wraps the ChatMessage model so the rest of the pipeline (conversation
manager, context builder) doesn't need to know about SQLAlchemy directly.
Works identically against SQLite or PostgreSQL — no database-specific code.
"""
from app.extensions import db
from app.models import ChatMessage

MAX_HISTORY_TURNS = 10  # keep context window sane


def load_recent_history(session_id: str) -> list:
    """Returns the last N turns as [{"role": ..., "content": ...}, ...],
    oldest first — ready to hand straight to an LLM call."""
    messages = (
        ChatMessage.query.filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_TURNS)
        .all()
    )
    messages.reverse()  # back to chronological order
    return [{"role": m.role, "content": m.content} for m in messages]


def save_turn(session_id: str, role: str, content: str) -> ChatMessage:
    """Persists a single message (user or assistant) to history."""
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.session.add(msg)
    db.session.commit()
    return msg


def full_history(session_id: str) -> list:
    """All messages for a session, for the /api/chat/history endpoint."""
    messages = (
        ChatMessage.query.filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [m.to_dict() for m in messages]
