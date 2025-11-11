import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List

from shared.common.db_utils import normalize_url, normalize_url_str
from shared.database_gen.sqlacodegen_models import License


@dataclass
class MatchingLicense:
    """Response structure for license URL resolution."""

    license_id: str
    license_url: str
    normalized_url: str
    match_type: str
    confidence: float
    spdx_id: str | None = None
    matched_name: str | None = None
    matched_catalog_url: str | None = None
    matched_source: str | None = None


# The COMMON_PATTERNS list contains tuples of (regex pattern, SPDX ID).
# It is used for heuristic matching of license URLs.
COMMON_PATTERNS = [
    (re.compile(r"opendatacommons\.org/licenses/odbl/1\.0/?", re.I), "ODbL-1.0"),
    (re.compile(r"opendatacommons\.org/licenses/by/1\.0/?", re.I), "ODC-By-1.0"),
    (re.compile(r"opendatacommons\.org/licenses/pddl/1\.0/?", re.I), "PDDL-1.0"),
    (re.compile(r"opensource\.org/licenses/Apache-2\.0/?", re.I), "Apache-2.0"),
    (re.compile(r"opensource\.org/licenses/MIT/?", re.I), "MIT"),
    (re.compile(r"choosealicense\.com/licenses/mit/?", re.I), "MIT"),
    (re.compile(r"choosealicense\.com/licenses/apache-2\.0/?", re.I), "Apache-2.0"),
    # add Etalab / Québec, etc., once verified
]


def extract_host(url: str) -> str:
    """Extract host only from normalized URL."""
    # if the url has protocol like http://, normalize_url_str should have removed it
    normalized_url = normalize_url_str(url)
    return normalized_url.split("/", 1)[0] if normalized_url else ""


def resolve_commons_creative_license(url: str) -> str | None:
    """Resolve Creative Commons license from URL to SPDX ID."""
    # Use string-normalization util, not SQL-expression variant
    n = normalize_url_str(url)
    n = re.sub(r"/legalcode(\.[a-zA-Z\-]+)?$", "", n, flags=re.I)
    n = re.sub(r"/deed(\.[a-zA-Z\-]+)?$", "", n, flags=re.I)
    # CC0
    if re.search(r"creativecommons\.org/publicdomain/zero/1\.0/?$", n, re.I):
        return "CC0-1.0"
    # CC BY family + optional locale
    m = re.search(r"creativecommons\.org/licenses/([a-z\-]+)/([\d\.]+)(?:/[a-z]{2})?/?$", n, re.I)
    if m:
        code = m.group(1).lower()
        ver = m.group(2)
        mapping = {
            "by": "CC-BY",
            "by-sa": "CC-BY-SA",
            "by-nd": "CC-BY-ND",
            "by-nc": "CC-BY-NC",
            "by-nc-sa": "CC-BY-NC-SA",
            "by-nc-nd": "CC-BY-NC-ND",
        }
        base = mapping.get(code)
        if base:
            if code == "by" and re.search(r"/licenses/by/2\.1/jp/?$", n, re.I):
                return "CC-BY-2.1-JP"
            return f"{base}-{ver}"
    return None


def heuristic_spdx(url: str) -> str | None:
    """Heuristic SPDX resolver based on common URL patterns."""
    for rx, spdx in COMMON_PATTERNS:
        if rx.search(url) or rx.search(normalize_url_str(url)):
            return spdx
    return None


