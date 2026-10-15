from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as NotificationSubscriptionOrm
from user_service_gen.models.notification_subscription import NotificationSubscription
from user_service_gen.models.subscription_feed import SubscriptionFeed


class NotificationSubscriptionImpl(NotificationSubscription):
    """Implementation of the NotificationSubscription model.
    Converts a SQLAlchemy NotificationSubscription ORM object to a Pydantic NotificationSubscription model.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        sub: NotificationSubscriptionOrm | None,
        feed_metadata: dict | None = None,
    ) -> NotificationSubscription | None:
        if not sub:
            return None
        # The subscription's targeted feeds come from the notification_subscription_feed join
        # table (sorted by stable ID for a stable response). Each feed is enriched with
        # data_type/provider/feed_name resolved (by the caller) from the feeds DB; metadata is
        # absent for a feed that no longer exists, so its fields stay null.
        feed_metadata = feed_metadata or {}
        feeds = [
            SubscriptionFeed(
                feed_id=stable_id,
                data_type=feed_metadata.get(stable_id, {}).get("data_type"),
                provider=feed_metadata.get(stable_id, {}).get("provider"),
                feed_name=feed_metadata.get(stable_id, {}).get("feed_name"),
            )
            for stable_id in sorted(f.feed_stable_id for f in sub.notification_subscription_feeds)
        ]
        return cls(
            id=sub.id,
            user_id=sub.user_id,
            notification_id=sub.notification_type_id,
            active=sub.active,
            created_at=sub.created_at,
            feeds=feeds or None,
        )
