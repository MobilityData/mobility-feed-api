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
        return cls(
            id=sub.id,
            user_id=sub.user_id,
            notification_id=sub.notification_type_id,
            active=sub.active,
            last_notified_at=sub.last_notified_at,
            created_at=sub.created_at,
        )
