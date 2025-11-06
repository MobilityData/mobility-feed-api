# This script defines a task to populate the 'licenses' table and the 'license_rules'
# association table in the database. It is designed to be triggered as a background task.
#
# The script performs the following steps:
# 1. Fetches a list of license definition files from the MobilityData/licenses-aas GitHub repository
#    using the GitHub API.
# 2. Downloads the JSON content of each individual license file.
# 3. For each license:
#    a. Parses the JSON, extracting license details primarily from the nested 'spdx' object.
#       This includes the license ID, name, URL, and full license text.
#    b. Creates a new 'License' record or updates an existing one based on the license ID.
#    c. Extracts the associated rule names from the 'permissions', 'conditions', and 'limitations'
#       lists at the top level of the JSON.
#    d. Queries the 'rules' table to find the corresponding Rule objects.
#    e. Associates the found rules with the license. The SQLAlchemy ORM automatically
#       manages the creation of records in the 'license_rules' join table to establish
#       the many-to-many relationship.
# 4. Supports a 'dry_run' mode, which simulates the process and logs intended
#    actions without committing any changes to the database.
# 5. Includes error handling for network issues and database transactions.
import logging
from datetime import datetime, timezone

import requests
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import License, Rule

LICENSES_API_URL = (
    "https://api.github.com/repos/MobilityData/licenses-aas/contents/data/licenses"
)


def populate_licenses_handler(payload):
    """
    Handler for populating licenses.

    Args:
        payload (dict): Incoming payload data.
    """
    dry_run = get_parameters(payload)
    return populate_licenses_task(dry_run)


@with_db_session
def populate_licenses_task(dry_run, db_session):
    """
    Populates licenses and their associated rules in the database.

    Args:
        dry_run (bool): If True, simulates the operation without making changes.
        db_session: Database session for executing queries.
    """
    logging.info("Starting populate_licenses_task with dry_run=%s", dry_run)

    try:
        logging.info("Downloading license list from %s", LICENSES_API_URL)
        response = requests.get(LICENSES_API_URL, timeout=10)
        response.raise_for_status()
        files = response.json()

        licenses_data = []
        for file_info in files:
            if file_info["type"] == "file" and file_info["name"].endswith(".json"):
                download_url = file_info["download_url"]
                license_response = requests.get(download_url, timeout=10)
                license_response.raise_for_status()
                licenses_data.append(license_response.json())

        logging.info("Loaded %d licenses.", len(licenses_data))

        if dry_run:
            logging.info("Dry run: would process %d licenses.", len(licenses_data))
        else:
            for license_data in licenses_data:
                spdx_data = license_data.get("spdx")
                if not spdx_data:
                    logging.warning("Skipping license record without 'spdx' data")
                    continue
                else:
                    is_spdx = True
                license_id = spdx_data.get("licenseId")
                if not license_id:
                    logging.warning("Skipping record without licenseId.")
                    continue

                logging.info("Processing license %s", license_id)

                license_object = db_session.get(License, license_id)
                if not license_object:
                    license_object = License(id=license_id)
                    license_object.created_at = datetime.now(timezone.utc)

                license_object.is_spdx = is_spdx
                if is_spdx:
                    license_object.type = "standard"
                else:
                    license_object.type = "custom"
                license_object.name = spdx_data.get("name")
                license_object.updated_at = datetime.now(timezone.utc)
                cross_ref_list = spdx_data.get("crossRef")
                if (
                    cross_ref_list
                    and isinstance(cross_ref_list, list)
                    and cross_ref_list
                ):
                    license_object.url = cross_ref_list[0].get("url")
                else:
                    license_object.url = None

                license_object.content_txt = spdx_data.get("licenseText")
                license_object.content_html = spdx_data.get("licenseTextHtml")

                # Clear existing rules to handle updates
                license_object.rules = []

                all_rule_names = []
                for rule_type in ["permissions", "conditions", "limitations"]:
                    all_rule_names.extend(license_data.get(rule_type, []))

                all_rule_names = [
                    name[:-1] if name.endswith("s") else name for name in all_rule_names
                ]

                if all_rule_names:
                    rules = (
                        db_session.query(Rule)
                        .filter(Rule.name.in_(all_rule_names))
                        .all()
                    )
                    license_object.rules.extend(rules)
                    if len(rules) != len(all_rule_names):
                        logging.warning(
                            "License '%s': Found %d of %d rules in the database.",
                            license_id,
                            len(rules),
                            len(all_rule_names),
                        )
                # Merge the license object into the session. This handles both creating new licenses
                # and updating existing ones (upsert), including their rule associations.
                db_session.merge(license_object)

            logging.info(
                "Successfully upserted licenses into the database.",
            )

    except requests.exceptions.RequestException as e:
        logging.error("Failed to download licenses JSON file: %s", e)
        raise


def get_parameters(payload):
    """
    Get parameters from the payload.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        bool: dry_run
    """
    return payload.get("dry_run", False)
