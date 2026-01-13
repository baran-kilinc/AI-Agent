import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SessionData:
    messages: List[dict] = field(default_factory=list)
    last_access: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, ttl_seconds: int = 1800, max_messages: int = 20) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_messages = max_messages
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.Lock()

    def get_messages(self, session_id: str) -> List[dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            session.last_access = time.time()
            return list(session.messages)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(session_id, SessionData())
            session.last_access = time.time()
            session.messages.append({"role": role, "content": content})
            if len(session.messages) > self._max_messages:
                session.messages = session.messages[-self._max_messages :]

    def cleanup_expired(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [
                key
                for key, session in self._sessions.items()
                if now - session.last_access > self._ttl_seconds
            ]
            for key in expired_keys:
                del self._sessions[key]
                removed += 1
        return removed
