"""
memory.py
─────────
Lightweight in-memory conversation store, keyed by session_id.

Each session keeps a trimmed list of (role, text) turns so that:
  - the LLM can be given recent conversation context when answering
  - follow-up questions ("what about for solar?") can be rewritten
    into standalone questions before retrieval (see llm_client.contextualize)

This is intentionally simple — a Python dict that lives as long as the
uvicorn process does. Restarting the server clears history. If you later
want persistence across restarts, swap the dict for SQLite/Redis behind
the same get_history / add_turn interface; nothing else needs to change.
"""

from collections import defaultdict, deque

# How many turns (user+assistant messages combined) to keep per session.
# 6 turns = roughly the last 3 question/answer exchanges — enough context
# for follow-ups without bloating the prompt sent to Groq.
MAX_TURNS = 6

_sessions: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_TURNS))


def get_history(session_id: str | None) -> list[dict]:
    """
    Returns the recent conversation history for a session as a list of
    {"role": "user" | "assistant", "text": str} dicts, oldest first.
    Returns an empty list if session_id is missing or unseen.
    """
    if not session_id:
        return []
    return list(_sessions[session_id])


def add_turn(session_id: str | None, role: str, text: str) -> None:
    """
    Appends a single turn to the session's history.
    No-op if session_id is missing (e.g. frontend didn't send one).
    """
    if not session_id:
        return
    _sessions[session_id].append({"role": role, "text": text})


def clear_session(session_id: str | None) -> None:
    """Removes a session's history entirely (used on 'New chat')."""
    if session_id and session_id in _sessions:
        del _sessions[session_id]
