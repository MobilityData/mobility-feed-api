import json
import logging
import os

import functions_framework
import pycountry
from geoalchemy2 import WKTElement
from google.cloud import bigquery
from sqlalchemy import func, literal, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlalchemy.schema import DDL

from shared.database_gen.sqlacodegen_models import Geopolygon
from shared.database.database import with_db_session
from shared.helpers.logger import init_logger
from enum import Enum
from shared.database_gen.sqlacodegen_models import Geopolygonhierarchy

# Initialize logging
init_logger()
client = None  # Global BigQuery client


class LocationType(Enum):
    COUNTRY = "country"
    SUBDIVISION = "subdivision"
    LOCALITY = "locality"  # City/Municipality/Town


def parse_request_parameters(request):
    """Parse and validate request parameters, including the country code."""
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    if not request_json or "country_code" not in request_json:
        logging.error("Request missing required country_code parameter.")
        raise ValueError("Invalid request parameters: country_code is required.")

    country_code = request_json["country_code"]
    if pycountry.countries.get(alpha_2=country_code) is None:
        logging.error("Invalid country code detected: %s", country_code)
        raise ValueError(f"Invalid country code: {country_code}")

    admin_levels = request_json.get("admin_levels", None)
    try:
        if admin_levels:
            admin_levels = [int(level) for level in admin_levels.split(",")]
        if admin_levels and not all(2 <= level <= 8 for level in admin_levels):
            raise ValueError("Invalid admin levels.")
    except ValueError:
        logging.error("Invalid admin levels detected: %s", admin_levels)
        raise ValueError(f"Invalid admin levels: {admin_levels}")
    return country_code, admin_levels


def fetch_subdivision_admin_levels(country_code):
    """Fetch distinct subdivision admin levels for the given country code."""
    logging.info("Fetching subdivision administrative levels.")
    query = f"""
        SELECT DISTINCT
          CAST((SELECT value FROM UNNEST(all_tags) WHERE key = 'admin_level') AS INT) AS admin_level
        FROM
          `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons`
        WHERE
          ('boundary', 'administrative') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))
          AND EXISTS (
            SELECT 1
            FROM UNNEST(all_tags) AS tag
            WHERE tag.key = 'ISO3166-2' AND tag.value LIKE '{country_code}%'
          )
        ORDER BY admin_level;
    """
    query_job = client.query(query)
    results = query_job.result()
    return [row.admin_level for row in results if row.admin_level is not None]


def fetch_country_admin_levels(country_code):
    """Fetch distinct country admin levels for the given country code."""
    logging.info("Fetching country administrative levels.")
    query = f"""
        SELECT DISTINCT
          CAST((SELECT value FROM UNNEST(all_tags) WHERE key = 'admin_level') AS INT) AS admin_level
        FROM
          `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons`
        WHERE
          ('boundary', 'administrative') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))
          AND EXISTS (
            SELECT 1
            FROM UNNEST(all_tags) AS tag
            WHERE tag.key = 'ISO3166-1' AND tag.value LIKE '{country_code}'
          )
        ORDER BY admin_level;
    """
    query_job = client.query(query)
    results = query_job.result()
    return [row.admin_level for row in results if row.admin_level is not None]


def generate_query(admin_level, country_code, location_type, country_name=None):
    """
    Generate the query for a specific admin level and location type.

    - For "country", we enforce ISO3166-1.
    - For "subdivision", we require an ISO3166-2 tag.
    - For "locality", no extra ISO condition is applied.
    """
    logging.info(
        "Generating query for admin level: %s, country code: %s",
        admin_level,
        country_code,
    )
    country_name_filter = ""
    # Define query parameters
    query_parameters = [
        bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
        bigquery.ScalarQueryParameter("admin_level", "STRING", admin_level),
    ]
    if country_name:
        country_name = country_name.replace("'", "\\'")
        country_name_filter = "AND ('name:en', @country_name) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))"
        query_parameters.append(
            bigquery.ScalarQueryParameter("country_name", "STRING", country_name)
        )
    extra_condition = ""
    if location_type == LocationType.COUNTRY:
        extra_condition = "AND ('ISO3166-1', @country_code) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))"
    elif location_type == LocationType.SUBDIVISION:
        extra_condition = (
            f"AND EXISTS (SELECT 1 FROM UNNEST(all_tags) AS tag WHERE tag.key = 'ISO3166-2' "
            f"AND tag.value LIKE '{country_code}-%')"
        )
    # For "locality", we assume no extra ISO tag condition is needed.

    query = f"""
        WITH bounding_area AS (
          SELECT geometry
          FROM `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons`
          WHERE
            ('ISO3166-1', @country_code) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))
            {country_name_filter}
            AND ('boundary', 'administrative') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))
            AND ('admin_level', '2') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))
        )
        SELECT planet_features.*
        FROM `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons` planet_features, bounding_area
        WHERE
          ('boundary', 'administrative') IN (SELECT STRUCT(key, value) FROM UNNEST(planet_features.all_tags))
          AND ('admin_level', @admin_level) IN (SELECT STRUCT(key, value) FROM UNNEST(planet_features.all_tags))
          {extra_condition}
          AND ST_DWithin(bounding_area.geometry, planet_features.geometry, 0);
    """
    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    return query, job_config


