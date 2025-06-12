from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import joinedload, Session

from shared.database_gen.sqlacodegen_models import Feed
from shared.database.database import with_db_session


@dataclass
class Location:
    """
    Location data class.
    """

    country: str
    country_code: str
    subdivision_name: str
    municipality: str


@with_db_session
def get_feed_location(stable_id: str, db_session: Session) -> List[Location]:
    """
    Get the location of a feed.
    @param stable_id: The stable ID of the feed.
    @param db_session: The database session.
    @return: A list of locations.
    """
    feeds = (
        db_session.query(Feed)
        .filter(Feed.stable_id == stable_id)
        .options(joinedload(Feed.locations))
        .all()
    )
    return (
        [
            Location(
                country=location.country,
                country_code=location.country_code,
                subdivision_name=location.subdivision_name,
                municipality=location.municipality,
            )
            for location in feeds[0].locations
        ]
        if feeds is not None and len(feeds) > 0
        else []
    )
