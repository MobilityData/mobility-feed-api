import io
import logging
import os
import zipfile
from typing import List, Dict

import functions_framework
import pandas as pd
import pycountry
import requests
from geoalchemy2 import WKTElement
from google.cloud import storage
from shapely.geometry import Point

from database_gen.sqlacodegen_models import (
    Admingeography,
    Supportedreversegeocodingcountry, Location,
)
from helpers.database import start_db_session
from helpers.logger import Logger
from helpers.utils import save_to_bucket, fetch_df_from_bucket

logging.basicConfig(level=logging.INFO)


def generate_geonames_id(country_code, admin1_code, admin2_code) -> str:
    """Generate a GeoNames ID from the country_code, admin1_code, and admin2_code."""
    try:
        admin1_code_str = str(int(float(admin1_code)))
    except ValueError:
        admin1_code_str = admin1_code
    try:
        admin2_code_str = str(int(float(admin2_code)))
    except ValueError:
        admin2_code_str = admin2_code
    geonames_id = f"{country_code}.{admin1_code_str}.{admin2_code_str}"
    logging.debug(f"Generated GeoNames ID: {geonames_id}")
    return geonames_id


def parse_request_parameters(request):
    """Parse and validate request parameters including country codes and force_update flag."""
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    if not request_json or "country_codes" not in request_json:
        logging.error("Request missing required country_codes parameter.")
        raise ValueError("Invalid request parameters: country_codes is required.")

    country_codes = set(request_json["country_codes"].split(","))
    for code in country_codes:
        if pycountry.countries.get(alpha_2=code) is None:
            logging.error(f"Invalid country code detected: {code}")
            raise ValueError(f"Invalid country code: {code}")

    force_update = bool(request_json.get("force_update", False))
    logging.info(
        f"Request parsed successfully with country_codes: {country_codes} and force_update: {force_update}"
    )
    return country_codes, force_update

def get_countries_geonames_id(country_codes: List[str], df: pd.DataFrame) -> Dict[str, int]:
    """Generate a list of GeoNames IDs from the country_codes."""
    geonames_ids = dict()
    for country_code in country_codes:
        geonames_id = df[
            (df["country_code"] == country_code)
            & (df["feature_code"] == "PCLI")
            & (df["feature_class"] == "A")
        ]
        if len(geonames_id) == 1:
            geonames_ids[country_code] = geonames_id.iloc[0]["geonameid"]
            logging.info(f"Country code {country_code} has geoname id {geonames_id}")
        else:
            logging.error(f"Country code {country_code} not found")
            logging.error(geonames_id)
    return geonames_ids


def download_and_save_all_countries(bucket):
    """Download and save allCountries.txt from GeoNames to GCP Storage as allCountries.csv."""
    logging.info("Downloading allCountries.zip from GeoNames.")
    url = "https://download.geonames.org/export/dump/allCountries.zip"
    response = requests.get(url)
    response.raise_for_status()
    logging.info("Download successful. Processing allCountries.txt.")

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        with zip_file.open("allCountries.txt") as file:
            column_names = [
                "geonameid",
                "name",
                "asciiname",
                "alternatenames",
                "latitude",
                "longitude",
                "feature_class",
                "feature_code",
                "country_code",
                "cc2",
                "admin1_code",
                "admin2_code",
                "admin3_code",
                "admin4_code",
                "population",
                "elevation",
                "dem",
                "timezone",
                "modification_date",
            ]
            logging.info("Reading allCountries.txt into DataFrame.")
            df = pd.read_csv(file, delimiter="\t", names=column_names, na_values="")
            logging.info("allCountries.txt processed successfully.")
            logging.info("Saving allCountries.csv to GCP bucket.")
            save_to_bucket(bucket, "allCountries.csv", df.to_csv(index=False))
            logging.info("Saved allCountries.csv to GCP bucket.")
            return df


def fetch_sources_country_codes():
    """Download sources.csv and extract valid country codes, returning as a set."""
    logging.info("Fetching sources.csv to retrieve valid country codes.")
    sources_url = "https://bit.ly/catalogs-csv"
    sources_content = requests.get(sources_url).content
    sources_df = pd.read_csv(io.StringIO(sources_content.decode("utf-8")))
    country_codes = set(sources_df["location.country_code"])
    logging.info(f"Fetched valid country codes from sources.csv: {country_codes}")
    return country_codes


def filter_and_merge_data(df, country_codes):
    """Filter for ADM1 and ADM2 entries in the DataFrame and merge them, limited to given country codes."""
    logging.info("Filtering and merging ADM1 and ADM2 data.")
    adm1_df = df[df["feature_code"] == "ADM1"]
    adm2_df = df[df["feature_code"] == "ADM2"]
    adm2_with_adm1 = pd.merge(
        adm2_df,
        adm1_df[["geonameid", "country_code", "admin1_code", "name"]],
        on=["country_code", "admin1_code"],
        suffixes=("_municipality", "_subdivision"),
    )
    adm2_with_adm1 = adm2_with_adm1[adm2_with_adm1["country_code"].isin(country_codes)]
    logging.info("Data filtered and merged based on provided country codes.")
    return adm2_with_adm1


