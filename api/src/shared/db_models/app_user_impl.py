from shared.users_database_gen.sqlacodegen_models import AppUser
from user_service_gen.models.feature_flag import FeatureFlag as FeatureFlagModel
from user_service_gen.models.feature_flag_value import FeatureFlagValue
from user_service_gen.models.user_profile import UserProfile


class AppUserImpl(UserProfile):
    """Implementation of the UserProfile model.
    Converts a SQLAlchemy AppUser ORM object to a Pydantic UserProfile model.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, user: AppUser | None) -> UserProfile | None:
        if not user:
            return None

        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            legacy_org_name=user.legacy_org_name,
            email_verified=user.email_verified,
            is_registered_to_receive_api_announcements=user.is_registered_to_receive_api_announcements or False,
            features=[
                FeatureFlagModel(
                    id=uff.feature_flag.id,
                    name=uff.feature_flag.name,
                    value_type=uff.feature_flag.value_type,
                    value=FeatureFlagValue(
                        actual_instance=(uff.value if uff.value is not None else uff.feature_flag.default_value)
                    ),
                )
                for uff in (user.user_feature_flags or [])
                if uff.feature_flag.default_value is not None or uff.value is not None
            ],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
