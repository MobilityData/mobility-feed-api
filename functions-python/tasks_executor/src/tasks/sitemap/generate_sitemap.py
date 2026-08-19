#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Generate the mobilitydatabase.org sitemap and upload it to GCS.

One ``<url>`` entry is emitted per published, non-deprecated feed, pointing at
``{base_url}/feeds/{data_type}/{stable_id}``. The ``lastmod`` rule differs per
data type (see ``LASTMOD_FLOOR`` and the ``fetch_*`` helpers below); ``priority``
is a flat 0.8 and ``changefreq`` is deliberately omitted.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional
from xml.sax.saxutils import escape

from google.cloud import storage
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gbfsversion,
    Gtfsdataset,
    t_feedreference,
)

DEFAULT_BUCKET_NAME: str = "mobilitydatabase-sitemap"
DEFAULT_OBJECT_NAME: str = "sitemap.xml"
DEFAULT_BASE_URL: str = "https://mobilitydatabase.org"

# Every feed page is considered to have changed at least on this date (the date
# the current feed pages went live), so nothing reports a lastmod older than it.
LASTMOD_FLOOR: date = date(2026, 3, 5)

# Flat across all feeds: <priority> is relative-only, so equal values carry no
# signal, but it is kept for parity with the previous hand-maintained sitemap.
PRIORITY: str = "0.8"

# The sitemaps.org protocol caps a single file at 50,000 URLs / 50 MiB
# uncompressed. Past either we must split into a sitemap index.
MAX_URLS_PER_SITEMAP: int = 50_000
MAX_SITEMAP_BYTES: int = 50 * 1024 * 1024

# Ordering of the emitted entries; within a data type, entries sort by stable_id.
DATA_TYPE_ORDER: dict[str, int] = {"gtfs": 0, "gtfs_rt": 1, "gbfs": 2}


