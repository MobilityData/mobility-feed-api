from feeds_gen.models.feed_related_link import FeedRelatedLink
from shared.database_gen.sqlacodegen_models import Feedrelatedlink


class FeedRelatedLinkImpl(FeedRelatedLink):
    """Implementation of the FeedRelatedLink model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed_related_link_orm: Feedrelatedlink) -> FeedRelatedLink | None:
        if not feed_related_link_orm:
            return None
        return cls(
            code=feed_related_link_orm.code,
            url=feed_related_link_orm.url,
            description=feed_related_link_orm.description,
            created_at=feed_related_link_orm.created_at,
        )

    @classmethod
    def to_orm_from_dict(cls, feedrelaticlink_dict: dict) -> Feedrelatedlink | None:
        """Convert a dict to a SQLAlchemy row object."""
        if not feedrelaticlink_dict:
            return None
        result = Feedrelatedlink(
            code=feedrelaticlink_dict.get("code"),
            url=feedrelaticlink_dict.get("url"),
            description=feedrelaticlink_dict.get("description"),
        )
        return result
