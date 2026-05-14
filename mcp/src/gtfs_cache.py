import os
import threading
import time
from typing import Callable, Optional

import duckdb

DEFAULT_TTL_SECONDS = int(os.getenv("FEED_CACHE_TTL_SECONDS", "600"))


class _CacheEntry:
    __slots__ = ("connection", "loaded_at", "lock")

    def __init__(self):
        self.connection: Optional[duckdb.DuckDBPyConnection] = None
        self.loaded_at: float = 0.0
        self.lock = threading.Lock()


class GtfsCache:
    """Thread-safe singleton TTL cache for GTFS DuckDB connections."""

    _instance: Optional["GtfsCache"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> "GtfsCache":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._ttl_seconds = ttl_seconds
                    cls._instance._cache: dict[tuple[str, str], _CacheEntry] = {}
                    cls._instance._cache_lock = threading.Lock()
        return cls._instance

    def _is_fresh(self, entry: _CacheEntry) -> bool:
        return (
            entry.connection is not None
            and time.monotonic() - entry.loaded_at <= self._ttl_seconds
        )

    def get_or_load(
        self,
        feed_id: str,
        dataset_id: str,
        loader_fn: Callable[[], duckdb.DuckDBPyConnection],
    ) -> duckdb.DuckDBPyConnection:
        key = (feed_id, dataset_id)
        entry = self._cache.get(key)
        if entry and self._is_fresh(entry):
            return entry.connection

        if entry is None:
            with self._cache_lock:
                entry = self._cache.get(key)
                if entry is None:
                    entry = _CacheEntry()
                    self._cache[key] = entry

        old_connection: Optional[duckdb.DuckDBPyConnection] = None
        with entry.lock:
            if self._is_fresh(entry):
                return entry.connection
            old_connection = entry.connection
            entry.connection = loader_fn()
            entry.loaded_at = time.monotonic()
            connection = entry.connection

        if old_connection is not None and old_connection is not connection:
            try:
                old_connection.close()
            except Exception:
                pass

        return connection


_gtfs_cache: Optional[GtfsCache] = None
_gtfs_cache_lock = threading.Lock()


def get_gtfs_cache() -> GtfsCache:
    """Return the module-level GTFS cache singleton."""
    global _gtfs_cache
    if _gtfs_cache is None:
        with _gtfs_cache_lock:
            if _gtfs_cache is None:
                _gtfs_cache = GtfsCache()
    return _gtfs_cache