@dataclass(frozen=True)
class SitemapEntry:
    """A single ``<url>`` entry in the sitemap."""

    data_type: str
    stable_id: str
    lastmod: date

    def loc(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/feeds/{self.data_type}/{self.stable_id}"


def to_utc_date(value: Optional[datetime | date]) -> Optional[date]:
    """Normalize a timestamp to a UTC calendar date.

    Naive datetimes are read as UTC: the only naive timestamp columns in the
    schema are written by jobs that already store UTC.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(timezone.utc).date()
    return value


def resolve_lastmod(
    *candidates: Optional[datetime | date], floor: date = LASTMOD_FLOOR
) -> date:
    """Return the most recent of ``candidates``, never older than ``floor``."""
    dates = [d for d in (to_utc_date(c) for c in candidates) if d is not None]
    dates.append(floor)
    return max(dates)


def published_feed_filters() -> list:
    """Filters shared by all three data types.

    ``status`` must be one of the non-deprecated, non-null values; a NULL
    status (or ``deprecated``) excludes the feed from the sitemap.
    """
    return [
        Feed.operational_status == "published",
        Feed.status.in_(["future", "inactive", "active"]),
        Feed.stable_id.isnot(None),
    ]


def fetch_gtfs_entries(db_session: Session, floor: date) -> list[SitemapEntry]:
    """GTFS: lastmod is the feed's most recent dataset download, floored."""
    rows = (
        db_session.query(
            Feed.stable_id,
            func.max(Gtfsdataset.downloaded_at).label("latest_dataset_at"),
        )
        .select_from(Feed)
        .outerjoin(Gtfsdataset, Gtfsdataset.feed_id == Feed.id)
        .filter(Feed.data_type == "gtfs", *published_feed_filters())
        .group_by(Feed.stable_id)
        .all()
    )
    return [
        SitemapEntry("gtfs", stable_id, resolve_lastmod(latest_dataset_at, floor=floor))
        for stable_id, latest_dataset_at in rows
    ]


def fetch_gtfs_rt_entries(db_session: Session, floor: date) -> list[SitemapEntry]:
    """GTFS-RT: lastmod is the latest of the floor, the feed's own created_at,
    and the most recent dataset download across its related scheduled feeds.

    The schema records no "feed location last changed" timestamp, so the related
    GTFS feed's latest dataset stands in for it: locations are re-derived
    whenever a new dataset is processed.
    """
    rows = (
        db_session.query(
            Feed.stable_id,
            Feed.created_at,
            func.max(Gtfsdataset.downloaded_at).label("latest_related_dataset_at"),
        )
        .select_from(Feed)
        .outerjoin(t_feedreference, t_feedreference.c.gtfs_rt_feed_id == Feed.id)
        .outerjoin(Gtfsdataset, Gtfsdataset.feed_id == t_feedreference.c.gtfs_feed_id)
        .filter(Feed.data_type == "gtfs_rt", *published_feed_filters())
        .group_by(Feed.stable_id, Feed.created_at)
        .all()
    )
    return [
        SitemapEntry(
            "gtfs_rt",
            stable_id,
            resolve_lastmod(created_at, latest_related_dataset_at, floor=floor),
        )
        for stable_id, created_at, latest_related_dataset_at in rows
    ]


def fetch_gbfs_entries(db_session: Session, floor: date) -> list[SitemapEntry]:
    """GBFS: lastmod is the date the feed's newest GBFS version was recorded.

    ``gbfsversion`` rows are upserted on a stable id, so ``created_at`` only
    moves when the feed actually gains a version rather than on every crawl.
    """
    rows = (
        db_session.query(
            Feed.stable_id,
            func.max(Gbfsversion.created_at).label("latest_version_at"),
        )
        .select_from(Feed)
        .outerjoin(Gbfsversion, Gbfsversion.feed_id == Feed.id)
        .filter(Feed.data_type == "gbfs", *published_feed_filters())
        .group_by(Feed.stable_id)
        .all()
    )
    return [
        SitemapEntry("gbfs", stable_id, resolve_lastmod(latest_version_at, floor=floor))
        for stable_id, latest_version_at in rows
    ]


def collect_entries(
    db_session: Session, floor: date = LASTMOD_FLOOR
) -> list[SitemapEntry]:
    """Collect every sitemap entry, in a deterministic order."""
    entries = [
        *fetch_gtfs_entries(db_session, floor),
        *fetch_gtfs_rt_entries(db_session, floor),
        *fetch_gbfs_entries(db_session, floor),
    ]
    return sorted(
        entries,
        key=lambda entry: (
            DATA_TYPE_ORDER.get(entry.data_type, len(DATA_TYPE_ORDER)),
            entry.stable_id,
        ),
    )


def build_sitemap_xml(entries: Iterable[SitemapEntry], base_url: str) -> str:
    """Render entries as a sitemaps.org 0.9 urlset."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(entry.loc(base_url))}</loc>")
        lines.append(f"    <lastmod>{entry.lastmod.isoformat()}</lastmod>")
        lines.append(f"    <priority>{PRIORITY}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def upload_sitemap(
    xml: str, bucket_name: str, object_name: str, make_public: bool
) -> None:
    """Overwrite ``object_name`` in ``bucket_name`` with the rendered sitemap."""
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    blob.cache_control = "public, max-age=3600"
    blob.upload_from_string(xml, content_type="application/xml; charset=utf-8")
    logging.info(
        "Uploaded sitemap to gs://%s/%s (%d bytes).",
        bucket_name,
        object_name,
        len(xml.encode("utf-8")),
    )
    if make_public:
        try:
            blob.make_public()
        except Exception as exc:
            # Buckets with uniform bucket-level access reject per-object ACLs;
            # public read is granted at the bucket level there instead, so this
            # is not fatal to the upload that already succeeded.
            logging.warning(
                "Could not set a public ACL on gs://%s/%s: %s",
                bucket_name,
                object_name,
                exc,
            )


def generate_mobilitydatabase_sitemap_handler(payload: dict) -> dict:
    """Handler for generating the mobilitydatabase.org sitemap.

    Payload parameters:
        dry_run (bool): If True, build the sitemap but do not upload it. Default: True.
        bucket_name (str): Destination GCS bucket. Default: 'mobilitydatabase-sitemap'.
        object_name (str): Destination object name. Default: 'sitemap.xml'.
        base_url (str): Site origin used to build each <loc>. Default: 'https://mobilitydatabase.org'.
        make_public (bool): Set a public-read ACL on the uploaded object. Default: True.
        include_xml (bool): Return the rendered XML in the response. Default: False.
    """
    dry_run = payload.get("dry_run", True)
    bucket_name = payload.get("bucket_name", DEFAULT_BUCKET_NAME)
    object_name = payload.get("object_name", DEFAULT_OBJECT_NAME)
    base_url = payload.get("base_url", DEFAULT_BASE_URL)
    make_public = payload.get("make_public", True)
    include_xml = payload.get("include_xml", False)

    return generate_mobilitydatabase_sitemap(
        dry_run=dry_run,
        bucket_name=bucket_name,
        object_name=object_name,
        base_url=base_url,
        make_public=make_public,
        include_xml=include_xml,
    )


@with_db_session
def generate_mobilitydatabase_sitemap(
    dry_run: bool = True,
    bucket_name: str = DEFAULT_BUCKET_NAME,
    object_name: str = DEFAULT_OBJECT_NAME,
    base_url: str = DEFAULT_BASE_URL,
    make_public: bool = True,
    include_xml: bool = False,
    db_session: Session | None = None,
) -> dict:
    """Build the sitemap from the DB and (unless dry_run) upload it to GCS."""
    entries = collect_entries(db_session)
    xml = build_sitemap_xml(entries, base_url)
    size_bytes = len(xml.encode("utf-8"))

    counts: dict[str, int] = {data_type: 0 for data_type in DATA_TYPE_ORDER}
    for entry in entries:
        counts[entry.data_type] = counts.get(entry.data_type, 0) + 1
    logging.info(
        "Built sitemap with %d URLs (%s), %d bytes.",
        len(entries),
        ", ".join(f"{key}={value}" for key, value in counts.items()),
        size_bytes,
    )

    if len(entries) > MAX_URLS_PER_SITEMAP or size_bytes > MAX_SITEMAP_BYTES:
        # Still uploaded — a slightly oversized sitemap is better than none —
        # but it needs splitting into a sitemap index before crawlers reject it.
        logging.error(
            "Sitemap exceeds the sitemaps.org limits (%d URLs / %d bytes vs %d / %d). "
            "It must be split into a sitemap index.",
            len(entries),
            size_bytes,
            MAX_URLS_PER_SITEMAP,
            MAX_SITEMAP_BYTES,
        )

    if dry_run:
        logging.info(
            "Dry run: skipping upload to gs://%s/%s.", bucket_name, object_name
        )
    else:
        upload_sitemap(xml, bucket_name, object_name, make_public)

    result = {
        "dry_run": dry_run,
        "uploaded": not dry_run,
        "bucket_name": bucket_name,
        "object_name": object_name,
        "base_url": base_url,
        "url_count": len(entries),
        "counts_by_data_type": counts,
        "size_bytes": size_bytes,
    }
    if include_xml:
        result["xml"] = xml
    return result