def fetch_data(admin_level, country_code, location_type, country_name=None):
    """Fetch data for a specific admin level."""
    query, job_config = generate_query(
        admin_level, country_code, location_type, country_name
    )
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    logging.info("Fetched %s rows for admin level %s.", results.total_rows, admin_level)

    data = []
    for row in results:
        if row["osm_id"] is None:
            continue
        all_tags = {tag["key"]: tag["value"] for tag in row.all_tags}
        data.append(
            {
                "admin_lvl": admin_level,
                "osm_id": row.osm_id,
                "iso3166_1": all_tags.get("ISO3166-1"),
                "iso3166_2": all_tags.get("ISO3166-2"),
                "name": all_tags.get("name"),
                "name:en": all_tags.get("name:en"),
                "name:fr": all_tags.get("name:fr"),
                "geometry": row.geometry,
                "alt_name": all_tags.get("alt_name"),
                "alt_name:en": all_tags.get("alt_name"),
            }
        )
    return data


@with_db_session
def save_to_database(data, db_session=None):
    """Save data to the database."""
    for row in data:
        if not row["name"] or not row["geometry"]:
            logging.info("Skipping row with missing data: %s", row["osm_id"])
            continue

        geopolygon = (
            db_session.query(Geopolygon)
            .filter(Geopolygon.osm_id == row["osm_id"])
            .first()
        )
        if geopolygon:
            logging.info("Geopolygon with osm_id %s already exists.", row["osm_id"])
        else:
            logging.info("Adding geopolygon with osm_id %s.", row["osm_id"])
            geopolygon = Geopolygon(osm_id=row["osm_id"])
            db_session.add(geopolygon)

        geopolygon.admin_level = row["admin_lvl"]
        geopolygon.iso_3166_1_code = row["iso3166_1"]
        geopolygon.iso_3166_2_code = row["iso3166_2"]
        geopolygon.name = row["name:en"] if row["name:en"] else row["name"]
        geopolygon.alt_name = row["alt_name"] if row["alt_name"] else row["alt_name:en"]
        geopolygon.geometry = WKTElement(row["geometry"], srid=4326)
    db_session.commit()


def get_saved_geopolygon_rows(data):
    """Get rows that will be saved to the geopolygon table."""
    rows_by_osm_id = {}
    for row in data:
        if row.get("osm_id") is not None and row.get("name") and row.get("geometry"):
            rows_by_osm_id[row["osm_id"]] = row
    return list(rows_by_osm_id.values())


def _upsert_hierarchy_rows(db_session, rows):
    """Upsert precomputed hierarchy edges keyed by osm_id."""
    hierarchy_table = Geopolygonhierarchy.__table__
    statement = insert(hierarchy_table).values(rows)
    db_session.execute(
        statement.on_conflict_do_update(
            index_elements=[hierarchy_table.c.osm_id],
            set_={
                "parent_osm_id": statement.excluded.parent_osm_id,
                "country_osm_id": statement.excluded.country_osm_id,
                "subdivision_osm_id": statement.excluded.subdivision_osm_id,
                "updated_at": func.current_timestamp(),
            },
        )
    )