def fuzzy_ratio(a: str, b: str) -> float:
    """Compute fuzzy similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def resolve_fuzzy_match(
    url_str: str,
    url_host: str,
    url_normalized: str,
    fuzzy_threshold: float,
    db_session: Session | None = None,
    max_candidates: int | None = 5,
) -> List[MatchingLicense]:
    """Fuzzy match license URL against same-host candidates in DB.

    Returns a sorted list of candidates (best first) whose similarity is >= fuzzy_threshold.
    """
    if not db_session or not url_host:
        return []

    # Pull candidates from DB and filter by host in Python, based on License.url
    db_licenses: list[License] = list(db_session.scalars(select(License)))
    same_host: list[License] = []
    for lic in db_licenses:
        if not getattr(lic, "url", None):
            continue
        if extract_host(normalize_url_str(lic.url)) == url_host:
            same_host.append(lic)

    scored: list[tuple[float, License]] = []
    for lic in same_host:
        lic_norm = normalize_url_str(lic.url)
        score = fuzzy_ratio(url_normalized, lic_norm)
        if score >= fuzzy_threshold:
            scored.append((float(score), lic))

    # Sort by descending score and optionally limit
    scored.sort(key=lambda x: x[0], reverse=True)
    if max_candidates is not None:
        scored = scored[:max_candidates]

    results: List[MatchingLicense] = []
    for score, lic in scored:
        results.append(
            MatchingLicense(
                license_id=lic.id,
                license_url=url_str,
                normalized_url=url_normalized,
                spdx_id=lic.id,
                match_type="fuzzy",
                confidence=round(score, 3),
                matched_name=lic.name,
                matched_catalog_url=lic.url,
                matched_source="db.license",
            )
        )
    return results


def resolve_license(
    license_url: str,
    allow_fuzzy: bool = True,
    fuzzy_threshold: float = 0.94,
    db_session: Session | None = None,
) -> List[MatchingLicense]:
    """Resolve a license URL to one or more SPDX candidates using multiple strategies.

    Strategies (in order of precedence):
      1) Exact match in DB(db.license)            -> return [exact]
      2) Creative Commons resolver(cc-resolver)    -> return [cc]
      3) Generic heuristics(pattern-heuristics)           -> return [heuristic]
      4) Fuzzy (same host candidates) -> return [fuzzy...]
      5) No match                     -> return [none]

    Args:
        license_url (str): The license URL to resolve.
        allow_fuzzy (bool): Whether to allow fuzzy matching.
        fuzzy_threshold (float): Minimum similarity ratio for fuzzy match.
        db_session (Session | None): SQLAlchemy DB session. Required for DB-based strategies.

    Returns:
        List[MatchingLicense]: Ordered list of resolution results. Empty if no match.
    """
    url_str = str(license_url)
    url_normalized = normalize_url_str(url_str)
    url_host = extract_host(url_normalized)

    # 1) Exact hit in DB (compare normalized strings of known licenses)
    exact_match: License | None = find_exact_match_license_url(url_normalized, db_session) if db_session else None
    if exact_match:
        return [
            MatchingLicense(
                license_id=exact_match.id,
                license_url=url_str,
                normalized_url=url_normalized,
                spdx_id=exact_match.id,
                match_type="exact",
                confidence=1.0,
                matched_name=exact_match.name,
                matched_catalog_url=exact_match.url,
                matched_source="db.license",
            )
        ]

    # 2) Creative Commons resolver
    common_creative_match = resolve_commons_creative_license(url_str)
    if common_creative_match:
        return [
            MatchingLicense(
                license_id=common_creative_match,
                license_url=url_str,
                normalized_url=url_normalized,
                spdx_id=common_creative_match,
                match_type="heuristic",
                confidence=0.99,
                matched_name=None,
                matched_catalog_url=None,
                matched_source="cc-resolver",
            )
        ]

    # 3) Generic heuristics
    heuristic_match = heuristic_spdx(url_str)
    if heuristic_match:
        return [
            MatchingLicense(
                license_id=heuristic_match,
                license_url=url_str,
                normalized_url=url_normalized,
                spdx_id=heuristic_match,
                match_type="heuristic",
                confidence=0.95,
                matched_source="pattern-heuristics",
            )
        ]

    # 4) Fuzzy (same host candidates only)
    if allow_fuzzy and url_host and db_session is not None:
        fuzzy_results = resolve_fuzzy_match(
            url_str=url_str,
            url_host=url_host,
            url_normalized=url_normalized,
            fuzzy_threshold=fuzzy_threshold,
            db_session=db_session,
        )
        if fuzzy_results:
            return fuzzy_results

    # 5) No match
    return []


def find_exact_match_license_url(url_normalized: str, db_session: Session | None) -> License | None:
    """Find exact match of normalized license URL in DB (License.url)."""
    if not db_session:
        return None
    # Compare normalized strings using SQL functions on License.url
    return (
        db_session.query(License)
        .filter(normalize_url_str(url_normalized) == func.lower(func.trim(normalize_url(License.url))))
        .first()
    )
