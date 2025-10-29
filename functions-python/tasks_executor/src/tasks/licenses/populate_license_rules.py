import logging

from fastapi import requests
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Rule

RULES_JSON_URL = (
    "https://raw.githubusercontent.com/MobilityData/licenses-aas/main/data/rules.json"
)


def populate_license_rules_handler(payload):
    """
    Handler for populating license rules.

    Args:
        payload (dict): Incoming payload data.

    """
    (dry_run) = get_parameters(payload)
    return populate_license_rules_task(dry_run)


@with_db_session
def populate_license_rules_task(dry_run, db_session):
    """
    Populates license rules in the database. This function is triggered by a Cloud Task.

    Args:
        dry_run (bool): If True, the function will simulate the operation without making changes.
        db_session: Database session for executing queries.
    """
    logging.info(f"Starting populate_license_rules_task with dry_run={dry_run}")

    try:
        logging.info(f"Downloading rules from {RULES_JSON_URL}")
        response = requests.get(RULES_JSON_URL)
        response.raise_for_status()
        rules_data = response.json()
        logging.info(f"Rules data downloaded: {rules_data}")
        logging.info(f"Successfully downloaded {len(rules_data)} rules.")

        if dry_run:
            logging.info("Dry run enabled. No changes will be made to the database.")
            logging.info(f"Would attempt to upsert {len(rules_data)} rules.")
        else:
            logging.info("Populating license rules in the database...")

            for rule_data in rules_data:
                # Create a Rule ORM object from the downloaded data
                rule_object = Rule(
                    name=rule_data.get("name"),
                    label=rule_data.get("label"),
                    description=rule_data.get("description"),
                    type=rule_data.get("type"),
                )
                # Merge the object into the session.
                # If a rule with the same primary key (name) exists, it will be updated.
                # If not, a new one will be inserted.
                db_session.merge(rule_object)

            db_session.commit()
            logging.info(
                f"License rules populated successfully. {len(rules_data)} rules were upserted."
            )
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download rules JSON file: {e}")
        raise
    except Exception as e:
        logging.error(f"An error occurred while populating license rules: {e}")
        db_session.rollback()
        raise


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        tuple: (dry_run, after_date)
    """
    dry_run = payload.get("dry_run", False)
    return dry_run
