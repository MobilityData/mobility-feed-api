from typing import Optional, Any
from sqlalchemy.orm import Session
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import ConfigKey, ConfigValueFeed


@with_db_session
def get_config_value(
    namespace: str,
    key: str,
    feed_id: Optional[str] = None,
    db_session: Session = None,
) -> Optional[Any]:
    """
    Retrieves a configuration value from the database using the provided session.

    It first looks for a feed-specific override. If a feed_id is provided and a
    value is found, it returns that value.

    If no feed-specific value is found or no feed_id is provided, it looks for
    the global default value in the `config_key` table.

    :param namespace: The namespace of the configuration key.
    :param key: The configuration key.
    :param feed_id: The optional feed_id for a specific override.
    :param db_session: The SQLAlchemy session, injected by the `with_db_session` decorator.
    :return: The configuration value, or None if not found.
    """
    # 1. Try to get feed-specific value if feed_id is provided
    if feed_id:
        feed_config = (
            db_session.query(ConfigValueFeed.value)
            .filter(
                ConfigValueFeed.feed_id == feed_id,
                ConfigValueFeed.namespace == namespace,
                ConfigValueFeed.key == key,
            )
            .first()
        )
        if feed_config:
            return feed_config.value

    # 2. If not found or no feed_id, get the default value
    default_config = (
        db_session.query(ConfigKey.default_value).filter(ConfigKey.namespace == namespace, ConfigKey.key == key).first()
    )

    return default_config.default_value if default_config else None


# Example of how you would use it elsewhere in your application:
#
# from shared.config.config_reader import get_config_value
#
# def my_service_function():
#     # The `with_db_session` decorator handles creating and closing the session.
#     http_headers = get_config_value(
#         namespace='feed_download',
#         key='http_headers',
#         feed_id='mdb-2126'
#     )
#     print(f"HTTP Headers for mdb-2126: {http_headers}")
