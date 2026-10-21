from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.services.intent import Metric


@dataclass
class SessionContext:
    city: str | None = None
    cities: list[str] = field(default_factory=list)
    metric: Metric | None = None
    dataset: str | None = None
    day_filter: str | None = None
    date: str | None = None
    hour: int | None = None
    last_intent: str | None = None
    last_reply_kind: str | None = None


class SessionStore:
    """In-memory multi-turn context keyed by session_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}
        self._lock = Lock()

    def get(self, session_id: str | None) -> SessionContext:
        if not session_id:
            return SessionContext()
        with self._lock:
            return self._sessions.setdefault(session_id, SessionContext())

    def update(self, session_id: str | None, **kwargs: Any) -> SessionContext:
        ctx = self.get(session_id)
        if not session_id:
            return ctx
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(ctx, key) and value is not None:
                    setattr(ctx, key, value)
            self._sessions[session_id] = ctx
            return ctx
