import logging
from collections import Counter
from typing import Tuple, List

from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Location,
    Translation,
    t_feedsearch,
    Gtfsfeed,
)
from helpers.database import refresh_materialized_view
from .geocoded_location import GeocodedLocation


def reverse_coords(
    points: List[Tuple[float, float]],
    decision_threshold: float = 0.5,
) -> List[GeocodedLocation]:
    """
    Retrieves location details for multiple latitude and longitude points.

    :param points: A list of tuples, each containing latitude and longitude.
    :param decision_threshold: Threshold to decide on a common location attribute.
    :return: A list of LocationInfo objects containing location information.
    """
    municipalities = []
    subdivisions = []
    countries = []
    country_codes = []
    point_mapping = []

    for lat, lon in points:
        (
            country_code,
            country,
            subdivision_name,
            municipality,
        ) = GeocodedLocation.reverse_coord(lat, lon)
        logging.info(
            f"Reverse geocoding result for point lat={lat}, lon={lon}: "
            f"country_code={country_code}, "
            f"country={country}, "
            f"subdivision={subdivision_name}, "
            f"municipality={municipality}"
        )
        if country_code:
            municipalities.append(municipality) if municipality else None
            subdivisions.append(subdivision_name) if subdivision_name else None
            countries.append(country)
            country_codes.append(country_code)
            point_mapping.append((lat, lon))

    if not municipalities and not subdivisions:
        unique_countries, unique_country_codes, point_mapping = get_unique_countries(
            countries, country_codes, point_mapping
        )

        logging.info(
            f"No common municipality or subdivision found. Setting location to country level with countries "
            f"{unique_countries} and country codes {unique_country_codes}"
        )

        return GeocodedLocation.from_country_level(
            unique_country_codes, unique_countries, point_mapping
        )

    most_common_municipality, municipality_count = (
        Counter(municipalities).most_common(1)[0] if municipalities else (None, 0)
    )
    most_common_subdivision, subdivision_count = (
        Counter(subdivisions).most_common(1)[0] if subdivisions else (None, 0)
    )

    logging.info(
        f"Most common municipality: {most_common_municipality} with count {municipality_count}"
    )
    logging.info(
        f"Most common subdivision: {most_common_subdivision} with count {subdivision_count}"
    )

    if municipality_count / len(points) >= decision_threshold:
        related_country = countries[municipalities.index(most_common_municipality)]
        related_country_code = country_codes[
            municipalities.index(most_common_municipality)
        ]
        related_subdivision = subdivisions[
            municipalities.index(most_common_municipality)
        ]
        logging.info(
            f"Common municipality found. Setting location to municipality level with country {related_country}, "
            f"country code {related_country_code}, subdivision {most_common_subdivision}, and municipality "
            f"{most_common_municipality}"
        )
        point = point_mapping[municipalities.index(most_common_municipality)]
        return GeocodedLocation.from_common_attributes(
            most_common_municipality,
            "municipality",
            related_country,
            related_country_code,
            related_subdivision,
            point,
        )
    elif subdivision_count / len(points) >= decision_threshold:
        related_country = countries[subdivisions.index(most_common_subdivision)]
        related_country_code = country_codes[
            subdivisions.index(most_common_subdivision)
        ]
        logging.info(
            f"No common municipality found. Setting location to subdivision level with country {related_country} "
            f",country code {related_country_code}, and subdivision {most_common_subdivision}"
        )
        point = point_mapping[subdivisions.index(most_common_subdivision)]
        return GeocodedLocation.from_common_attributes(
            most_common_subdivision,
            "subdivision",
            related_country,
            related_country_code,
            most_common_subdivision,
            point,
        )

    unique_countries, unique_country_codes, point_mapping = get_unique_countries(
        countries, country_codes, point_mapping
    )
    logging.info(
        f"No common municipality or subdivision found. Setting location to country level with countries "
        f"{unique_countries} and country codes {unique_country_codes}"
    )
    return GeocodedLocation.from_country_level(
        unique_country_codes, unique_countries, point_mapping
    )


def get_unique_countries(
    countries: List[str], country_codes: List[str], points: List[Tuple[float, float]]
) -> Tuple[List[str], List[str], List[Tuple[float, float]]]:
    """
    Get unique countries, country codes, and their corresponding points from a list.
    :param countries: List of countries.
    :param country_codes: List of country codes.
    :param points: List of (latitude, longitude) tuples.
    :return: Unique countries, country codes, and corresponding points.
    """
    # Initialize a dictionary to store unique country codes and their corresponding countries and points
    unique_country_dict = {}
    point_mapping = []

    # Iterate over the country codes, countries, and points
    for code, country, point in zip(country_codes, countries, points):
        if code not in unique_country_dict:
            unique_country_dict[code] = country
            point_mapping.append(
                point
            )  # Append the point associated with the unique country code

    # Extract the keys (country codes), values (countries), and points from the dictionary in order
    unique_country_codes = list(unique_country_dict.keys())
    unique_countries = list(unique_country_dict.values())

    return unique_countries, unique_country_codes, point_mapping


