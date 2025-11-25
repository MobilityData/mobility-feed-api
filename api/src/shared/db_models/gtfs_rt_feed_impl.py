import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.database.database import with_db_session
from shared.db_models.feed_impl import FeedImpl
from shared.database_gen.sqlacodegen_models import Gtfsrealtimefeed, Feed as FeedOrm, Entitytype
from shared.db_models.location_impl import LocationImpl
from feeds_gen.models.gtfs_rt_feed import GtfsRTFeed


class GtfsRTFeedImpl(FeedImpl, GtfsRTFeed):
    """Implementation of the 'Gtfsrealtimefeed' model."""

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    @with_db_session
    def from_orm(cls, feed: Gtfsrealtimefeed | None, db_session: Session) -> GtfsRTFeed | None:
        gtfs_rt_feed: GtfsRTFeed = super().from_orm(feed)
        if not gtfs_rt_feed:
            return None
        gtfs_rt_feed.locations = [LocationImpl.from_orm(item) for item in feed.locations] if feed.locations else []
        gtfs_rt_feed.entity_types = [item.name for item in feed.entitytypes] if feed.entitytypes else []

        provider_value = (feed.provider or "").strip().lower()

        query = db_session.query(FeedOrm).filter(
            func.lower(func.trim(FeedOrm.provider)) == provider_value,
            FeedOrm.stable_id != feed.stable_id,
        )

        gtfs_rt_feed.feed_references = [gtfs_feed.stable_id for gtfs_feed in query.all()]

        return gtfs_rt_feed

    @classmethod
    @with_db_session
    def to_orm_entity_types(cls, entity_types: list, db_session: Session) -> list[Entitytype]:
        """Convert the entity_types list to a list of Entitytype ORM objects."""
        if not entity_types:
            return []
        orm_entity_types = []
        for entity_type_name in entity_types:
            entity_type_orm = db_session.query(Entitytype).filter(Entitytype.name == entity_type_name).one_or_none()
            if entity_type_orm:
                orm_entity_types.append(entity_type_orm)
            else:
                logging.warning("Entity Type  not found: %s.", entity_type_name)
        return orm_entity_types

    @classmethod
    def to_orm_from_dict(cls, feed_dict: dict) -> Gtfsrealtimefeed | None:
        """Convert a dictionary representation of a GTFS RT feed to a SQLAlchemy GtfsRTFeed ORM object."""
        if not feed_dict:
            return None
        feed: FeedOrm = super().to_orm_from_dict(feed_dict)
        if not feed:
            return None
        allowed = {col.name for col in Gtfsrealtimefeed.__mapper__.columns} | {
            rel.key for rel in Gtfsrealtimefeed.__mapper__.relationships
        }
        data = {k: v for k, v in feed.__dict__.items() if k in allowed}
        result = Gtfsrealtimefeed(**data)
        result.entitytypes = cls.to_orm_entity_types(feed_dict.get("entity_types"))
        return result
