import logging
import os
import pycountry

from google.cloud import bigquery
from geoalchemy2 import WKTElement
from helpers.database import Database
from helpers.logger import Logger
from database_gen.sqlacodegen_models import Geopolygon
import functions_framework

# Initialize logging
logging.basicConfig(level=logging.INFO)
client = None  # Global BigQuery client


def parse_request_parameters(request):
    """Parse and validate request parameters, including the country code."""
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    if not request_json or "country_code" not in request_json:
        logging.error("Request missing required country_code parameter.")
        raise ValueError("Invalid request parameters: country_code is required.")

    country_code = request_json["country_code"]
    if pycountry.countries.get(alpha_2=country_code) is None:
        logging.error(f"Invalid country code detected: {country_code}")
        raise ValueError(f"Invalid country code: {country_code}")

    admin_levels = request_json.get("admin_levels", None)
    try:
        if admin_levels:
            admin_levels = [int(level) for level in admin_levels.split(",")]
        if admin_levels and not all(2 <= level <= 8 for level in admin_levels):
            raise ValueError("Invalid admin levels.")
    except ValueError:
        logging.error(f"Invalid admin levels detected: {admin_levels}")
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


def generate_query(admin_level, country_code, is_lower=False, country_name=None):
    """Generate the query for a specific admin level."""
    logging.info(
        f"Generating query for admin level: {admin_level}, country code: {country_code}"
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

    iso_3166_1_condition = (
        f"AND ('ISO3166-1', '{country_code}') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))"
        if not is_lower
        else ""
    )

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
          AND ST_DWithin(bounding_area.geometry, planet_features.geometry, 0)
          {iso_3166_1_condition};
    """

    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    return query, job_config


def fetch_data(admin_level, country_code, is_lower=False, country_name=None):
    """Fetch data for a specific admin level."""
    query, job_config = generate_query(
        admin_level, country_code, is_lower, country_name
    )
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    logging.info(f"Fetched {results.total_rows} rows for admin level {admin_level}.")

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
            }
        )
    return data


def save_to_database(data, session):
    """Save data to the database."""
    for row in data:
        if not row["name"] or not row["geometry"]:
            logging.info(f"Skipping row with missing data: {row['osm_id']}")
            continue

        geopolygon = (
            session.query(Geopolygon).filter(Geopolygon.osm_id == row["osm_id"]).first()
        )
        if geopolygon:
            logging.info(f"Geopolygon with osm_id {row['osm_id']} already exists.")
        else:
            logging.info(f"Adding geopolygon with osm_id {row['osm_id']}.")
            geopolygon = Geopolygon(osm_id=row["osm_id"])
            session.add(geopolygon)

        geopolygon.admin_level = row["admin_lvl"]
        geopolygon.iso_3166_1_code = row["iso3166_1"]
        geopolygon.iso_3166_2_code = row["iso3166_2"]
        geopolygon.name = row["name:en"] if row["name:en"] else row["name"]
        geopolygon.geometry = WKTElement(row["geometry"], srid=4326)
    session.commit()


@functions_framework.http
def reverse_geolocation_populate(request):
    """Cloud Function entry point to populate the reverse geolocation database."""
    Logger.init_logger()
    global client
    client = bigquery.Client()
    logging.info("Reverse geolocation database population triggered.")

    try:
        session = Database().start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
    except Exception as e:
        logging.error(f"Error connecting to the database: {e}")
        return str(e), 500

    try:
        country_code, admin_levels = parse_request_parameters(request)
        logging.info(f"Country code parsed: {country_code}")

        if (
            not admin_levels
            and session.query(Geopolygon)
            .filter(Geopolygon.iso_3166_1_code == country_code)
            .first()
        ):
            return f"Database already initialized for {country_code}.", 200
    except ValueError as e:
        logging.error(e)
        return str(e), 400

    try:
        country_admin_levels = fetch_country_admin_levels(country_code)
        if not country_admin_levels:
            raise ValueError(f"No admin levels found for country {country_code}")
        country_admin_level = country_admin_levels[0]
        logging.info(f"Country admin level: {country_admin_level}")
        if not admin_levels:
            admin_levels = get_admin_levels(country_code, country_admin_level)
        logging.info(f"Filtered admin levels: {admin_levels}")

        data = []
        country_name = None
        for level in admin_levels:
            data.extend(
                fetch_data(
                    level, country_code, level > country_admin_level, country_name
                )
            )
            if level == country_admin_level and data:
                country_name = data[0]["name:en"] or data[0]["name"]
                logging.info(f"Extracted country name: {country_name}")

        save_to_database(data, session)
        return f"Database initialized for {country_code}.", 200

    except Exception as e:
        logging.error(f"Error processing {country_code}: {e}")
        return str(e), 400


def get_admin_levels(country_code, country_admin_level):
    """Get the pertinent admin levels for the given country code."""
    subdivision_levels = fetch_subdivision_admin_levels(country_code)
    logging.info(f"Subdivision levels: {subdivision_levels}")
    admin_levels = sorted(
        {
            country_admin_level,
            *subdivision_levels,
            max(subdivision_levels + [country_admin_level])
            + 1,  # Adding a level higher than the highest subdivision level
            max(subdivision_levels + [country_admin_level])
            + 2,  # Adding another level higher than the highest subdivision level
        }
    )
    admin_levels = [level for level in admin_levels if level <= 8][:5]
    return admin_levels
