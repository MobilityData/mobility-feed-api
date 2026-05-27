"""
MCP tool: get_validation_results
Retrieves validation results for a GTFS feed enriched with rule docs and GTFS file samples.
"""
import csv
import io
import json
import logging
import os
from typing import Optional

import httpx
from sqlalchemy.orm import joinedload

from rules_cache import get_rules_cache
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Gtfsfeed, Validationreport

logger = logging.getLogger(__name__)

SAMPLE_ROWS = 10
SEVERITY_MAP = {
    "errors": "ERROR",
    "warnings": "WARNING",
    "info": "INFO",
}


def _fetch_gtfs_sample(feed_stable_id: str, dataset_stable_id: str, filename: str) -> Optional[dict]:
    """Fetch a GTFS CSV file from GCS and return columns, sample rows, and total row count."""
    datasets_bucket_url = os.getenv("DATASETS_BUCKET_URL", "")
    if not datasets_bucket_url:
        return None

    url = f"{datasets_bucket_url}/{feed_stable_id}/{dataset_stable_id}/extracted/{filename}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            content = response.text
    except Exception as exc:
        logger.warning("Failed to fetch GTFS file %s: %s", url, exc)
        return None

    reader = csv.DictReader(io.StringIO(content))
    columns = reader.fieldnames or []
    rows = []
    total = 0
    for row in reader:
        total += 1
        if len(rows) < SAMPLE_ROWS:
            rows.append(dict(row))

    return {
        "filename": filename,
        "source_url": url,
        "columns": list(columns),
        "sample_rows": rows,
        "total_rows": total,
    }


def get_validation_results_tool(
    feed_id: str,
    severity_filter: Optional[str] = "all",
) -> str:
    """
    Retrieve validation results for a GTFS feed, enriched with rule documentation
    and sample rows from the affected GTFS files.

    Args:
        feed_id: Mobility Database feed ID (e.g. "mdb-1210")
        severity_filter: Filter notices by severity. One of: all, errors, warnings, info. Default: all

    Returns:
        JSON string with feed metadata, validation summary, and enriched notice list
    """
    rules = get_rules_cache()

    db = Database()
    with db.start_db_session() as session:
        feed = (
            session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == feed_id)
            .options(
                joinedload(Gtfsfeed.latest_dataset)
                .joinedload(Gtfsdataset.validation_reports)
                .joinedload(Validationreport.notices),
                joinedload(Gtfsfeed.latest_dataset)
                .joinedload(Gtfsdataset.validation_reports)
                .joinedload(Validationreport.features),
            )
            .first()
        )

        if feed is None:
            return json.dumps({"error": f"Feed '{feed_id}' not found."})

        dataset = feed.latest_dataset
        if dataset is None:
            return json.dumps({"error": f"Feed '{feed_id}' has no dataset yet."})

        report: Optional[Validationreport] = None
        if dataset.validation_reports:
            report = max(dataset.validation_reports, key=lambda item: item.validated_at or 0)

        if report is None:
            return json.dumps(
                {
                    "feed_id": feed_id,
                    "provider": feed.provider,
                    "dataset_id": dataset.stable_id,
                    "error": "No validation report found for this feed.",
                }
            )

        severity_value = SEVERITY_MAP.get((severity_filter or "all").lower())
        notices = report.notices
        if severity_value:
            notices = [notice for notice in notices if notice.severity == severity_value]

        file_sample_cache: dict[str, Optional[dict]] = {}
        enriched_notices = []
        for notice in sorted(notices, key=lambda item: (item.severity or "", -(item.total_notices or 0))):
            rule_doc = rules.get_dict(notice.notice_code)

            affected_file_data = None
            affected_files = rule_doc.get("affected_files") if rule_doc else []
            if affected_files:
                primary_file = affected_files[0]
                if primary_file not in file_sample_cache:
                    file_sample_cache[primary_file] = _fetch_gtfs_sample(
                        feed_id, dataset.stable_id, primary_file
                    )
                affected_file_data = file_sample_cache[primary_file]

            enriched_notices.append(
                {
                    "code": notice.notice_code,
                    "severity": notice.severity,
                    "total_notices": notice.total_notices,
                    "rule_doc": rule_doc,
                    "affected_file": affected_file_data,
                }
            )

        feature_names = [feature.name for feature in report.features]

        result = {
            "feed_id": feed_id,
            "provider": feed.provider,
            "dataset_id": dataset.stable_id,
            "validated_at": str(report.validated_at) if report.validated_at else None,
            "validator_version": report.validator_version,
            "report_urls": {
                "json": report.json_report,
                "html": report.html_report,
            },
            "gtfs_features": feature_names,
            "summary": {
                "total_errors": report.total_error,
                "total_warnings": report.total_warning,
                "total_info": report.total_info,
                "unique_error_count": report.unique_error_count,
                "unique_warning_count": report.unique_warning_count,
                "unique_info_count": report.unique_info_count,
            },
            "notices": enriched_notices,
        }

    return json.dumps(result, default=str)
