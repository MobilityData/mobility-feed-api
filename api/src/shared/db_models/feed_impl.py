from shared.db_models.basic_feed_impl import BaseFeedImpl
from feeds_gen.models.feed import Feed
from shared.database_gen.sqlacodegen_models import Feed as FeedOrm
from shared.db_models.feed_related_link_impl import FeedRelatedLinkImpl


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
