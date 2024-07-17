from feeds_gen.models.latest_dataset import LatestDataset
from feeds_gen.models.search_feed_item_result import SearchFeedItemResult
from feeds_gen.models.source_info import SourceInfo


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
    def from_orm(cls, feed_search_row):
        """Create a model instance from a SQLAlchemy row object."""
        if feed_search_row is None:
            return None
        match feed_search_row.data_type:
            case "gtfs":
                return cls.from_orm_gtfs(feed_search_row)
            case "gtfs_rt":
                return cls.from_orm_gtfs_rt(feed_search_row)
            case _:
                raise ValueError(f"Unknown data type: {feed_search_row.data_type}")
