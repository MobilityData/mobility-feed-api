from typing import List, Optional

import matplotlib.pyplot as plt
import pycountry
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Geopolygon, Osmlocationgroup, Feedlocationgrouppoint, \
    Feedosmlocationgroup, Location

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

def extract_location_aggregate(
    feed_id: str, stop_point: WKTElement, logger, db_session: Session
) -> Optional[GeopolygonAggregate]:
    """
    Extract the location group for a given stop point.
    """
    geopolygons = (
        db_session.query(Geopolygon)
        .filter(Geopolygon.geometry.ST_Contains(stop_point))
        .all()
    )

    if len(geopolygons) <= 1:
        logger.warning(
            "Invalid number of geopolygons for point: %s -> %s", stop_point, geopolygons
        )
        return None
    return extract_location_aggregate_geopolygons(feed_id=feed_id, stop_point=stop_point,
                                                  geopolygons=geopolygons, logger=logger, db_session=db_session)

def extract_location_aggregate_geopolygons(
    feed_id: str, stop_point: WKTElement, geopolygons, logger, db_session: Session
) -> Optional[GeopolygonAggregate]:
    admin_levels = {g.admin_level for g in geopolygons}
    if len(admin_levels) != len(geopolygons):
        logger.warning(
            "Duplicate admin levels for point: %s -> %s",
            stop_point,
            geopolygons_as_string(geopolygons),
        )
        return None

    valid_iso_3166_1 = any(g.iso_3166_1_code for g in geopolygons)
    valid_iso_3166_2 = any(g.iso_3166_2_code for g in geopolygons)
    if not valid_iso_3166_1 or not valid_iso_3166_2:
        logger.warning(
            "Invalid ISO codes for point: %s -> %s",
            stop_point,
            geopolygons_as_string(geopolygons),
        )
        return

    # Sort the polygons by admin level so that lower levels come first
    geopolygons.sort(key=lambda x: x.admin_level)

    group_id = ".".join([str(g.osm_id) for g in geopolygons])
    group = (
        db_session.query(Osmlocationgroup)
        .filter(Osmlocationgroup.group_id == group_id)
        .one_or_none()
    )
    if not group:
        group = Osmlocationgroup(
            group_id=group_id,
            group_name=", ".join([g.name for g in geopolygons]),
            osms=geopolygons,
        )
        db_session.add(group)
    # TODO: Review the connection with stops
        # db_session.flush()
    # stop = (
    #     db_session.query(Feedlocationgrouppoint)
    #     .filter(
    #         Feedlocationgrouppoint.feed_id == feed_id,
    #         Feedlocationgrouppoint.geometry == stop_point,
    #     )
    #     .one_or_none()
    # )
    # if not stop:
    #     stop = Feedlocationgrouppoint(
    #         feed_id=feed_id,
    #         geometry=stop_point,
    #     )
    #     stop.group = group
    #     db_session.add(stop)
    # else:
    #     if stop.group_id != group.group_id:
    #         logger.info(
    #             "Updating stop point %s from group %s to %s",
    #             stop_point,
    #             stop.group_id,
    #             group.group_id,
    #         )
    #         stop.group = group
    # db_session.flush()  # Ensure the group and stop entity is in sync with the DB
    logger.debug(
        "Point %s matched to %s", stop_point, ", ".join([g.name for g in geopolygons])
    )
    return GeopolygonAggregate(group, 1)


def get_or_create_feed_osm_location_group(
    feed_id: str, location_aggregate: GeopolygonAggregate, db_session: Session
) -> Feedosmlocationgroup:
    """Get or create the feed osm location group."""
    feed_osm_location = (
        db_session.query(Feedosmlocationgroup)
        .filter(
            Feedosmlocationgroup.feed_id == feed_id,
            Feedosmlocationgroup.group_id == location_aggregate.group_id,
        )
        .one_or_none()
    )
    if not feed_osm_location:
        feed_osm_location = Feedosmlocationgroup(
            feed_id=feed_id,
            group_id=location_aggregate.group_id,
        )
    feed_osm_location.stops_count = location_aggregate.stop_count
    return feed_osm_location

def get_or_create_location(
    location_group: GeopolygonAggregate, logger, db_session: Session
) -> Optional[Location]:
    """Get or create the Location entity."""
    try:
        logger.debug("Location ID : %s", location_group.location_id())
        location = (
            db_session.query(Location)
            .filter(Location.id == location_group.location_id())
            .one_or_none()
        )
        if not location:
            location = Location(
                id=location_group.location_id(),
                country_code=location_group.iso_3166_1_code,
                country=location_group.country(),
                subdivision_name=location_group.subdivision_name(),
                municipality=location_group.municipality(),
            )
        return location
    except Exception as e:
        logger.error("Error creating location: %s", e)
        return None