def _upsert_locality_hierarchy(
    db_session, locality_osm_ids, subdivision_osm_ids, country_osm_id
):
    """Match localities to their parents within the current run and upsert the edges.

    ``parent_osm_id`` is the deepest lower-admin-level polygon from this run that
    covers the locality (so nested localities keep their real parent), while
    ``subdivision_osm_id`` records the covering subdivision for direct lookups. Each
    locality's representative point is computed once, and containment is tested with
    ``ST_Covers`` against the raw (spatially indexed) candidate geometry. Point-in-
    polygon is robust to invalid polygons, so the large candidate geometries are
    never repaired with ``ST_MakeValid`` here.
    """
    hierarchy_table = Geopolygonhierarchy.__table__
    child = aliased(Geopolygon)
    parent_candidate = aliased(Geopolygon)
    subdivision_candidate = aliased(Geopolygon)
    parent_candidate_ids = subdivision_osm_ids + locality_osm_ids

    locality_points = (
        select(
            child.osm_id.label("osm_id"),
            child.admin_level.label("admin_level"),
            func.ST_PointOnSurface(func.ST_MakeValid(child.geometry)).label("point"),
        )
        .where(child.osm_id.in_(locality_osm_ids))
        .where(child.geometry.isnot(None))
        .cte("locality_points")
    )

    parent = (
        select(parent_candidate.osm_id.label("parent_osm_id"))
        .where(parent_candidate.osm_id.in_(parent_candidate_ids))
        .where(parent_candidate.admin_level < locality_points.c.admin_level)
        .where(parent_candidate.geometry.op("&&")(locality_points.c.point))
        .where(func.ST_Covers(parent_candidate.geometry, locality_points.c.point))
        .order_by(
            parent_candidate.admin_level.desc(),
            func.ST_Area(parent_candidate.geometry).asc(),
        )
        .limit(1)
        .lateral("parent_match")
    )

    subdivision = (
        select(subdivision_candidate.osm_id.label("subdivision_osm_id"))
        .where(subdivision_candidate.osm_id.in_(subdivision_osm_ids))
        .where(subdivision_candidate.geometry.op("&&")(locality_points.c.point))
        .where(func.ST_Covers(subdivision_candidate.geometry, locality_points.c.point))
        .order_by(func.ST_Area(subdivision_candidate.geometry).asc())
        .limit(1)
        .lateral("subdivision_match")
    )

    matched = select(
        locality_points.c.osm_id.label("osm_id"),
        func.coalesce(parent.c.parent_osm_id, literal(country_osm_id)).label(
            "parent_osm_id"
        ),
        literal(country_osm_id).label("country_osm_id"),
        subdivision.c.subdivision_osm_id.label("subdivision_osm_id"),
        func.current_timestamp().label("updated_at"),
    ).select_from(
        locality_points.outerjoin(parent, true()).outerjoin(subdivision, true())
    )

    statement = insert(hierarchy_table).from_select(
        [
            "osm_id",
            "parent_osm_id",
            "country_osm_id",
            "subdivision_osm_id",
            "updated_at",
        ],
        matched,
    )
    db_session.execute(
        statement.on_conflict_do_update(
            index_elements=[hierarchy_table.c.osm_id],
            set_={
                "parent_osm_id": statement.excluded.parent_osm_id,
                "country_osm_id": statement.excluded.country_osm_id,
                "subdivision_osm_id": statement.excluded.subdivision_osm_id,
                "updated_at": statement.excluded.updated_at,
            },
        )
    )


@with_db_session
def update_geopolygon_hierarchy(saved_rows, db_session=None):
    """Update hierarchy edges for the geopolygons saved in the current populate run.

    Country and subdivision edges are derived directly from the ISO codes collected
    during the run, so they require no spatial computation. Localities are the only
    rows matched by geometry, and only against this run's subdivisions.
    """
    if not saved_rows:
        logging.info("Skipping hierarchy update because no geopolygons were saved.")
        return

    logging.info("Updating hierarchy for %s geopolygons.", len(saved_rows))
    country_rows = [row for row in saved_rows if row.get("iso3166_1")]
    subdivision_rows = [
        row for row in saved_rows if not row.get("iso3166_1") and row.get("iso3166_2")
    ]
    locality_osm_ids = [
        row["osm_id"]
        for row in saved_rows
        if not row.get("iso3166_1") and not row.get("iso3166_2")
    ]
    country_osm_id = country_rows[0]["osm_id"] if country_rows else None
    subdivision_osm_ids = [row["osm_id"] for row in subdivision_rows]

    direct_hierarchy_rows = [
        {
            "osm_id": row["osm_id"],
            "parent_osm_id": None,
            "country_osm_id": None,
            "subdivision_osm_id": None,
        }
        for row in country_rows
    ]
    direct_hierarchy_rows.extend(
        {
            "osm_id": row["osm_id"],
            "parent_osm_id": country_osm_id,
            "country_osm_id": country_osm_id,
            "subdivision_osm_id": None,
        }
        for row in subdivision_rows
    )
    if direct_hierarchy_rows:
        _upsert_hierarchy_rows(db_session, direct_hierarchy_rows)

    if locality_osm_ids:
        _upsert_locality_hierarchy(
            db_session, locality_osm_ids, subdivision_osm_ids, country_osm_id
        )

    db_session.commit()
    logging.info("Hierarchy update completed for %s geopolygons.", len(saved_rows))


