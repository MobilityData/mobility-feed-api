import requests
import logging
from typing import Tuple, Optional, List, NamedTuple
from collections import Counter
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


class LocationInfo(NamedTuple):
    country_codes: List[str]
    countries: List[str]
    most_common_subdivision_name: Optional[str]
    most_common_municipality: Optional[str]


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
) -> LocationInfo:
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

    # Apply decision threshold to determine final values
    if municipality_count / len(points) < decision_threshold:
        most_common_municipality = None

    if subdivision_count / len(points) < decision_threshold:
        most_common_subdivision = None

    return LocationInfo(
        country_codes=country_codes,
        countries=countries,
        most_common_subdivision_name=most_common_subdivision,
        most_common_municipality=most_common_municipality,
    )


def update_location(location_info: LocationInfo, dataset_id: str, session: Session):
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
    for i in range(len(location_info.country_codes)):
        location = Location(
            country_code=location_info.country_codes[i],
            country=location_info.countries[i],
            subdivision_name=location_info.most_common_subdivision_name,
            municipality=location_info.most_common_municipality,
        )
        locations.append(location)
    if len(locations) == 0:
        raise Exception("No locations found for the dataset.")
    dataset.locations = locations

    # Update the location of the related feed as well
    dataset.feed.locations = locations

    session.add(dataset)
    session.commit()
