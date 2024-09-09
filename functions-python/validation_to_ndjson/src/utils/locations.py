import os
from typing import List

from sqlalchemy.orm import joinedload

from database_gen.sqlacodegen_models import Feed, Location
from helpers.database import start_db_session


def get_feed_location(data_type: str, stable_id: str) -> List[Location]:
    """
    Get the location of a feed.
    @param data_type: The data type of the feed.
    @param stable_id: The stable ID of the feed.
    @return: A list of locations.
    """
    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        feeds = (
            session.query(Feed)
            .filter(Feed.data_type == data_type)
            .filter(Feed.stable_id == stable_id)
            .options(joinedload(Feed.locations))
            .all()
        )
        return feeds[0].locations if feeds is not None and len(feeds) > 0 else []
    finally:
        if session:
            session.close()
