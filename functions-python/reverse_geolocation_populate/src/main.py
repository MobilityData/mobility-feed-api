import json
import logging
import os

import functions_framework
import pycountry
from geoalchemy2 import WKTElement
from google.cloud import bigquery

from shared.database_gen.sqlacodegen_models import Geopolygon
from shared.database.database import with_db_session
from shared.helpers.logger import init_logger
from enum import Enum


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
        save_to_database(data)
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
