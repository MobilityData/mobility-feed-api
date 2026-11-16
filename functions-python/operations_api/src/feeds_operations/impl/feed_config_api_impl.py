#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Per-feed config overrides: `config_key` is the catalog, `config_value_feed` the overrides.

Generic over every registered key. Nothing here knows what a key means: the shape of a
value is its schema in config_value_schemas, and what it does is up to the code that
reads it. Keys themselves are registered by migrations, never through this API.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from jsonschema.exceptions import best_match
from jsonschema.validators import validator_for
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from feeds_gen.apis.config_api_base import BaseConfigApi
from feeds_gen.models.config_key import ConfigKey as ConfigKeyModel
from feeds_gen.models.feed_config_entry import FeedConfigEntry
from feeds_gen.models.set_feed_config_value_request import SetFeedConfigValueRequest
from feeds_operations.impl.config_value_schemas import value_schema
from middleware.request_context_oauth2 import get_request_context
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import ConfigKey, ConfigValueFeed, Feed

SOURCE_OVERRIDE = "override"
SOURCE_DEFAULT = "default"
SOURCE_NONE = "none"


class FeedConfigApiImpl(BaseConfigApi):
    """Implementation of the Operations config API."""

    @with_db_session
    def list_config_keys(self, db_session: Session = None) -> List[ConfigKeyModel]:
        keys = db_session.query(ConfigKey).order_by(ConfigKey.namespace, ConfigKey.key)
        return [
            ConfigKeyModel(
                namespace=k.namespace,
                key=k.key,
                description=k.description,
                default_value=k.default_value,
                value_schema=value_schema(k.namespace, k.key),
                updated_at=k.updated_at,
            )
            for k in keys
        ]

    @with_db_session
    def get_feed_config(
        self, id: str, db_session: Session = None
    ) -> List[FeedConfigEntry]:
        feed = _get_feed(db_session, id)
        overrides = {
            (row.namespace, row.key): row
            for row in db_session.query(ConfigValueFeed).filter(
                ConfigValueFeed.feed_id == feed.id
            )
        }
        keys = db_session.query(ConfigKey).order_by(ConfigKey.namespace, ConfigKey.key)
        return [_entry(k, overrides.get((k.namespace, k.key))) for k in keys]

    @with_db_session
    def set_feed_config_value(
        self,
        id: str,
        namespace: str,
        key: str,
        set_feed_config_value_request: SetFeedConfigValueRequest,
        db_session: Session = None,
    ):
        feed = _get_feed(db_session, id)
        config_key = _get_key(db_session, namespace, key)
        value = set_feed_config_value_request.value
        _validate_value(config_key, value)

        row = _get_override(db_session, feed, namespace, key)
        _check_expected(row, set_feed_config_value_request.expected_updated_at)

        now = datetime.now(timezone.utc)
        updated_by = get_request_context().get("user_email")
        created = row is None
        if row is None:
            # Upsert rather than add: a concurrent write may have created the row since
            # it was read, and the last write wins as it would on the update path.
            db_session.execute(
                insert(ConfigValueFeed)
                .values(
                    feed_id=feed.id,
                    feed_stable_id=feed.stable_id,
                    namespace=namespace,
                    key=key,
                    value=value,
                    updated_at=now,
                    updated_by=updated_by,
                )
                .on_conflict_do_update(
                    index_elements=["feed_id", "namespace", "key"],
                    set_={"value": value, "updated_at": now, "updated_by": updated_by},
                )
            )
            row = _get_override(db_session, feed, namespace, key)
        else:
            row.value = value
            row.updated_at = now
            row.updated_by = updated_by
        db_session.flush()
        logging.info(
            "Feed %s config %s/%s set by %s", feed.stable_id, namespace, key, updated_by
        )

        entry = _entry(config_key, row)
        if created:
            return JSONResponse(
                status_code=201, content=jsonable_encoder(entry.model_dump())
            )
        return entry

    @with_db_session
    def delete_feed_config_value(
        self,
        id: str,
        namespace: str,
        key: str,
        expected_updated_at: Optional[str] = None,
        db_session: Session = None,
    ):
        feed = _get_feed(db_session, id)
        _get_key(db_session, namespace, key)
        row = _get_override(db_session, feed, namespace, key)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Feed {id} has no override of {namespace}/{key}.",
            )
        _check_expected(row, _parse_datetime(expected_updated_at))
        db_session.delete(row)
        db_session.flush()
        logging.info(
            "Feed %s config %s/%s removed by %s",
            feed.stable_id,
            namespace,
            key,
            get_request_context().get("user_email"),
        )
        return Response(status_code=204)


