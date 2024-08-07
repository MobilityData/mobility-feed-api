def create_location_translation_object(row):
    """Create a location translation object from a row."""
    return LocationTranslation(
        location_id=row[1],
        country_code=row[2],
        country=row[3],
        subdivision_name=row[4],
        municipality=row[5],
        country_translation=row[6],
        subdivision_name_translation=row[7],
        municipality_translation=row[8],
    )


def translate_feed_locations(feed, location_translations):
    """Translate the locations of a feed."""
    for location in feed.locations:
        location_translation = location_translations.get(location.id)
        if location_translation:
            location.country_code = location_translation.country_code
            location.country = (
                location_translation.country_translation
                if location_translation.country_translation
                else location.country
            )
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
