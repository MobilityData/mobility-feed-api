import logging
from collections import Counter
from typing import Tuple, Optional, List

import requests
from sqlalchemy.orm import Session

from database_gen.sqlacodegen_models import Gtfsdataset, Location

NOMINATIM_ENDPOINT = (
    "https://nominatim.openstreetmap.org/reverse?format=json&zoom=13&addressdetails=1"
)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36"
}
EN_LANG_HEADER = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en",
}

logging.basicConfig(level=logging.INFO)


class LocationInfo:
    def __init__(
        self,
        country_code: str,
        country: str,
        municipality: Optional[str] = None,
        subdivision_name: Optional[str] = None,
        language: Optional[str] = "en",
        translations: Optional[List["LocationInfo"]] = None,
    ):
        self.country_code = country_code
        self.country = country
        self.municipality = municipality
        self.subdivision_name = subdivision_name
        self.language = language
        self.translations = translations if translations is not None else []

    def get_location_entity(self):
        return Location(
            id=self.get_location_id(),
            country_code=self.country_code,
            country=self.country,
            municipality=self.municipality,
            subdivision_name=self.subdivision_name,
        )

    def get_location_id(self):
        location_id = (
            f"{self.country_code or ''}-"
            f"{self.subdivision_name or ''}-"
            f"{self.municipality or ''}"
        ).replace(" ", "_")
        return location_id


def reverse_coord(
    lat: float, lon: float, include_lang_header: bool = False
) -> (Tuple)[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Retrieves location details for a given latitude and longitude using the Nominatim API.

    :param lat: Latitude of the location.
    :param lon: Longitude of the location.
    :param include_lang_header: If True, include English language header in the request.
    :return: A tuple containing country code, country, subdivision code, subdivision name, and municipality.
    """
    request_url = f"{NOMINATIM_ENDPOINT}&lat={lat}&lon={lon}"
    headers = EN_LANG_HEADER if include_lang_header else DEFAULT_HEADERS

    try:
        response = requests.get(request_url, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        address = response_json.get("address", {})

        country_code = (
            address.get("country_code").upper() if address.get("country_code") else None
        )
        country = address.get("country")
        municipality = address.get("city", address.get("town"))
        subdivision_name = address.get("state", address.get("province"))

    except requests.exceptions.RequestException as e:
        logging.error(f"Error occurred while requesting location data: {e}")
        country_code = country = subdivision_name = municipality = None

    return country_code, country, subdivision_name, municipality


def reverse_coords(
    points: List[Tuple[float, float]],
    include_lang_header: bool = False,
    decision_threshold: float = 0.5,
) -> List[LocationInfo]:
    """
    Retrieves location details for multiple latitude and longitude points.

    :param points: A list of tuples, each containing latitude and longitude.
    :param include_lang_header: If True, include English language header in the request.
    :param decision_threshold: Threshold to decide on a common location attribute.
    :return: A LocationInfo object containing lists of country codes and countries,
             and the most common subdivision name and municipality if above the threshold.
    """
    results = []
    municipalities = []
    subdivisions = []
    countries = []
    country_codes = []

    for lat, lon in points:
        (
            country_code,
            country,
            subdivision_name,
            municipality,
        ) = reverse_coord(lat, lon, include_lang_header)
        logging.info(
            f"Reverse geocoding result for point lat={lat}, lon={lon}: "
            f"country_code={country_code}, "
            f"country={country}, "
            f"subdivision={subdivision_name}, "
            f"municipality={municipality}"
        )
        if country_code is not None:
            municipalities.append(municipality) if municipality else None
            subdivisions.append(subdivision_name) if subdivision_name else None
            countries.append(country)
            country_codes.append(country_code)
            results.append(
                (
                    country_code,
                    country,
                    subdivision_name,
                    municipality,
                )
            )

    # Determine the most common attributes
    most_common_municipality = None
    most_common_subdivision = None
    municipality_count = subdivision_count = 0

    if municipalities:
        most_common_municipality, municipality_count = Counter(
            municipalities
        ).most_common(1)[0]

    if subdivisions:
        most_common_subdivision, subdivision_count = Counter(subdivisions).most_common(
            1
        )[0]
    logging.info(
        f"Most common municipality: {most_common_municipality} with count {municipality_count}"
    )
    logging.info(
        f"Most common subdivision: {most_common_subdivision} with count {subdivision_count}"
    )

    # Apply decision threshold to determine final values
    if municipality_count / len(results) < decision_threshold:
        if subdivision_count / len(results) < decision_threshold:
            # No common municipality or subdivision
            unique_countries = list(set(countries))
            unique_country_codes = list(set(country_codes))
            logging.info(
                f"No common municipality or subdivision found. Setting location to country level with countries "
                f"{unique_countries} and country codes {unique_country_codes}"
            )
            locations = [
                LocationInfo(
                    country_code=unique_country_codes[i],
                    country=unique_countries[i],
                    municipality=None,
                    subdivision_name=None,
                )
                for i in range(len(unique_country_codes))
            ]
        else:
            # No common municipality but common subdivision
            related_country = countries[subdivisions.index(most_common_subdivision)]
            related_country_code = country_codes[
                subdivisions.index(most_common_subdivision)
            ]
            logging.info(
                f"No common municipality found. Setting location to subdivision level with country {related_country} "
                f",country code {related_country_code} and subdivision {most_common_subdivision}"
            )
            locations = [
                LocationInfo(
                    country_code=related_country_code,
                    country=related_country,
                    municipality=None,
                    subdivision_name=most_common_subdivision,
                )
            ]
    else:
        # Common municipality
        most_common_subdivision = subdivisions[
            municipalities.index(most_common_municipality)
        ]
        related_country = countries[municipalities.index(most_common_municipality)]
        related_country_code = country_codes[
            municipalities.index(most_common_municipality)
        ]
        logging.info(
            f"Common municipality found. Setting location to municipality level with country {related_country}, "
            f"country code {related_country_code}, subdivision {most_common_subdivision} and municipality "
            f"{most_common_municipality}"
        )
        locations = [
            LocationInfo(
                country_code=related_country_code,
                country=related_country,
                municipality=most_common_municipality,
                subdivision_name=most_common_subdivision,
            )
        ]
    return locations


def update_location(
    location_info: List[LocationInfo], dataset_id: str, session: Session
):
    """
    Update the location details of a dataset in the database.

    :param location_info: A LocationInfo object containing location details.
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
        logging.info(
            f"Extracted location with country code {location.country_code}, country {location.country}, "
            f"subdivision {location.subdivision_name}, and municipality {location.municipality}"
        )
        # Check if location already exists
        location_id = location.get_location_id()
        location_entity = (
            session.query(Location).filter(Location.id == location_id).one_or_none()
        )
        if location_entity is not None:
            logging.info(f"[{dataset_id}] Location already exists: {location_id}")
        else:
            logging.info(f"[{dataset_id}] Creating new location: {location_id}")
            location_entity = location.get_location_entity()
        location_entity.country = (
            location.country
        )  # Update the country name as it's a later addition
        locations.append(location)
    if len(locations) == 0:
        raise Exception("No locations found for the dataset.")
    dataset.locations.clear()
    dataset.locations = locations

    # Update the location of the related feed as well
    dataset.feed.locations.clear()
    dataset.feed.locations = locations

    session.add(dataset)
    session.commit()
