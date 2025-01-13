from sqlalchemy.orm import joinedload
from sqlalchemy.orm.strategy_options import _AbstractLoad

from database_gen.sqlacodegen_models import Feed
from feeds.impl.models.external_id_impl import ExternalIdImpl
from feeds.impl.models.redirect_impl import RedirectImpl
from feeds_gen.models.basic_feed import BasicFeed
from feeds_gen.models.source_info import SourceInfo


class BaseFeedImpl(BasicFeed):
    """Base implementation of the feeds models.
    This class converts a SQLAlchemy row DB object with common feed fields to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: Feed | None, _=None) -> BasicFeed | None:
        if not feed:
            return None
        return cls(
            id=feed.stable_id,
            data_type=feed.data_type,
            status=feed.status,
            official=feed.official,
            official_updated_at=feed.official_updated_at,
            created_at=feed.created_at,
            external_ids=sorted(
                [ExternalIdImpl.from_orm(item) for item in feed.externalids], key=lambda x: x.external_id
            ),
            provider=feed.provider,
            feed_name=feed.feed_name,
            note=feed.note,
            feed_contact_email=feed.feed_contact_email,
            source_info=SourceInfo(
                producer_url=feed.producer_url,
                authentication_type=None if feed.authentication_type is None else int(feed.authentication_type),
                authentication_info_url=feed.authentication_info_url,
                api_key_parameter_name=feed.api_key_parameter_name,
                license_url=feed.license_url,
            ),
            redirects=sorted([RedirectImpl.from_orm(item) for item in feed.redirectingids], key=lambda x: x.target_id),
        )

    @staticmethod
    def get_joinedload_options() -> [_AbstractLoad]:
        """Returns common joinedload options for feeds queries."""
        return [
            joinedload(Feed.locations),
            joinedload(Feed.externalids),
            joinedload(Feed.redirectingids),
            joinedload(Feed.officialstatushistories),
        ]


class BasicFeedImpl(BaseFeedImpl, BasicFeed):
    """Implementation of the `BasicFeed` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
