import os
from typing import List, Dict

from helpers.database import start_db_session
from sqlalchemy.orm import joinedload
from database_gen.sqlacodegen_models import Feed, Location


def get_feeds_locations_map(data_type: str) -> Dict[str, List[Location]]:
    session = None
    try:
        session = start_db_session(os.getenv('FEEDS_DATABASE_URL'))
        feeds_locations_map = {}
        feeds = (session.query(Feed)
                 .filter(Feed.data_type == data_type)
                 .options(joinedload(Feed.locations))
                 .all())

        for feed in feeds:
            feeds_locations_map[feed.stable_id] = feed.locations
        return feeds_locations_map
    finally:
        if session:
            session.close()
