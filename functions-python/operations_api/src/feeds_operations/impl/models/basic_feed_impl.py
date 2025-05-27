from feeds_operations.impl.models.external_id_impl import ExternalIdImpl
from feeds_operations.impl.models.location_impl import LocationImpl
from feeds_operations.impl.models.redirect_impl import RedirectImpl
from feeds_operations_gen.models.base_feed import BaseFeed
from feeds_operations_gen.models.source_info import SourceInfo
from shared.database_gen.sqlacodegen_models import Feed


class BaseFeedImpl(BaseFeed):
    """Base implementation of the feeds models."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: Feed | None) -> BaseFeed | None:
        """Convert a SQLAlchemy row object to a Pydantic model."""
        if not feed:
            return None

        return cls(
            id=feed.id,
            stable_id=feed.stable_id,
            status=feed.status,
            data_type=feed.data_type,
            provider=feed.provider,
            feed_name=feed.feed_name,
            note=feed.note,
            feed_contact_email=feed.feed_contact_email,
            source_info=SourceInfo(
                producer_url=feed.producer_url,
                authentication_type=None
                if feed.authentication_type is None
                else int(feed.authentication_type),
                authentication_info_url=feed.authentication_info_url,
                api_key_parameter_name=feed.api_key_parameter_name,
                license_url=feed.license_url,
            ),
            operational_status=feed.operational_status,
            created_at=feed.created_at,
            official=feed.official,
            official_updated_at=feed.official_updated_at,
            locations=sorted(
                [LocationImpl.from_orm(item) for item in feed.locations],
                key=lambda x: (x.country_code or "", x.municipality or ""),
            ),
            external_ids=sorted(
                [ExternalIdImpl.from_orm(item) for item in feed.externalids],
                key=lambda x: x.external_id,
            ),
            redirects=sorted(
                [RedirectImpl.from_orm(item) for item in feed.redirectingids],
                key=lambda x: x.target_id,
            ),
        )
