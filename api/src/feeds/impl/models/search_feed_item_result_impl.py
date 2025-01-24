from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.search_feed_item_result import SearchFeedItemResult
from feeds_gen.models.source_info import SourceInfo
import pycountry


class SearchFeedItemResultImpl(SearchFeedItemResult):
    """Implementation of the `SearchFeedItemResult` model.
    This class converts a SQLAlchemy row object to a Pydantic model instance taking in consideration the data type.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm_gtfs(cls, feed_search_row):
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
                authentication_type=int(feed_search_row.authentication_type)
                if feed_search_row.authentication_type
                else None,
                authentication_info_url=feed_search_row.authentication_info_url,
                api_key_parameter_name=feed_search_row.api_key_parameter_name,
                license_url=feed_search_row.license_url,
            ),
            redirects=feed_search_row.redirect_ids,
            locations=feed_search_row.locations,
            latest_dataset=LatestDataset(
                id=feed_search_row.latest_dataset_id,
                hosted_url=feed_search_row.latest_dataset_hosted_url,
                downloaded_at=feed_search_row.latest_dataset_downloaded_at,
                hash=feed_search_row.latest_dataset_hash,
                service_date_range_start=feed_search_row.latest_dataset_service_date_range_start,
                service_date_range_end=feed_search_row.latest_dataset_service_date_range_end,
            )
            if feed_search_row.latest_dataset_id
            else None,
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
                authentication_type=int(feed_search_row.authentication_type)
                if feed_search_row.authentication_type
                else None,
                authentication_info_url=feed_search_row.authentication_info_url,
                api_key_parameter_name=feed_search_row.api_key_parameter_name,
                license_url=feed_search_row.license_url,
            ),
            redirects=feed_search_row.redirect_ids,
            locations=feed_search_row.locations,
            entity_types=feed_search_row.entities,
            feed_references=feed_search_row.feed_reference_ids,
        )

    @classmethod
    def _translate_locations(cls, feed_search_row):
        """Translate location information in the feed search row.
        This method modifies the locations in the feed search row in place."""
        if feed_search_row.locations is None:
            return
        country_translations = cls._create_translation_dict(feed_search_row.country_translations)
        subdivision_translations = cls._create_translation_dict(feed_search_row.subdivision_name_translations)
        municipality_translations = cls._create_translation_dict(feed_search_row.municipality_translations)

        for location in feed_search_row.locations:
            location["country"] = country_translations.get(location["country"], location["country"])
            if location["country"] is None or len(location["country"]) == 0:
                location["country"] = SearchFeedItemResultImpl.resolve_country_by_code(location)
            location["subdivision_name"] = subdivision_translations.get(
                location["subdivision_name"], location["subdivision_name"]
            )
            location["municipality"] = municipality_translations.get(location["municipality"], location["municipality"])

    @classmethod
    def resolve_country_by_code(cls, location):
        """Resolve country name by country code.
        If the country code is not found, return the original country name."""
        country = pycountry.countries.get(alpha_2=location["country_code"])
        return country.name if country else location["country"]

    @staticmethod
    def _create_translation_dict(translations):
        """Helper method to create a translation dictionary."""
        if translations:
            return {
                elem.get("key"): elem.get("value") for elem in translations if elem.get("key") and elem.get("value")
            }
        return {}

    @classmethod
    def from_orm(cls, feed_search_row):
        """Create a model instance from a SQLAlchemy row object."""
        if feed_search_row is None:
            return None

        # Translate location data
        cls._translate_locations(feed_search_row)

        match feed_search_row.data_type:
            case "gtfs":
                return cls.from_orm_gtfs(feed_search_row)
            case "gtfs_rt":
                return cls.from_orm_gtfs_rt(feed_search_row)
            case _:
                raise ValueError(f"Unknown data type: {feed_search_row.data_type}")
