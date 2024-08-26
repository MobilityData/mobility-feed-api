from typing import List

import sqlalchemy
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, and_

from database_gen.sqlacodegen_models import (
    Gbfsfeed,
    Gbfssnapshot,
    Gbfsvalidationreport,
    Gbfsnotice,
)
from .base_analytics_processor import BaseAnalyticsProcessor


class GBFSAnalyticsProcessor(BaseAnalyticsProcessor):
    def __init__(self, run_date):
        super().__init__(run_date)
        self.versions_metrics_data = []

    def get_latest_data(self) -> sqlalchemy.orm.Query:
        subquery = (
            self.session.query(
                Gbfssnapshot.feed_id,
                func.max(Gbfssnapshot.downloaded_at).label("max_downloaded_at"),
            )
            .filter(Gbfssnapshot.downloaded_at < self.run_date)
            .group_by(Gbfssnapshot.feed_id)
            .subquery()
        )

        query = (
            self.session.query(Gbfsfeed, Gbfssnapshot)
            .join(Gbfssnapshot, Gbfsfeed.id == Gbfssnapshot.feed_id)
            .join(
                subquery,
                and_(
                    Gbfssnapshot.feed_id == subquery.c.feed_id,
                    Gbfssnapshot.downloaded_at == subquery.c.max_downloaded_at,
                ),
            )
            .options(
                joinedload(Gbfsfeed.locations),
                joinedload(Gbfssnapshot.gbfsvalidationreports).joinedload(
                    Gbfsvalidationreport.gbfsnotices
                ),
                joinedload(Gbfssnapshot.gbfsvalidationreports),
            )
            .order_by(Gbfssnapshot.downloaded_at.desc())
        )
        return query

    def process_feed_data(self, feed: Gbfsfeed, snapshot: Gbfssnapshot, _) -> None:
        if feed.stable_id in self.processed_feeds:
            return
        self.processed_feeds.add(feed.stable_id)

        validation_reports = snapshot.gbfsvalidationreports
        if not validation_reports:
            return

        latest_validation_report = max(validation_reports, key=lambda x: x.validated_at)
        notices = latest_validation_report.gbfsnotices

        self.data.append(
            {
                "feed_id": feed.stable_id,
                "snapshot_id": snapshot.stable_id,
                "notices": [
                    {
                        "keyword": notice.keyword,
                        "gbfs_file": notice.gbfs_file,
                        "schema_path": notice.schema_path,
                    }
                    for notice in notices
                ],
                "created_on": feed.created_at,
                "operator": feed.operator,
                "locations": [
                    {
                        "country_code": location.country_code,
                        "country": location.country,
                        "municipality": location.municipality,
                        "subdivision_name": location.subdivision_name,
                    }
                    for location in feed.locations
                ],
            }
        )

        self.feed_metrics_data.append(
            {
                "feed_id": feed.stable_id,
                "computed_on": [self.run_date],
                "errors_count": [len(notices)],
            }
        )

        self._process_versions(feed)
        self._process_notices(notices)

    def save_summary(self) -> None:
        # Save the summary data for the current run date
        summary_file_name = f"summary/summary_{self.run_date.strftime('%Y-%m-%d')}.json"
        summary_data = {
            "feed_metrics": self.feed_metrics_data,
            "notices_metrics": self.notices_metrics_data,
            "versions_metrics": self.versions_metrics_data,
        }
        self._save_json(summary_file_name, summary_data)

    def save(self) -> None:
        metrics_file_data = {
            "feed_metrics": [],
            "versions_metrics": [],
            "notices_metrics": [],
        }
        merging_keys = {
            "feed_metrics": ["feed_id"],
            "versions_metrics": ["version"],
            "notices_metrics": ["keyword", "gbfs_file", "schema_path"],
        }
        self.aggregate_summary_files(metrics_file_data, merging_keys)

    def _process_versions(self, feed: Gbfsfeed) -> None:
        for version in feed.gbfsversions:
            existing_version_index = next(
                (
                    index
                    for (index, d) in enumerate(self.versions_metrics_data)
                    if d["version"] == version.version
                ),
                None,
            )
            if existing_version_index is not None:
                self.versions_metrics_data[existing_version_index]["feeds_count"][
                    -1
                ] += 1
            else:
                self.versions_metrics_data.append(
                    {
                        "version": version.version,
                        "computed_on": [self.run_date],
                        "feeds_count": [1],
                    }
                )

    def _process_notices(self, notices: List[Gbfsnotice]) -> None:
        for notice in notices:
            existing_notice_index = next(
                (
                    index
                    for (index, d) in enumerate(self.notices_metrics_data)
                    if d["keyword"] == notice.keyword
                    and d["gbfs_file"] == notice.gbfs_file
                    and d["schema_path"] == notice.schema_path
                ),
                None,
            )
            if existing_notice_index is not None:
                self.notices_metrics_data[existing_notice_index]["feeds_count"][-1] += 1
            else:
                self.notices_metrics_data.append(
                    {
                        "keyword": notice.keyword,
                        "gbfs_file": notice.gbfs_file,
                        "schema_path": notice.schema_path,
                        "computed_on": [self.run_date],
                        "feeds_count": [1],
                    }
                )
