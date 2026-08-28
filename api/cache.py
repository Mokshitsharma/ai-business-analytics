# api/cache.py

import threading
import time
from typing import Any, Optional


class SimpleCache:
    """Thread-safe in-memory cache with per-key TTL."""

    def __init__(self):
        self._store: dict = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)

            if entry is None:
                return None

            data, expires_at = entry

            if expires_at is not None and time.time() > expires_at:
                del self._store[key]
                return None

            return data

    def set(self, key: str, data: Any, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None

        with self._lock:
            self._store[key] = (data, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
