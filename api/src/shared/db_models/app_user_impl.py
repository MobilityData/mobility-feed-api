from shared.notifications.notification_constants import NotificationTypeId
from shared.users_database_gen.sqlacodegen_models import AppUser, FeatureFlag
from user_service_gen.models.feature_flag import FeatureFlag as FeatureFlagModel
from user_service_gen.models.user_profile import UserProfile


class AppUserImpl(UserProfile):
    """Implementation of the UserProfile model.
    Converts a SQLAlchemy AppUser ORM object to a Pydantic UserProfile model.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        user: AppUser | None,
        all_flags: list[FeatureFlag] | None = None,
    ) -> UserProfile | None:
        if not user:
            return None

        # Always return every feature flag with its resolved value: the user's
        # override when set, otherwise the flag's default. A user need not be
        # explicitly linked to a flag to receive its default.
        overrides = {uff.feature_flag_id: uff.value for uff in (user.user_feature_flags or [])}
        features = [
            FeatureFlagModel(
                id=flag.id,
                name=flag.name,
                value_type=flag.value_type,
                value=overrides[flag.id] if overrides.get(flag.id) is not None else flag.default_value,
            )
            for flag in (all_flags or [])
        ]

        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            legacy_org_name=user.legacy_org_name,
            email_verified=user.email_verified,
            is_registered_to_receive_api_announcements=cls.is_registered_to_announcements(user),
            features=features,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def is_registered_to_announcements(user: AppUser) -> bool:
        """Whether the user has an active api.announcements subscription."""
        return any(
            sub.notification_type_id == NotificationTypeId.API_ANNOUNCEMENTS and sub.active
            for sub in user.notification_subscriptions
        )