def update_location(
    location_info: List[GeocodedLocation], dataset_id: str, session: Session
):
    """
    Update the location details of a dataset in the database.

    :param location_info: A list of GeocodedLocation objects containing location details.
    :param dataset_id: The ID of the dataset.
    :param session: The database session.
    """
    dataset: Gtfsdataset | None = (
        session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if dataset is None:
        raise Exception(f"Dataset {dataset_id} does not exist in the database.")

    locations = []
    for location in location_info:
        location_entity = get_or_create_location(location, session)
        locations.append(location_entity)

        for translation in location.translations:
            if translation.language != "en":
                continue
            update_translation(location, translation, session)

    if len(locations) == 0:
        raise Exception("No locations found for the dataset.")
    logging.info(f"Updating dataset with stable ID {dataset.stable_id}")
    dataset.locations.clear()
    dataset.locations = locations

    # Update the location of the related feeds as well
    logging.info(f"Updating feed with stable ID {dataset.feed.stable_id}")
    dataset.feed.locations.clear()
    dataset.feed.locations = locations

    gtfs_feed: Gtfsfeed | None = (
        session.query(Gtfsfeed)
        .filter(Gtfsfeed.stable_id == dataset.feed.stable_id)
        .one_or_none()
    )
    if gtfs_feed is None:
        logging.error(f"Feed {dataset.feed.stable_id} not found a GTFS feed.")
        raise Exception(f"Feed {dataset.feed.stable_id} not found a GTFS feed.")

    for gtfs_rt_feed in gtfs_feed.gtfs_rt_feeds:
        logging.info(f"Updating GTFS-RT feed with stable ID {gtfs_rt_feed.stable_id}")
        gtfs_rt_feed.locations.clear()
        gtfs_rt_feed.locations = locations
        session.add(gtfs_rt_feed)

    refresh_materialized_view(session, t_feedsearch.name)
    session.add(dataset)
    session.commit()


def get_or_create_location(location: GeocodedLocation, session: Session) -> Location:
    """
    Get an existing location or create a new one.

    :param location: A GeocodedLocation object.
    :param session: The database session.
    :return: The Location entity.
    """
    location_id = location.get_location_id()
    location_entity = (
        session.query(Location).filter(Location.id == location_id).one_or_none()
    )
    if location_entity is not None:
        logging.info(f"Location already exists: {location_id}")
    else:
        logging.info(f"Creating new location: {location_id}")
        location_entity = Location(id=location_id)
        session.add(location_entity)

    # Ensure the elements are up-to-date
    location_entity.country = location.country
    location_entity.country_code = location.country_code
    location_entity.municipality = location.municipality
    location_entity.subdivision_name = location.subdivision_name
    session.add(location_entity)

    return location_entity


def update_translation(
    location: GeocodedLocation, translation: GeocodedLocation, session: Session
):
    """
    Update or create a translation for a location.

    :param location: The original location entity.
    :param translation: The translated location information.
    :param session: The database session.
    """
    translated_country = translation.country
    translated_subdivision = translation.subdivision_name
    translated_municipality = translation.municipality

    if translated_country is not None:
        update_translation_record(
            session,
            location.country,
            translated_country,
            translation.language,
            "country",
        )
    if translated_subdivision is not None:
        update_translation_record(
            session,
            location.subdivision_name,
            translated_subdivision,
            translation.language,
            "subdivision_name",
        )
    if translated_municipality is not None:
        update_translation_record(
            session,
            location.municipality,
            translated_municipality,
            translation.language,
            "municipality",
        )


def update_translation_record(
    session: Session, key: str, value: str, language_code: str, translation_type: str
):
    """
    Update or create a translation record in the database.

    :param session: The database session.
    :param key: The key value for the translation (e.g., original location name).
    :param value: The translated value.
    :param language_code: The language code of the translation.
    :param translation_type: The type of translation (e.g., 'country', 'subdivision_name', 'municipality').
    """
    if not key or not value or value == key:
        logging.info(f"Skipping translation for key {key} and value {value}")
        return
    value = value.strip()
    translation = (
        session.query(Translation)
        .filter(Translation.key == key)
        .filter(Translation.language_code == language_code)
        .filter(Translation.type == translation_type)
        .one_or_none()
    )
    if translation is None:
        translation = Translation(
            key=key,
            value=value,
            language_code=language_code,
            type=translation_type,
        )
        session.add(translation)
