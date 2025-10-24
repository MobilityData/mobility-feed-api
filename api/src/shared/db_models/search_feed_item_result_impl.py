from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.latest_dataset_validation_report import LatestDatasetValidationReport
from feeds_gen.models.search_feed_item_result import SearchFeedItemResult
from feeds_gen.models.source_info import SourceInfo
import pycountry

from shared.database_gen.sqlacodegen_models import t_feedsearch


class SearchFeedItemResultImpl(SearchFeedItemResult):
    """Implementation of the `SearchFeedItemResult` model.
    This class converts a SQLAlchemy row object to a Pydantic model instance taking in consideration the data type.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm_gtfs(cls, feed_search_row: t_feedsearch):
        """Create a model instance from a SQLAlchemy a GTFS row object."""
        return cls(
            id=feed_search_row.feed_stable_id,
            data_type=feed_search_row.data_type,
            status=feed_search_row.status,
            external_ids=feed_search_row.external_ids,
            provider=feed_search_row.provider,
            feed_name=feed_search_row.feed_name,
            official=feed_search_row.official,
            note=feed_search_row.note,
            feed_contact_email=feed_search_row.feed_contact_email,
            source_info=SourceInfo(
                producer_url=feed_search_row.producer_url,
                authentication_type=(
                    int(feed_search_row.authentication_type) if feed_search_row.authentication_type else None
                ),
                authentication_info_url=feed_search_row.authentication_info_url,
                api_key_parameter_name=feed_search_row.api_key_parameter_name,
                license_url=feed_search_row.license_url,
            ),
            redirects=feed_search_row.redirect_ids,
            locations=cls.resolve_locations(feed_search_row.locations),
            latest_dataset=(
                LatestDataset(
                    id=feed_search_row.latest_dataset_id,
                    hosted_url=feed_search_row.latest_dataset_hosted_url,
                    downloaded_at=feed_search_row.latest_dataset_downloaded_at,
                    hash=feed_search_row.latest_dataset_hash,
                    service_date_range_start=feed_search_row.latest_dataset_service_date_range_start,
                    service_date_range_end=feed_search_row.latest_dataset_service_date_range_end,
                    agency_timezone=feed_search_row.latest_dataset_agency_timezone,
                    validation_report=LatestDatasetValidationReport(
                        total_error=feed_search_row.latest_total_error,
                        total_warning=feed_search_row.latest_total_warning,
                        total_info=feed_search_row.latest_total_info,
                        unique_error_count=feed_search_row.latest_unique_error_count,
                        unique_warning_count=feed_search_row.latest_unique_warning_count,
                        unique_info_count=feed_search_row.latest_unique_info_count,
                        features=(
                            sorted([feature for feature in feed_search_row.latest_dataset_features])
                            if feed_search_row.latest_dataset_features
                            else []
                        ),
                    ),
                )
                if feed_search_row.latest_dataset_id
                else None
            ),
        )

    @classmethod
    def from_orm_gbfs(cls, feed_search_row):
        """Create a model instance from a SQLAlchemy a GTFS row object."""
        return cls(
            id=feed_search_row.feed_stable_id,
            data_type=feed_search_row.data_type,
            status=feed_search_row.status,
            external_ids=feed_search_row.external_ids,
            provider=feed_search_row.provider,
            feed_contact_email=feed_search_row.feed_contact_email,
            versions=feed_search_row.versions,
            source_info=SourceInfo(
                producer_url=feed_search_row.producer_url,
                authentication_type=(
                    int(feed_search_row.authentication_type) if feed_search_row.authentication_type else None
                ),
                authentication_info_url=feed_search_row.authentication_info_url,
                api_key_parameter_name=feed_search_row.api_key_parameter_name,
                license_url=feed_search_row.license_url,
            ),
            redirects=feed_search_row.redirect_ids,
            locations=cls.resolve_locations(feed_search_row.locations),
        )

    @classmethod
    def from_orm_gtfs_rt(cls, feed_search_row):
        """Create a model instance from a SQLAlchemy a GTFS-RT row object."""
        return cls(
            id=feed_search_row.feed_stable_id,
            data_type=feed_search_row.data_type,
            status=feed_search_row.status,
            external_ids=feed_search_row.external_ids,
            provider=feed_search_row.provider,
            feed_name=feed_search_row.feed_name,
            official=feed_search_row.official,
            note=feed_search_row.note,
            feed_contact_email=feed_search_row.feed_contact_email,
            source_info=SourceInfo(
                producer_url=feed_search_row.producer_url,
                authentication_type=(
                    int(feed_search_row.authentication_type) if feed_search_row.authentication_type else None
                ),
                authentication_info_url=feed_search_row.authentication_info_url,
                api_key_parameter_name=feed_search_row.api_key_parameter_name,
                license_url=feed_search_row.license_url,
            ),
            redirects=feed_search_row.redirect_ids,
            locations=cls.resolve_locations(feed_search_row.locations),
            entity_types=feed_search_row.entities,
            feed_references=feed_search_row.feed_reference_ids,
        )

    @classmethod
    def resolve_locations(cls, locations):
        """Resolve locations by country code."""
        if not locations or not isinstance(locations, list):
            return []
        return [
            {
                **location,
                "country": (
                    location.get("country") if location.get("country") else cls.resolve_country_by_code(location)
                ),
            }
            for location in locations
        ]

    @classmethod
    def resolve_country_by_code(cls, location):
        """Resolve country name by country code.
        If the country code is not found, return the original country name."""
        try:
            country = pycountry.countries.get(alpha_2=location.get("country_code"))
            return country.name if country else location.get("country")
        except AttributeError:
            return location.get("country")

    @classmethod
    def from_orm(cls, feed_search_row):
        """Create a model instance from a SQLAlchemy row object."""
        if feed_search_row is None:
            return None
        match feed_search_row.data_type:
            case "gtfs":
                return cls.from_orm_gtfs(feed_search_row)
            case "gtfs_rt":
                return cls.from_orm_gtfs_rt(feed_search_row)
            case "gbfs":
                return cls.from_orm_gbfs(feed_search_row)
            case _:
                raise ValueError(f"Unknown data type: {feed_search_row.data_type}")
