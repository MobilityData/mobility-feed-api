from shared.users_database_gen.sqlacodegen_models import AppUser
from user_service_gen.models.feature_flag import FeatureFlag as FeatureFlagModel
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
                FeatureFlagModel(id=ff.id, name=ff.name, description=ff.description)
                for ff in (user.feature_flags or [])
            ],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
