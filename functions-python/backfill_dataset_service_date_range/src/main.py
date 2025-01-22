import logging
import os
import functions_framework

from shared.helpers.logger import Logger

from shared.helpers.database import Database

from typing import TYPE_CHECKING
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

from shared.database_gen.sqlacodegen_models import Gtfsdataset

import requests
import json

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)


# function backfills the service date range columns in the gtfsdataset table that are null
# this will not overwrite any existing values
def backfill_datasets(session: "Session"):
    # Only care about datasets where service_date_range_start and service_date_range_end are NULL
    changes_count = 0
    datasets = (
        session.query(Gtfsdataset)
        .options(joinedload(Gtfsdataset.validation_reports))
        .filter(
            or_(
                Gtfsdataset.service_date_range_start.is_(None),
                Gtfsdataset.service_date_range_end.is_(None),
            )
        )
    )

    for dataset in datasets:
        print(f"Processing gtfsdataset ID {dataset.id}")
        gtfsdataset_id = dataset.id

        # Get the latest validation report for the dataset
        latest_validation_report = max(
            dataset.validation_reports,
            key=lambda report: report.validated_at,
            default=None,
        )

        if not latest_validation_report:
            print(
                f"Skipping gtfsdataset ID {gtfsdataset_id}: no validation reports found."
            )
            continue

        json_report_url = latest_validation_report.json_report

        try:
            # Download the JSON report
            response = requests.get(json_report_url)
            response.raise_for_status()
            json_data = response.json()
            extracted_service_start_date = (
                json_data.get("summary", {})
                .get("feedInfo", {})
                .get("feedStartDate", None)
            )
            extracted_service_end_date = (
                json_data.get("summary", {})
                .get("feedInfo", {})
                .get("feedEndDate", None)
            )

            if extracted_service_start_date is None:
                print(
                    f"Key 'summary.feedInfo.feedStartDate' not found in JSON for gtfsdataset ID {gtfsdataset_id}."
                )
                continue

            if extracted_service_end_date is None:
                print(
                    f"Key 'summary.feedInfo.feedEndDate' not found in JSON for gtfsdataset ID {gtfsdataset_id}."
                )
                continue

            dataset.service_date_range_start = extracted_service_start_date
            dataset.service_date_range_end = extracted_service_end_date

            formatted_dates = (
                extracted_service_start_date + " - " + extracted_service_end_date
            )
            print(
                f"Updated gtfsdataset ID {gtfsdataset_id} with value: {formatted_dates}"
            )
            changes_count += 1

        except requests.RequestException as e:
            print(f"Error downloading JSON for gtfsdataset ID {gtfsdataset_id}: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for gtfsdataset ID {gtfsdataset_id}: {e}")
        except Exception as e:
            print(f"Error processing gtfsdataset ID {gtfsdataset_id}: {e}")

    try:
        session.commit()
        print("Database changes committed.")
    except Exception as e:
        print("Error committing changes:", e)
        session.rollback()
    finally:
        session.close()
        return changes_count


@functions_framework.http
def backfill_dataset_service_date_range(_):
    """Fills gtfs dataset service date range from the latest validation report."""
    Logger.init_logger()
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    change_count = 0
    try:
        with db.start_db_session() as session:
            logging.info("Database session started.")
            change_count = backfill_datasets(session)

    except Exception as error:
        logging.error(f"Error creating validation report entities: {error}")
        return f"Error creating validation report entities: {error}", 500
    finally:
        pass

    return f"Script executed successfully. {change_count} datasets updated", 200
