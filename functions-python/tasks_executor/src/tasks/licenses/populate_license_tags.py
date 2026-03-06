# This script defines a task to populate the 'license_tag' table in the database from a canonical
# JSON file. It is designed to be triggered as a background task.
#
# The script performs the following steps:
# 1. Fetches the 'tags.json' file from the MobilityData/licenses-aas GitHub repository.
# 2. The JSON file categorises tags into groups (e.g., 'spdx', 'license', 'domain', 'copyleft').
#    Each group contains a '_group' metadata entry and individual tag entries.
# 3. For each group and each tag (skipping the '_group' metadata key) it builds a record with:
#    a. id: composite key of the form "group:tag" (e.g., "spdx:osi-approved")
#    b. group: the group name (e.g., "spdx")
#    c. tag: the tag name (e.g., "osi-approved")
#    d. description: human-readable description of the tag
# 4. For each tag record, it performs an "upsert" operation using SQLAlchemy's `merge` method,
#    with the tag's composite 'id' acting as the primary key.
# 5. Supports a 'dry_run' mode, which simulates the process and logs intended actions
#    without committing any changes to the database.
# 6. Includes error handling for network issues and database transactions.
import logging

import requests
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Licensetag

TAGS_JSON_URL = (
    "https://raw.githubusercontent.com/MobilityData/licenses-aas/main/data/tags.json"
)


def populate_license_tags_handler(payload):
    """
    Handler for populating license tags.

    Args:
        payload (dict): Incoming payload data.
    """
    dry_run = get_parameters(payload)
    return populate_license_tags_task(dry_run)


@with_db_session
def populate_license_tags_task(dry_run, db_session):
    """
    Populates license tags in the database from a canonical JSON source.

    Args:
        dry_run (bool): If True, simulates the operation without making changes.
        db_session: Database session for executing queries.
    """
    logging.info("Starting populate_license_tags_task with dry_run=%s", dry_run)

    try:
        logging.info("Downloading tags from %s", TAGS_JSON_URL)
        response = requests.get(TAGS_JSON_URL, timeout=10)
        response.raise_for_status()
        tags_json = response.json()

        tags_data = []
        for group_name, group_entries in tags_json.items():
            for tag_name, tag_entry in group_entries.items():
                if tag_name == "_group":
                    # Skip the group-level metadata entry
                    continue
                tag_id = f"{group_name}:{tag_name}"
                tags_data.append(
                    {
                        "id": tag_id,
                        "group": group_name,
                        "tag": tag_name,
                        "description": tag_entry.get("description"),
                    }
                )

        logging.info("Loaded %d tags from %d groups.", len(tags_data), len(tags_json))

        if dry_run:
            logging.info("Dry run: would insert/update %d tags.", len(tags_data))
        else:
            for tag_data in tags_data:
                tag_object = Licensetag(
                    id=tag_data["id"],
                    group=tag_data["group"],
                    tag=tag_data["tag"],
                    description=tag_data["description"],
                )
                db_session.merge(tag_object)

            logging.info(
                "Successfully upserted %d tags into the database.", len(tags_data)
            )

    except requests.exceptions.RequestException as e:
        logging.error("Failed to download tags JSON file: %s", e)
        raise
    except Exception as e:
        logging.error("An error occurred while populating license tags: %s", e)
        db_session.rollback()
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