def populate_database_with_locations(session, adm2_with_adm1, all_countries_df, country_codes):
    """Populate the database with location records for each valid country code in the DataFrame."""
    logging.info("Populating database with geolocation data.")
    country_codes_geonames_id = get_countries_geonames_id(country_codes, all_countries_df)
    if len(country_codes_geonames_id) != len(country_codes):
        logging.error("Not all country codes have a geoname id")
        raise ValueError("Not all country codes have a geoname id")

    for _, row in adm2_with_adm1[adm2_with_adm1["country_code"].isin(country_codes)].iterrows():
        country_code = row["country_code"]
        country_geoname_id = country_codes_geonames_id[country_code]
        admin1_geoname_id, admin2_geoname_id = row["geonameid_subdivision"], row["geonameid_municipality"]
        admin1_code, admin2_code = row["admin1_code"], row["admin2_code"]
        name_subdivision, name_municipality = (
            row["name_subdivision"],
            row["name_municipality"],
        )
        composite_id = f"{country_code}-{name_subdivision}-{name_municipality}".replace(
            " ", "_"
        )
        logging.info(f"Processing geolocation entry for {composite_id}.")

        geolocation = (
            session.query(Admingeography)
            .filter(Admingeography.id == composite_id)
            .one_or_none()
        )
        location = (
            session.query(Location)
            .filter(Location.id == composite_id)
            .one_or_none()
        )
        if location is None:
            logging.info(f"Creating new location entry for {composite_id}.")
            location = Location(
                id=composite_id,
                country_code=country_code,
                country=pycountry.countries.get(alpha_2=country_code).name,
                subdivision_name=name_subdivision,
                municipality=name_municipality,
            )
            session.add(location)

        if geolocation is None:
            logging.info(f"Creating new geolocation entry for {composite_id}.")
            geolocation = Admingeography(
                location_id=composite_id,
                id=composite_id,
            )
        else:
            logging.info(f"Updating geolocation entry for {composite_id}.")

        geonames_id = f"{country_geoname_id}.{admin1_geoname_id}.{admin2_geoname_id}"
        geolocation.geonames_id = geonames_id

        # Fetch all latitude/longitude points for admin1/admin2 region from all_countries_df
        locations = all_countries_df[
            (all_countries_df["country_code"] == country_code)
            & (all_countries_df["admin1_code"] == admin1_code)
            & (all_countries_df["admin2_code"] == admin2_code)
            ]
        logging.info(f"Found {len(locations)} locations for {composite_id}.")
        points = {
            Point(loc["longitude"], loc["latitude"]) for _, loc in locations.iterrows()
        }
        logging.info(f"Found {len(points)} unique points for {composite_id}.")
        if points:
            geometry_wkt = f"GEOMETRYCOLLECTION({', '.join([f'POINT({p.x} {p.y})' for p in points])})"
            logging.info("Generated WKT geometry for geolocation entry:" + geometry_wkt)
            geolocation.coordinates = WKTElement(geometry_wkt, srid=4326)
            session.add(geolocation)

        if (
                session.query(Supportedreversegeocodingcountry)
                        .filter(Supportedreversegeocodingcountry.country_code == country_code)
                        .count()
                == 0
        ):
            session.add(Supportedreversegeocodingcountry(country_code=country_code))
            logging.info(
                f"Added {country_code} to supported reverse geocoding countries."
            )
        session.commit()
    logging.info("Database population completed.")


@functions_framework.http
def reverse_geolocation_populate(request):
    Logger.init_logger()
    logging.info(
        "Batch function triggered for reverse geolocation database initialization."
    )

    # Parse request parameters
    try:
        country_codes, force_update = parse_request_parameters(request)
    except ValueError as e:
        logging.error(e)
        return str(e), 400

    # Initialize GCP storage and database
    bucket_name = os.getenv("BUCKET_NAME")
    if not bucket_name:
        logging.error("BUCKET_NAME environment variable not set.")
        return "BUCKET_NAME environment variable not set.", 500

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)

    # Download and process data
    try:
        all_countries_df = fetch_df_from_bucket(bucket, "allCountries.csv")
        if all_countries_df is None or force_update:
            logging.info(
                "No preprocessed allCountries.csv found in bucket or force_update is enabled. Processing raw data."
            )
            all_countries_df = download_and_save_all_countries(bucket)

        valid_country_codes = fetch_sources_country_codes().union(country_codes)
        adm2_with_adm1 = filter_and_merge_data(all_countries_df, valid_country_codes)

    except Exception as e:
        logging.error(f"Error during data processing: {e}")
        return "Data processing error.", 500

    # Populate the database
    populate_database_with_locations(session, adm2_with_adm1, all_countries_df, country_codes)
    logging.info("Reverse geolocation database initialization complete.")
    return (
        f"Reverse geolocation database initialized for country codes: {', '.join(country_codes)}.",
        200,
    )
