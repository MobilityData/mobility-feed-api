from typing import Dict

from database_gen.sqlacodegen_models import Feed


def translate_feed_locations(feed: Feed, location_translations: Dict):
    """
    Translate the locations of a feed.
    :param feed: The feed object
    :param location_translations: The location translations
    """
    for location in feed.locations:
        location_translation = location_translations.get(location.id)

        if location_translation:
            location.subdivision_name = (
                location_translation["subdivision_name_translation"]
                if location_translation["subdivision_name_translation"]
                else location.subdivision_name
            )
            location.municipality = (
                location_translation["municipality_translation"]
                if location_translation["municipality_translation"]
                else location.municipality
            )
            location.country = (
                location_translation["country_translation"]
                if location_translation["country_translation"]
                else location.country
            )
