#
# This script populates the local database with reverse geolocation data for all ISO 3166-1 alpha-2 codes.
# It reads the country codes from a JSON file and sends a POST request to the `reverse_geolocation_populate` endpoint
# for each country code to populate the database.
# This is an expensive operation and should be used with caution.
# To avoid overloading the local database, only a subset of countries is processed.
# The filtered countries are: US, CA, GB, FR, DE, IT, ES, JP and IN.
#
# Usage(from this function's root directory):
# PYTHONPATH=src python src/scripts/populate_local_db_countries.py
#

import json
import logging
from pathlib import Path

from flask import Flask, Request

from main import reverse_geolocation_populate

iso_3166_1_codes_file = "iso_3166_1_alpha_2_codes.json"

SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / iso_3166_1_codes_file

country_filter = ["US", "CA", "GB", "FR", "DE", "IT", "ES", "JP", "IN"]
logging.basicConfig(level=logging.INFO)


def populate_db():
    """Populate the local database with reverse geolocation data for all ISO 3166-1 alpha-2 codes."""
    global app, code, data, request
    app = Flask(__name__)
    with app.test_request_context(
        path="/reverse_geolocation_populate",
        method="POST",
        headers={"Content-Type": "application/json"},
    ):
        # Load the ISO 3166-1 alpha-2 codes from the JSON file, item per item in the json list
        with open(JSON_PATH, "r") as file:
            iso_3166_1_codes = json.load(file)
        for code_with_name in iso_3166_1_codes:
            # This conditional reduce the number of countries to process
            if code_with_name["country_code"] not in country_filter:
                continue
            code = code_with_name["country_code"]
            country_name = code_with_name["country_name"]
            logging.info("Populating database for country: %s(%s)", country_name, code)
            data = {"country_code": code}
            request = Request.from_values(
                method="POST",
                path="/reverse_geolocation_populate",
                data=json.dumps(data),
                headers={"Content-Type": "application/json"},
            )
            reverse_geolocation_populate(request)


if __name__ == "__main__":
    populate_db()
