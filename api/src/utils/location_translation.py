import pycountry
from typing import TYPE_CHECKING
from sqlalchemy.engine.result import Row

from database_gen.sqlacodegen_models import Location as LocationOrm, t_location_with_translations_en
from database_gen.sqlacodegen_models import Feed as FeedOrm

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class LocationTranslation:
    def __init__(
        self,
        location_id,
        country_code,
        country,
        subdivision_name,
        municipality,
        country_translation,
        subdivision_name_translation,
        municipality_translation,
    ):
        self.location_id = location_id
        self.country_code = country_code
        self.country = country
        self.subdivision_name = subdivision_name
        self.municipality = municipality
        self.country_translation = country_translation
        self.subdivision_name_translation = subdivision_name_translation
        self.municipality_translation = municipality_translation

    def __repr__(self):
        return (
            f"LocationTranslation(location_id={self.location_id}, country_code={self.country_code}, "
            f"country={self.country}, subdivision_name={self.subdivision_name}, municipality={self.municipality}, "
            f"country_translation={self.country_translation}, subdivision_name_translation="
            f"{self.subdivision_name_translation}, municipality_translation={self.municipality_translation})"
        )


def get_feeds_location_ids(feeds: list[FeedOrm]) -> list[str]:
    """
    Get the location ids of a list of feeds.
    :param feeds: The list of feeds
    :return: The list of location ids
    """
    location_ids = []
    for feed in feeds:
        location_ids.extend([location.id for location in feed.locations])
    return location_ids


def get_feeds_location_translations(feeds: list[FeedOrm], db_session: "Session") -> dict[str, LocationTranslation]:
    """
    Get the location translations of a list of feeds.
    :param feeds: The list of feeds
    :return: The location translations
    """
    location_ids = get_feeds_location_ids(feeds)
    location_translations = (
        db_session.query(t_location_with_translations_en)
        .filter(t_location_with_translations_en.c.location_id.in_(location_ids))
        .all()
    )
    return {
        location_translation[0]: create_location_translation_object(location_translation)
        for location_translation in location_translations
    }


def create_location_translation_object(row: Row):
    """Create a location translation object from a row."""
    if len(row) == 9:
        # The first element is the feed
        row = row[1:]
    return LocationTranslation(
        location_id=row[0],
        country_code=row[1],
        country=row[2],
        subdivision_name=row[3],
        municipality=row[4],
        country_translation=row[5],
        subdivision_name_translation=row[6],
        municipality_translation=row[7],
    )


def set_country_name(location: LocationOrm, country_name: str) -> LocationOrm:
    """
    Set the country name of a location
    :param location: The location object
    :param country_name: The english translation of the country name
    :return: Modified location object
    """
    try:
        if country_name is not None:
            location.country = country_name
        else:
            location.country = pycountry.countries.get(alpha_2=location.country_code).name
    except AttributeError:
        pass
    return location


def translate_feed_locations(feed: FeedOrm, location_translations: dict[str, LocationTranslation]):
    """
    Translate the locations of a feed.
    :param feed: The feed object
    :param location_translations: The location translations
    """
    for location in feed.locations:
        location_translation = location_translations.get(location.id)
        location = set_country_name(
            location, location_translation.country_translation if location_translation else None
        )
        if location_translation:
            location.country_code = location_translation.country_code
            location.subdivision_name = (
                location_translation.subdivision_name_translation
                if location_translation.subdivision_name_translation
                else location.subdivision_name
            )
            location.municipality = (
                location_translation.municipality_translation
                if location_translation.municipality_translation
                else location.municipality
            )