@with_db_session
def refresh_location_search_view(db_session=None):
    """Refresh the location search read model after geopolygon updates."""
    logging.info("Refreshing GeopolygonLocationSearch materialized view.")
    db_session.execute(
        DDL("REFRESH MATERIALIZED VIEW CONCURRENTLY GeopolygonLocationSearch")
    )
    db_session.commit()
    logging.info("GeopolygonLocationSearch materialized view refreshed.")


@functions_framework.http
def reverse_geolocation_populate(request):
    """
    Cloud Function entry point to populate the reverse geolocation database.
    This function accepts a POST request with a JSON body like:
    {
        "country_code": "CA", # Required, ISO 3166-1 alpha-2 country code
        "admin_levels": "2,4,6", # Optional, comma-separated list of admin levels, otherwise levels are computed
    }
    """
    global client
    client = bigquery.Client()
    logging.info("Reverse geolocation database population triggered.")

    try:
        country_code, locality_admin_levels = parse_request_parameters(request)
        logging.info("Country code parsed: %s", country_code)
    except ValueError as e:
        logging.error(e)
        return str(e), 400

    try:
        country_admin_levels = fetch_country_admin_levels(country_code)
        if not country_admin_levels:
            raise ValueError(f"No admin levels found for country {country_code}")
        subdivision_admin_levels = fetch_subdivision_admin_levels(country_code)
        if not subdivision_admin_levels:
            raise ValueError(
                f"No subdivision admin levels found for country {country_code}"
            )

        country_admin_level = country_admin_levels[0]

        logging.info("Country admin level: %s", country_admin_level)
        logging.info("Subdivision admin levels: %s", subdivision_admin_levels)

        if not locality_admin_levels:
            locality_admin_levels = get_locality_admin_levels(
                country_code, country_admin_level, subdivision_admin_levels
            )
        logging.info("Filtered admin levels: %s", locality_admin_levels)

        data = []

        # Fetch country level data
        data.extend(fetch_data(country_admin_level, country_code, LocationType.COUNTRY))
        country_name = data[0]["name:en"] or data[0]["name"]
        logging.info("Extracted country name: %s", country_name)

        # Fetch subdivision level data
        for level in subdivision_admin_levels:
            data.extend(
                fetch_data(level, country_code, LocationType.SUBDIVISION, country_name)
            )

        # Fetch locality level data
        for level in locality_admin_levels:
            data.extend(
                fetch_data(level, country_code, LocationType.LOCALITY, country_name)
            )
        saved_rows = get_saved_geopolygon_rows(data)
        save_to_database(data)
        update_geopolygon_hierarchy(saved_rows)
        refresh_location_search_view()
        result = f"Database initialized for {country_code}."
        logging.info(result)
        return result, 200

    except Exception as e:
        logging.error("Error processing %s: %s", country_code, e)
        return str(e), 400


def get_locality_admin_levels(country_code, country_admin_level, subdivision_levels):
    """Get the pertinent admin levels for the localities (city/municipality) given country code."""
    # Get parent dir of current file
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    locality_levels_file = os.path.join(parent_dir, "locality_admin_levels.json")
    with open(locality_levels_file) as file:
        locality_levels_per_country = json.load(file)
        if country_code in locality_levels_per_country:
            locality_levels = locality_levels_per_country[country_code]
            logging.info("Locality levels: %s", locality_levels)
        else:
            locality_levels = [
                max(subdivision_levels + [country_admin_level])
                + 1,  # Adding a level 1 level higher than the highest subdivision level
                max(subdivision_levels + [country_admin_level])
                + 2,  # Adding a level 2 levels higher than the highest subdivision level
            ]
    locality_levels = [level for level in locality_levels if level <= 8][:5]
    return locality_levels
