import logging

import requests
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
        response = requests.get(RULES_JSON_URL, timeout=10)
        response.raise_for_status()
        rules_json = response.json()
        # Type mapping to satisfy the check constraint of Rule.type
        TYPE_MAPPING = {
            "permissions": "permission",
            "conditions": "condition",
            "limitations": "limitation",
        }

        # Combine all rule lists from the three categories
        rules_data = []
        for rule_type, rule_list in rules_json.items():
            normalized_type = TYPE_MAPPING[rule_type]
            for rule_data in rule_list:
                rule_data["type"] = normalized_type
                rules_data.append(rule_data)

        logging.info(
            f"Loaded {len(rules_data)} rules from {len(rules_json)} categories."
        )

        if dry_run:
            logging.info(f"Dry run: would insert/update {len(rules_data)} rules.")
        else:
            for rule_data in rules_data:
                rule_object = Rule(
                    name=rule_data.get("name"),
                    label=rule_data.get("label"),
                    description=rule_data.get("description"),
                    type=rule_data.get("type"),
                )
                db_session.merge(rule_object)

            db_session.commit()
            logging.info(
                f"Successfully upserted {len(rules_data)} rules into the database."
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
