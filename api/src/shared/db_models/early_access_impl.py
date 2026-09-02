"""Implementation of the EarlyAccessGrant model.
Converts a user's EarlyAccessEnrollment rows to the pydantic EarlyAccessGrant response for
`GET /v1/user/early-access`. Follows `app_user_impl.py`'s conversion pattern.
"""

from shared.users_database_gen.sqlacodegen_models import AppUser
from user_service_gen.models.early_access_grant import EarlyAccessGrant
from user_service_gen.models.feature_flag import FeatureFlag as FeatureFlagModel


class EarlyAccessImpl:
    """Converts the authenticated user's EarlyAccessEnrollment rows to EarlyAccessGrant models."""

    @classmethod
    def from_orm(cls, user: AppUser | None) -> list[EarlyAccessGrant]:
        if not user:
            return []

        # Same resolution as AppUserImpl.from_orm: the user's override wins, falling back to the
        # flag's global default. The override is exactly what grant_program_flags wrote (unless
        # an operator already set it directly), so this matches what GET /v1/user shows.
        overrides = {uff.feature_flag_id: uff.value for uff in (user.user_feature_flags or [])}

        grants = []
        for enrollment in sorted(user.early_access_enrollments or [], key=lambda e: e.enrolled_at):
            program = enrollment.program
            features = [
                FeatureFlagModel(
                    id=grant.feature_flag.id,
                    name=grant.feature_flag.name,
                    value_type=grant.feature_flag.value_type,
                    value=(
                        overrides[grant.feature_flag_id]
                        if overrides.get(grant.feature_flag_id) is not None
                        else grant.feature_flag.default_value
                    ),
                )
                for grant in (program.early_access_program_feature_flags or [])
                if not grant.feature_flag.disabled
            ]
            grants.append(
                EarlyAccessGrant(
                    program_id=program.id,
                    program_name=program.name,
                    enrolled_at=enrollment.enrolled_at,
                    features=features,
                )
            )
        return grants
