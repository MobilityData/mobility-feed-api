from typing import List, Optional

import matplotlib.pyplot as plt
import pycountry
from geoalchemy2.shape import to_shape

from shared.database_gen.sqlacodegen_models import Geopolygon, Osmlocationgroup

ERROR_STATUS_CODE = 299  # Custom error code for the function to avoid retries


def generate_color(
    points_match: int, max_match: int, colormap_name: str = "OrRd"
) -> str:
    """
    Generate a color based on the points_match value using a matplotlib colormap.
    """
    colormap = plt.get_cmap(colormap_name)
    # Restrict normalized_value to the upper half of the spectrum (0.5 to 1)
    normalized_value = 0.5 + 0.5 * (points_match / max_match)
    rgba = colormap(normalized_value)  # Returns RGBA
    return f"rgba({int(rgba[0] * 255)}, {int(rgba[1] * 255)}, {int(rgba[2] * 255)}, {rgba[3]})"


class GeopolygonAggregate:
    """
    A class to represent an aggregate of geopolygon object to represent a location
    (e.g. Canada, Ontario, Toronto).
    """

    def __init__(self, location_group: Osmlocationgroup, stops_count: int):
        self.group_id = location_group.group_id
        self.group_name = location_group.group_name
        self.geopolygons = [
            geopolygon for geopolygon in detach_from_session(location_group.osms)
        ]
        self.iso_3166_1_code = [
            geopolygon.iso_3166_1_code
            for geopolygon in self.geopolygons
            if geopolygon.iso_3166_1_code
        ][-1]
        self.iso_3166_2_code = " | ".join(
            [
                geopolygon.iso_3166_2_code
                for geopolygon in self.geopolygons
                if geopolygon.iso_3166_2_code
            ]
        )
        self.stop_count = stops_count

    def country(self) -> str:
        """Returns the country name of the LocationGroup."""
        country = pycountry.countries.get(alpha_2=self.iso_3166_1_code)
        return country.name if country else None

    def location_id(self) -> str:
        """Returns the location ID of the LocationGroup."""
        return "-".join(
            [self.iso_3166_1_code, self.subdivision_name(), self.municipality()]
        )

    def subdivision_name(self) -> Optional[str]:
        """Returns the name of the lowest admin level geopolygon that has an ISO 3166-2 code defined but no ISO 3166-1
        code."""
        iso_3166_2_polygons = [
            geopolygon
            for geopolygon in self.geopolygons
            if geopolygon.iso_3166_2_code and not geopolygon.iso_3166_1_code
        ]
        if iso_3166_2_polygons:
            return min(
                iso_3166_2_polygons, key=lambda geopolygon: geopolygon.admin_level
            ).name
        return None

    def municipality(self) -> str:
        """Returns the name of the highest admin level geopolygon."""
        return max(self.geopolygons, key=lambda geopolygon: geopolygon.admin_level).name

    def highest_admin_geometry(self) -> str:
        """Get the highest admin level geometry."""
        return max(
            self.geopolygons, key=lambda geopolygon: geopolygon.admin_level
        ).geometry

    def merge(self, other: "GeopolygonAggregate") -> None:
        """Merge the stop count of another LocationGroup."""
        self.stop_count += other.stop_count

    def display_name(self) -> str:
        """Return the display name of the LocationGroup."""
        display_name = self.group_name
        if self.iso_3166_1_code:
            try:
                flag = pycountry.countries.get(alpha_2=self.iso_3166_1_code).flag
                display_name = f"{flag} {display_name}"
            except AttributeError:
                pass
        return display_name

    def __str__(self) -> str:
        return f"{self.group_id} - {self.group_name}"


class GeopolygonObject:
    """A class to represent a Geopolygon object."""

    def __init__(self, geopolygon_orm: Geopolygon):
        self.name = geopolygon_orm.name
        self.osm_id = geopolygon_orm.osm_id
        self.admin_level = geopolygon_orm.admin_level
        self.iso_3166_1_code = geopolygon_orm.iso_3166_1_code
        self.iso_3166_2_code = geopolygon_orm.iso_3166_2_code
        self.geometry = to_shape(geopolygon_orm.geometry)

    def __str__(self) -> str:
        return f"{self.name} [{self.osm_id} - Admin Level: {self.admin_level}]"


def detach_from_session(geopolygons: List[Geopolygon]) -> List[GeopolygonObject]:
    """
    Detach the geopolygons from the session and return as GeopolygonObject. This helps to avoid the
    'DetachedInstanceError' when accessing the properties of the geopolygons while the session is closed.
    """
    return [GeopolygonObject(geopolygon) for geopolygon in geopolygons]


def geopolygons_as_string(geopolygons: List[Geopolygon]) -> str:
    """Convert the geopolygons to a string."""
    return ", ".join(
        [str(geopolygon) for geopolygon in detach_from_session(geopolygons)]
    )