def _get_feed(db_session: Session, stable_id: str) -> Feed:
    feed = db_session.query(Feed).filter(Feed.stable_id == stable_id).one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail=f"Feed {stable_id} not found.")
    return feed


def _get_key(db_session: Session, namespace: str, key: str) -> ConfigKey:
    config_key = db_session.get(ConfigKey, (namespace, key))
    if config_key is None:
        raise HTTPException(
            status_code=404,
            detail=f"Config key {namespace}/{key} is not registered.",
        )
    return config_key


def _get_override(
    db_session: Session, feed: Feed, namespace: str, key: str
) -> Optional[ConfigValueFeed]:
    # Locked so a concurrent write cannot slip in between the expected_updated_at check
    # and this write.
    return (
        db_session.query(ConfigValueFeed)
        .filter(
            ConfigValueFeed.feed_id == feed.id,
            ConfigValueFeed.namespace == namespace,
            ConfigValueFeed.key == key,
        )
        .with_for_update()
        .one_or_none()
    )


def _validate_value(config_key: ConfigKey, value: Any) -> None:
    """Refuse null, then anything the key's JSON Schema rejects."""
    name = f"{config_key.namespace}/{config_key.key}"
    if value is None:
        raise HTTPException(status_code=422, detail=f"A value for {name} is required.")
    schema = value_schema(config_key.namespace, config_key.key)
    if not schema:
        return
    error = best_match(validator_for(schema)(schema).iter_errors(value))
    if error is None:
        return
    # A "not" failure names the whole sub-schema, which says nothing to the reader.
    message = (
        f"{error.instance!r} is not allowed"
        if error.validator == "not"
        else error.message
    )
    location = f" at {error.json_path}" if error.path else ""
    raise HTTPException(
        status_code=422, detail=f"Invalid value for {name}{location}: {message}"
    )


def _check_expected(
    row: Optional[ConfigValueFeed], expected_updated_at: Optional[datetime]
) -> None:
    if expected_updated_at is None:
        return
    if expected_updated_at.tzinfo is None:
        expected_updated_at = expected_updated_at.replace(tzinfo=timezone.utc)
    if row is None or row.updated_at != expected_updated_at:
        raise HTTPException(
            status_code=409,
            detail="The override has changed since it was read. Reload and try again.",
        )


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return TypeAdapter(datetime).validate_python(raw)
    except ValidationError:
        raise HTTPException(
            status_code=422, detail=f"expected_updated_at {raw!r} is not a date-time."
        )


def _entry(config_key: ConfigKey, row: Optional[ConfigValueFeed]) -> FeedConfigEntry:
    if row is not None:
        effective, source = row.value, SOURCE_OVERRIDE
    elif config_key.default_value is not None:
        effective, source = config_key.default_value, SOURCE_DEFAULT
    else:
        effective, source = None, SOURCE_NONE
    return FeedConfigEntry(
        namespace=config_key.namespace,
        key=config_key.key,
        description=config_key.description,
        value_schema=value_schema(config_key.namespace, config_key.key),
        default_value=config_key.default_value,
        override=row.value if row is not None else None,
        effective_value=effective,
        source=source,
        updated_at=row.updated_at if row is not None else None,
        updated_by=row.updated_by if row is not None else None,
    )
