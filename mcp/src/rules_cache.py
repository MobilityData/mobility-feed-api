"""
In-memory TTL cache for GTFS validator rule documentation.
Fetches rules.json from the official validator site on first use,
then serves from memory until TTL expires (default: 24 hours).
"""
import logging
import threading
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RULES_JSON_URL = "https://gtfs-validator.mobilitydata.org/rules.json"
RULES_BASE_URL = "https://gtfs-validator.mobilitydata.org/rules.html"
DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours


class RuleDoc:
    """Structured rule documentation entry."""

    __slots__ = ("code", "short_summary", "description", "affected_files", "rule_url")

    def __init__(
        self,
        code: str,
        short_summary: str,
        description: str,
        affected_files: list[str],
        rule_url: str,
    ):
        self.code = code
        self.short_summary = short_summary
        self.description = description
        self.affected_files = affected_files
        self.rule_url = rule_url

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "short_summary": self.short_summary,
            "affected_files": self.affected_files,
            "rule_url": self.rule_url,
        }


class RulesCache:
    """Thread-safe singleton cache for GTFS validator rule docs."""

    _instance: Optional["RulesCache"] = None
    _lock = threading.Lock()

    def __new__(cls, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> "RulesCache":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._ttl_seconds = ttl_seconds
                cls._instance._cache: dict[str, RuleDoc] = {}
                cls._instance._fetched_at: float = 0.0
                cls._instance._fetch_lock = threading.Lock()
        return cls._instance

    def _is_stale(self) -> bool:
        return time.monotonic() - self._fetched_at > self._ttl_seconds

    def _fetch_and_build(self) -> None:
        """Fetch rules.json and build the lookup dict. Called under _fetch_lock."""
        logger.info("Fetching GTFS validator rules from %s", RULES_JSON_URL)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(RULES_JSON_URL)
                response.raise_for_status()
                raw: dict = response.json()
        except Exception as exc:
            logger.error("Failed to fetch rules.json: %s", exc)
            # Keep serving stale data if we have it, otherwise propagate
            if not self._cache:
                raise
            logger.warning("Serving stale rules cache due to fetch failure")
            return

        new_cache: dict[str, RuleDoc] = {}
        for code, entry in raw.items():
            refs = entry.get("references", {})
            file_refs: list[str] = refs.get("fileReferences", []) or []
            new_cache[code] = RuleDoc(
                code=code,
                short_summary=entry.get("shortSummary", ""),
                description=entry.get("description", ""),
                affected_files=file_refs,
                rule_url=f"{RULES_BASE_URL}#{code}-rule",
            )

        self._cache = new_cache
        self._fetched_at = time.monotonic()
        logger.info("Rules cache populated: %d rules loaded", len(new_cache))

    def get(self, notice_code: str) -> Optional[RuleDoc]:
        """Look up a rule by notice code. Fetches/refreshes cache as needed."""
        if self._is_stale():
            with self._fetch_lock:
                # Double-check after acquiring lock
                if self._is_stale():
                    self._fetch_and_build()
        return self._cache.get(notice_code)

    def get_dict(self, notice_code: str) -> Optional[dict]:
        """Return the rule as a plain dict, or None if unknown."""
        rule = self.get(notice_code)
        return rule.to_dict() if rule else None

    @property
    def size(self) -> int:
        return len(self._cache)


_rules_cache: Optional[RulesCache] = None


def get_rules_cache() -> RulesCache:
    """Return the module-level RulesCache singleton."""
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = RulesCache()
    return _rules_cache
