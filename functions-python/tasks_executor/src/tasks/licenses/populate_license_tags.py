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
from shared.database_gen.sqlacodegen_models import LicenseTag, LicenseTagGroup


TAGS_JSON_URL = "https://raw.githubusercontent.com/MobilityData/licenses-catalog/main/data/tags.json"


@with_db_session
def populate_license_tags(dry_run, db_session):
    """
    Populates license tags in the database from a canonical JSON source.

    Args:
        dry_run (bool): If True, simulates the operation without making changes.
        db_session: Database session for executing queries.
    """
    logging.info("Starting populate_license_tags with dry_run=%s", dry_run)

    try:
        logging.info("Downloading tags from %s", TAGS_JSON_URL)
        response = requests.get(TAGS_JSON_URL, timeout=10)
        response.raise_for_status()
        tags_json = response.json()

        tags_data = []
        groups_data = {}

        for group_name, group_entries in tags_json.items():
            group_meta = group_entries.get("_group", {}) or {}
            groups_data[group_name] = {
                "id": group_name,
                "short_name": group_meta.get("short"),
                "description": group_meta.get("description") or group_name,
            }

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
                        "url": tag_entry.get("url"),
                    }
                )

        logging.info(
            "Loaded %d groups and %d tags from tags.json.",
            len(groups_data),
            len(tags_data),
        )

        if dry_run:
            logging.info(
                "Dry run: would insert/update %d groups and %d tags.",
                len(groups_data),
                len(tags_data),
            )
        else:
            # Upsert groups first so FK from license_tag.group is satisfied
            for group in groups_data.values():
                group_object = LicenseTagGroup(
                    id=group["id"],
                    short_name=group["short_name"],
                    description=group["description"],
                )
                db_session.merge(group_object)

            # Then upsert tags that reference those groups
            for tag_data in tags_data:
                tag_object = LicenseTag(
                    id=tag_data["id"],
                    group=tag_data["group"],
                    tag=tag_data["tag"],
                    description=tag_data["description"],
                    url=tag_data["url"],
                )
                db_session.merge(tag_object)

            logging.info(
                "Successfully upserted %d groups and %d tags into the database.",
                len(groups_data),
                len(tags_data),
            )

    except requests.exceptions.RequestException as e:
        logging.error("Failed to download tags JSON file: %s", e)
        raise
    except Exception as e:
        logging.error("An error occurred while populating license tags: %s", e)
        db_session.rollback()
        raise
