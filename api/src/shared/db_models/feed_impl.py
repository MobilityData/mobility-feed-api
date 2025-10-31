from shared.db_models.basic_feed_impl import BaseFeedImpl
from feeds_gen.models.feed import Feed
from shared.database_gen.sqlacodegen_models import Feed as FeedOrm
from shared.db_models.external_id_impl import ExternalIdImpl
from shared.db_models.feed_related_link_impl import FeedRelatedLinkImpl

from shared.db_models.location_impl import LocationImpl
from shared.db_models.redirect_impl import RedirectImpl


class FeedImpl(BaseFeedImpl, Feed):
    """Base implementation of the feeds models.
    This class converts a SQLAlchemy row DB object with common feed fields to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed_orm: FeedOrm | None) -> Feed | None:
        feed: Feed = super().from_orm(feed_orm)
        if not feed:
            return None
        feed.status = feed_orm.status
        feed.official = feed_orm.official
        feed.official_updated_at = feed_orm.official_updated_at
        feed.feed_name = feed_orm.feed_name
        feed.related_links = [FeedRelatedLinkImpl.from_orm(related_link) for related_link in feed_orm.feedrelatedlinks]
        feed.note = feed_orm.note
        return feed

    @classmethod
    def to_orm_from_dict(cls, feed_dict: dict | None) -> FeedOrm | None:
        """Convert a dictionary representation of a feed to a SQLAlchemy Feed ORM object."""
        if not feed_dict:
            return None
        result: Feed = FeedOrm(
            id=feed_dict.get("id"),
            stable_id=feed_dict.get("stable_id"),
            data_type=feed_dict.get("data_type"),
            created_at=feed_dict.get("created_at"),
            provider=feed_dict.get("provider"),
            feed_contact_email=feed_dict.get("feed_contact_email"),
            producer_url=feed_dict.get("producer_url"),
            authentication_type=None
            if feed_dict.get("authentication_type") is None
            else str(feed_dict.get("authentication_type")),
            authentication_info_url=feed_dict.get("authentication_info_url"),
            api_key_parameter_name=feed_dict.get("api_key_parameter_name"),
            license_url=feed_dict.get("license_url"),
            status=feed_dict.get("status"),
            official=feed_dict.get("official"),
            official_updated_at=feed_dict.get("official_updated_at"),
            feed_name=feed_dict.get("feed_name"),
            note=feed_dict.get("note"),
            externalids=sorted(
                [ExternalIdImpl.to_orm_from_dict(item) for item in feed_dict.get("externalids")],
                key=lambda x: x.associated_id,
            )
            if feed_dict.get("externalids")
            else [],
            redirectingids=sorted(
                [RedirectImpl.to_orm_from_dict(item) for item in feed_dict.get("redirectingids")],
                key=lambda x: x.target_id,
            )
            if feed_dict.get("redirectingids")
            else [],
            feedrelatedlinks=[FeedRelatedLinkImpl.to_orm_from_dict(item) for item in feed_dict.get("feedrelatedlinks")]
            if feed_dict.get("feedrelatedlinks")
            else [],
            locations=[LocationImpl.to_orm_from_dict(item) for item in feed_dict.get("locations")]
            if feed_dict.get("locations")
            else [],
        )
        return result
