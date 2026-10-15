from shared.users_database_gen.sqlacodegen_models import NotificationType as NotificationTypeOrm
from user_service_gen.models.notification_type import NotificationType


class NotificationTypeImpl(NotificationType):
    """Implementation of the NotificationType model.
    Converts a SQLAlchemy NotificationType ORM object to a Pydantic NotificationType model.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, notification_type: NotificationTypeOrm | None) -> NotificationType | None:
        if not notification_type:
            return None
        return cls(
            id=notification_type.id,
            description=notification_type.description,
        )
