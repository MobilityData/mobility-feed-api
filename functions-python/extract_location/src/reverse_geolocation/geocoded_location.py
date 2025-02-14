import logging
import os
from typing import Tuple, Optional, List

import requests

NOMINATIM_ENDPOINT = (
    "https://nominatim.openstreetmap.org/reverse?format=json&zoom=13&addressdetails=1"
)
DEFAULT_HEADERS = {
    "User-Agent": os.getenv("USER_AGENT", "mobility-database"),
}


class GeocodedLocation:
    def __init__(
        self,
        country_code: str,
        country: str,
        municipality: Optional[str] = None,
        subdivision_name: Optional[str] = None,
        language: Optional[str] = "local",
        translations: Optional[List["GeocodedLocation"]] = None,
        stop_coords: Optional[Tuple[float, float]] = None,
    ):
        self.country_code = country_code
        self.country = country
        self.municipality = municipality
        self.subdivision_name = subdivision_name
        self.language = language
        self.translations = translations if translations is not None else []
        self.stop_coord = stop_coords if stop_coords is not None else []
        if language == "local":
            self.generate_translation("en")  # Generate English translation by default

    def get_location_id(self) -> str:
        location_id = (
            f"{self.country_code or ''}-"
            f"{self.subdivision_name or ''}-"
            f"{self.municipality or ''}"
        ).replace(" ", "_")
        return location_id

    def generate_translation(self, language: str = "en"):
        """
        Generate a translation for the location in the specified language.
        :param language: Language code for the translation.
        """
        (
            country_code,
            country,
            subdivision_name,
            municipality,
        ) = GeocodedLocation.reverse_coord(
            self.stop_coord[0], self.stop_coord[1], language
        )
        if (
            self.country == country
            and (
                self.subdivision_name == subdivision_name
                or self.subdivision_name is None
            )
            and (self.municipality == municipality or self.municipality is None)
        ):
            return  # No need to add the same location
        logging.info(
            f"The location {self.country}, {self.subdivision_name}, {self.municipality} is "
            f"translated to {country}, {subdivision_name}, {municipality} in {language}"
        )
        self.translations.append(
            GeocodedLocation(
                country_code=country_code,
                country=country,
                municipality=municipality if self.municipality else None,
                subdivision_name=subdivision_name if self.subdivision_name else None,
                language=language,
                stop_coords=self.stop_coord,
            )
        )

    @classmethod
    def from_common_attributes(
        cls,
        common_attr,
        attr_type,
        related_country,
        related_country_code,
        related_subdivision,
        points,
    ):
        if attr_type == "country":
            return [
                cls(
                    country_code=related_country_code,
                    country=related_country,
                    stop_coords=points,
                )
            ]
        elif attr_type == "subdivision":
            return [
                cls(
                    country_code=related_country_code,
                    country=related_country,
                    subdivision_name=common_attr,
                    stop_coords=points,
                )
            ]
        elif attr_type == "municipality":
            return [
                cls(
                    country_code=related_country_code,
                    country=related_country,
                    municipality=common_attr,
                    subdivision_name=related_subdivision,
                    stop_coords=points,
                )
            ]

    @classmethod
    def from_country_level(cls, unique_country_codes, unique_countries, points):
        return [
            cls(
                country_code=unique_country_codes[i],
                country=unique_countries[i],
                stop_coords=points[i],
            )
            for i in range(len(unique_country_codes))
        ]

    @staticmethod
    def reverse_coord(
        lat: float, lon: float, language: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Retrieves location details for a given latitude and longitude using the Nominatim API.

        :param lat: Latitude of the location.
        :param lon: Longitude of the location.
        :param language: (optional) Language code for the request.
        :return: A tuple containing country code, country, subdivision name, and municipality.
        """
        request_url = f"{NOMINATIM_ENDPOINT}&lat={lat}&lon={lon}"
        headers = DEFAULT_HEADERS.copy()
        if language:
            headers["Accept-Language"] = language

        try:
            response = requests.get(request_url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            address = response_json.get("address", {})

            country_code = address.get("country_code", "").upper()
            country = address.get("country", "")
            municipality = address.get("city", address.get("town", ""))
            subdivision_name = address.get("state", address.get("province", ""))

        except requests.exceptions.RequestException as e:
            logging.error(f"Error occurred while requesting location data: {e}")
            country_code = country = subdivision_name = municipality = None

        return country_code, country, subdivision_name, municipality
