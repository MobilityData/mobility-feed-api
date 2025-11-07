import logging
import uuid
from datetime import datetime
from typing import Tuple, Optional
from sqlalchemy.orm import Session
import requests

from shared.common.locations_utils import create_or_get_location
from shared.helpers.feed_sync.models import TransitFeedSyncPayload as FeedPayload
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
    Externalid,
    Entitytype,
    Feed,
)


def check_url_status(url: str) -> bool:
    """Check if a URL is reachable."""
    try:
        response = requests.head(url, timeout=10)
        result = response.status_code < 400 or response.status_code == 403
        if not result:
            logging.error(
                "Url [%s] replied with status code: [%s]", url, response.status_code
            )
        return result
    except requests.RequestException:
        logging.warning("Failed to reach URL: %s", url)
        return False


def get_feed_model(spec: str) -> Tuple[type, str]:
    """Map feed specification to model and type."""
    spec_lower = spec.lower().replace("-", "_")
    if spec_lower == "gtfs":
        return Gtfsfeed, spec_lower
    if spec_lower == "gtfs_rt":
        return Gtfsrealtimefeed, spec_lower
    raise ValueError(f"Invalid feed specification: {spec}")


def get_tlnd_authentication_type(auth_type: Optional[str]) -> str:
    """Map TransitLand authentication type to database format."""
    if auth_type in (None, ""):
        return "0"
    if auth_type == "query_param":
        return "1"
    if auth_type == "header":
        return "2"
    raise ValueError(f"Invalid authentication type: {auth_type}")


def create_new_feed(session: Session, stable_id: str, payload: FeedPayload) -> Feed:
    """Create a new feed and its dependencies."""
    feed_type, data_type = get_feed_model(payload.spec)

    # Create new feed
    new_feed = feed_type(
        id=str(uuid.uuid4()),
        stable_id=stable_id,
        producer_url=payload.feed_url,
        data_type=data_type,
        authentication_type=get_tlnd_authentication_type(payload.type),
        authentication_info_url=payload.auth_info_url,
        api_key_parameter_name=payload.auth_param_name,
        status="active",
        provider=payload.operator_name,
        operational_status="wip",  # Default to of wip
        created_at=datetime.now(),
    )

    # Add external ID relationship
    external_id = Externalid(
        feed_id=new_feed.id,
        associated_id=payload.external_id,
        source=payload.source,
    )
    new_feed.externalids = [external_id]

    # Add entity types if applicable
    if feed_type == Gtfsrealtimefeed and payload.entity_types:
        entity_type_names = payload.entity_types.split(",")
        for entity_name in entity_type_names:
            entity = session.query(Entitytype).filter_by(name=entity_name).first()
            if not entity:
                entity = Entitytype(name=entity_name)
                session.add(entity)
            new_feed.entitytypes.append(entity)

    # Add location if provided
    location = create_or_get_location(
        session,
        payload.country,
        payload.state_province,
        payload.city_name,
    )
    if location:
        new_feed.locations = [location]
        logging.debug("Added location for feed %s", new_feed.id)

    # Persist the new feed
    session.add(new_feed)
    session.flush()
    logging.info("Created new feed with ID: %s", new_feed.id)
    return new_feed
