from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as NotificationSubscriptionOrm
from user_service_gen.models.notification_subscription import NotificationSubscription


class NotificationSubscriptionImpl(NotificationSubscription):
    """Implementation of the NotificationSubscription model.
    Converts a SQLAlchemy NotificationSubscription ORM object to a Pydantic NotificationSubscription model.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, sub: NotificationSubscriptionOrm | None) -> NotificationSubscription | None:
        if not sub:
            return None
        # feed_ids is the set of feed stable IDs this subscription targets, taken from the
        # notification_subscription_feed join table. Sorted for a stable response; None when
        # the subscription targets no feeds (i.e. non feed-scoped types).
        feed_ids = sorted(f.feed_stable_id for f in sub.notification_subscription_feeds)
        return cls(
            id=sub.id,
            user_id=sub.user_id,
            notification_id=sub.notification_type_id,
            active=sub.active,
            created_at=sub.created_at,
            feed_ids=feed_ids or None,
        )
