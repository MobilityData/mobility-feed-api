from typing import List, Dict

import sqlalchemy
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, and_
from database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Gtfsfeed,
    Validationreport,
    Notice,
    Feature,
    Feed,
    t_location_with_translations_en,
    Location,
)
from helpers.locations import translate_feed_locations
from .base_analytics_processor import BaseAnalyticsProcessor


class GTFSAnalyticsProcessor(BaseAnalyticsProcessor):
    def __init__(self, run_date):
        super().__init__(run_date)
        self.features_metrics_data = []

    def get_latest_data(self) -> sqlalchemy.orm.Query:
        subquery = (
            self.session.query(
                Gtfsdataset.feed_id,
                func.max(Gtfsdataset.downloaded_at).label("max_downloaded_at"),
            )
            .filter(Gtfsdataset.downloaded_at < self.run_date)
            .group_by(Gtfsdataset.feed_id)
            .subquery()
        )

        query = (
            self.session.query(Gtfsfeed, Gtfsdataset, t_location_with_translations_en)
            .join(Gtfsdataset, Gtfsfeed.id == Gtfsdataset.feed_id)
            .join(
                subquery,
                and_(
                    Gtfsdataset.feed_id == subquery.c.feed_id,
                    Gtfsdataset.downloaded_at == subquery.c.max_downloaded_at,
                ),
            )
            .outerjoin(Location, Feed.locations)
            .outerjoin(
                t_location_with_translations_en,
                Location.id == t_location_with_translations_en.c.location_id,
            )
            .where(Gtfsfeed.status != "deprecated")
            .options(
                joinedload(Gtfsfeed.locations),
                joinedload(Gtfsdataset.validation_reports).joinedload(
                    Validationreport.notices
                ),
                joinedload(Gtfsdataset.validation_reports).joinedload(
                    Validationreport.features
                ),
            )
            .order_by(Gtfsdataset.downloaded_at.desc())
        )
        return query

    def save_summary(self) -> None:
        # Save the summary data for the current run date
        summary_file_name = f"summary/summary_{self.run_date.strftime('%Y-%m-%d')}.json"
        summary_data = {
            "feed_metrics": self.feed_metrics_data,
            "notices_metrics": self.notices_metrics_data,
            "features_metrics": self.features_metrics_data,
        }
        self._save_json(summary_file_name, summary_data)


    def process_feed_data(
        self, feed: Feed, dataset: Gtfsdataset, translations: Dict
    ) -> None:
        if feed.stable_id in self.processed_feeds:
            return
        self.processed_feeds.add(feed.stable_id)

        validation_reports = dataset.validation_reports
        if not validation_reports:
            return

        translate_feed_locations(feed, translations)

        latest_validation_report = max(validation_reports, key=lambda x: x.validated_at)
        notices = latest_validation_report.notices
        errors = [notice for notice in notices if notice.severity == "ERROR"]
        warnings = [notice for notice in notices if notice.severity == "WARNING"]
        infos = [notice for notice in notices if notice.severity == "INFO"]
        features = latest_validation_report.features

        self.data.append(
            {
                "feed_id": feed.stable_id,
                "dataset_id": dataset.stable_id,
                "notices": {
                    "errors": [error.notice_code for error in errors],
                    "warnings": [warning.notice_code for warning in warnings],
                    "infos": [info.notice_code for info in infos],
                },
                "features": [feature.name for feature in features],
                "created_on": feed.created_at,
                "last_modified": dataset.downloaded_at,
                "provider": feed.provider,
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
                "errors_count": [len(errors)],
                "warnings_count": [len(warnings)],
                "infos_count": [len(infos)],
            }
        )

        self._process_features(features)
        self._process_notices(notices)

    def save(self) -> None:
        metrics_file_data = {
            "feed_metrics": [],
            "features_metrics": [],
            "notices_metrics": [],
        }
        merging_keys = {
            "feed_metrics": ["feed_id"],
            "features_metrics": ["feature"],
            "notices_metrics": ["notice", "severity"],
        }
        self.aggregate_summary_files(metrics_file_data, merging_keys)

    def _process_features(self, features: List[Feature]) -> None:
        for feature in features:
            existing_feature_index = next(
                (
                    index
                    for (index, d) in enumerate(self.features_metrics_data)
                    if d["feature"] == feature.name
                ),
                None,
            )
            if existing_feature_index is not None:
                self.features_metrics_data[existing_feature_index]["feeds_count"][
                    -1
                ] += 1
            else:
                self.features_metrics_data.append(
                    {
                        "feature": feature.name,
                        "computed_on": [self.run_date],
                        "feeds_count": [1],
                    }
                )

    def _process_notices(self, notices: List[Notice]) -> None:
        for notice in notices:
            existing_notice_index = next(
                (
                    index
                    for (index, d) in enumerate(self.notices_metrics_data)
                    if d["notice"] == notice.notice_code
                    and d["severity"] == notice.severity
                ),
                None,
            )
            if existing_notice_index is not None:
                self.notices_metrics_data[existing_notice_index]["feeds_count"][-1] += 1
            else:
                self.notices_metrics_data.append(
                    {
                        "notice": notice.notice_code,
                        "severity": notice.severity,
                        "computed_on": [self.run_date],
                        "feeds_count": [1],
                    }
                )
