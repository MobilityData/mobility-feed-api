"""Resolution of user-scoped feature flags (issue #1694).

Lives in `shared/common` rather than next to a single consumer because both the User Service and
the Feeds API gate behaviour on these flags, and the Feeds API must not import the User Service's
helpers - those pull in the Brevo SDK at module level.

The tables are `feature_flag` (the flag and its global default) and `user_feature_flag` (a
per-user override), both in the users database.
"""

import logging

from shared.users_database_gen.sqlacodegen_models import FeatureFlag, UserFeatureFlag

logger = logging.getLogger(__name__)


def feature_flag_enabled(db_session, user_id: str, flag_id: str) -> bool:
    """Resolve a boolean feature flag for a user.

    The user's override wins, falling back to the flag's default value; a missing flag denies
    (nothing to resolve). The ``disabled`` column is deliberately NOT consulted here: it only
    controls consumer-facing *exposure* (whether the flag is surfaced in the user profile's
    ``features`` list) — it is a backend concern and must not block a user who has been granted
    access from using the feature. Otherwise a disabled-but-granted flag would leave no way in.
    """
    flag = db_session.get(FeatureFlag, flag_id)
    if flag is None:
        logger.debug("feature flag %r not found; denying user %s", flag_id, user_id)
        return False
    override = db_session.get(UserFeatureFlag, (user_id, flag_id))
    value = override.value if override is not None and override.value is not None else flag.default_value
    enabled = value is True
    logger.debug(
        "feature flag %r for user %s: override=%r default=%r resolved=%r enabled=%s",
        flag_id,
        user_id,
        getattr(override, "value", None),
        flag.default_value,
        value,
        enabled,
    )
    return enabled
