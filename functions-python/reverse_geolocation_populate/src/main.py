import logging

import functions_framework
from google.cloud import bigquery
from helpers.logger import Logger
import os
import pycountry
from geoalchemy2 import WKTElement
from helpers.database import start_db_session
from database_gen.sqlacodegen_models import Geopolygon

client = None
logging.basicConfig(level=logging.INFO)


def parse_request_parameters(request):
    """Parse and validate request parameters including country code."""
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    if not request_json or "country_code" not in request_json:
        logging.error("Request missing required country_code parameter.")
        raise ValueError("Invalid request parameters: country_code is required.")

    code = request_json["country_code"]
    if pycountry.countries.get(alpha_2=code) is None:
        logging.error(f"Invalid country code detected: {code}")
        raise ValueError(f"Invalid country code: {code}")

    return code


def fetch_subdivision_admin_levels(country_code):
    """Fetch distinct subdivision admin levels for the given country code."""
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


def generate_query(admin_level, country_code, is_lower=False, country_name=None):
    """Generate the query for a specific admin level."""
    country_name_filter = ""
    query_parameters = [
        bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
        bigquery.ScalarQueryParameter("admin_level", "STRING", admin_level),
    ]
    if country_name is not None:
        country_name = country_name.replace("'", "\'")
        country_name_filter = "AND ('name:en', @country_name) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))"
        query_parameters.append(bigquery.ScalarQueryParameter("country_name", "STRING", country_name))

    iso_3166_1_condition = (
        f"AND ('ISO3166-1', '{country_code}') IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))"
        if not is_lower
        else ""
    )
    # Construct the query with placeholders
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

    # Define the parameters
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
            bigquery.ScalarQueryParameter("country_name", "STRING", country_name),
            bigquery.ScalarQueryParameter("admin_level", "STRING", admin_level),
        ]
    )
    return query, job_config

def fetch_data(admin_level, country_code, is_lower=False, country_name=None):
    """Fetch data for a specific admin level."""
    query, job_config = generate_query(admin_level, country_code, is_lower, country_name)
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    logging.info(f"Number of Level {admin_level} results: {results.total_rows}")

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
    Logger.init_logger()
    global client
    client = bigquery.Client()
    logging.info(
        "Batch function triggered for reverse geolocation database initialization."
    )
    # Connect to the database
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
    except Exception as e:
        logging.error(f"Error connecting to the database: {e}")
        return str(e), 500

    # Parse request parameters
    try:
        country_code = parse_request_parameters(request)
        logging.info(f"Request parameters parsed: {country_code}")
        # Check if country code is in the database
        if session.query(Geopolygon).filter(Geopolygon.iso_3166_1_code == country_code).one_or_none():
            return f"Reverse geolocation database already initialized for country code: {country_code}.", 200
    except ValueError as e:
        logging.error(e)
        return str(e), 400

    try:
        # Fetch all subdivision admin levels
        subdivision_levels = fetch_subdivision_admin_levels(country_code)
        logging.info(f"Subdivision admin levels: {subdivision_levels}")

        # Dynamically generate admin levels
        admin_levels = set(
            [2]
            + subdivision_levels
            + [max(subdivision_levels + [2]) + 1, max(subdivision_levels + [2]) + 2]
        )
        # Keep only admin levels <= 8
        admin_levels = [level for level in admin_levels if level <= 8]
        # order admin levels
        admin_levels.sort()
        logging.info(f"Admin levels: {admin_levels}")
        # keep the first 5 admin levels
        admin_levels = admin_levels[:5]
        logging.info(f"Admin levels after filtering: {admin_levels}")

        data = []
        country_name = None
        for level in admin_levels:
            data.extend(fetch_data(level, country_code, level > 2, country_name))
            logging.info(f"Data fetched for Level {level}: {len(data)}")
            logging.info(data)
            if level == 2:
                if not data:
                    logging.error(f"No data found for country code: {country_code}")
                    return f"No data found for country code: {country_code}", 404
                else:
                    data = [elem for elem in data if elem["iso3166_1"] == country_code] # Filter out non-country data
                    country_name = data[0]["name:en"] if data[0]["name:en"] else data[0]["name"]
                    if not country_name:
                        logging.error(f"Country name not found for country code: {country_code}")
                        return f"Country name not found for country code: {country_code}", 404
                    logging.info(f"Country name extracted: {country_name}")
                    logging.info(f"Data after filtering: {len(data)}")
                    logging.info(data)

        # Initialize GCP storage and database
        save_to_database(data, session)

        return (
            f"Reverse geolocation database initialized for country code: {country_code}.",
            200,
        )
    except Exception as e:
        logging.error(f"Error initializing reverse geolocation database for country code {country_code}: {e}")
        return str(e), 400
