import logging
import os
import functions_framework

from shared.helpers.logger import Logger

from shared.helpers.database import Database

from typing import TYPE_CHECKING
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, func
from shared.helpers.database import refresh_materialized_view
from shared.helpers.timezone import (
    extract_timezone_from_json_validation_report,
    get_service_date_range_with_timezone_utc,
)

from shared.database_gen.sqlacodegen_models import (
    Gtfsdataset,
    Validationreport,
    t_feedsearch,
)

import requests
import json

from google.cloud import storage

env = os.getenv("ENV", "dev").lower()
bucket_name = f"mobilitydata-datasets-{env}"

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)


def is_version_gte(target_version: str, version_field):
    target_parts = func.string_to_array(target_version, ".")
    version_parts = func.string_to_array(version_field, ".")
    return func.array_to_string(version_parts, ".") >= func.array_to_string(
        target_parts, "."
    )


# function backfills the service date range columns in the gtfsdataset table that are null
# this will not overwrite any existing values
def backfill_datasets(session: "Session"):
    # Only care about datasets where service_date_range_start or service_date_range_end are NULL
    changes_count = 0
    total_changes_count = 0
    elements_per_commit = 100
    # blob setup
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    datasets = (
        session.query(Gtfsdataset)
        .options(joinedload(Gtfsdataset.validation_reports))
        .filter(
            or_(
                Gtfsdataset.service_date_range_start.is_(None),
                Gtfsdataset.service_date_range_end.is_(None),
            )
        )
        .filter(
            Gtfsdataset.validation_reports.any(
                is_version_gte("6.0.0", Validationreport.validator_version)
            )
        )
    ).all()

    logging.info(f"Found {len(datasets)} datasets to process.")

    for dataset in datasets:
        logging.info(f"Processing gtfsdataset ID {dataset.stable_id}")
        gtfsdataset_id = dataset.stable_id
        feed_stable_id = "-".join(gtfsdataset_id.split("-")[0:2])
        # Get the latest validation report for the dataset
        latest_validation_report = max(
            dataset.validation_reports,
            key=lambda report: report.validated_at,
            default=None,
        )

        if not latest_validation_report:
            logging.info(
                f"Skipping gtfsdataset ID {gtfsdataset_id}: no validation reports found."
            )
            continue

        json_report_url = latest_validation_report.json_report

        try:
            # Download the JSON report
            blob_url = f"{feed_stable_id}/{gtfsdataset_id}/report_{latest_validation_report.validator_version}.json"
            logging.info("Blob URL: " + blob_url)
            dataset_blob = bucket.blob(blob_url)
            if not dataset_blob.exists():
                logging.info("Blob not found, downloading from URL")
                response = requests.get(json_report_url)
                response.raise_for_status()
                json_data = response.json()
            else:
                try:
                    logging.info("Blob found, downloading from blob")
                    json_data = json.loads(dataset_blob.download_as_string())
                except Exception as e:
                    logging.error(f"Error downloading blob: {e} trying json report url")
                    response = requests.get(json_report_url)
                    response.raise_for_status()
                    json_data = response.json()

            if (
                result := get_service_date_range_with_timezone_utc(json_data)
            ) is not None:
                utc_service_start_date, utc_service_end_date = result
                dataset.service_date_range_start = utc_service_start_date
                dataset.service_date_range_end = utc_service_end_date

            formatting_timezone = extract_timezone_from_json_validation_report(
                json_data
            )

            if formatting_timezone is not None:
                dataset.agency_timezone = formatting_timezone

            formatted_dates = f"{utc_service_start_date:%Y-%m-%d %H:%M} - {utc_service_end_date:%Y-%m-%d %H:%M}"
            logging.info(
                f"Updated gtfsdataset ID {gtfsdataset_id} with value: {formatted_dates}"
            )
            total_changes_count += 1
            changes_count += 1
            if changes_count >= elements_per_commit:
                try:
                    changes_count = 0
                    session.commit()
                    refresh_materialized_view(session, t_feedsearch.name)
                    logging.info(f"{changes_count} elements committed.")
                except Exception as e:
                    logging.error("Error committing changes:", e)
                    session.rollback()
                    session.close()
                    raise Exception(f"Error creating dataset: {e}")

        except requests.RequestException as e:
            logging.error(
                f"Error downloading JSON for gtfsdataset ID {gtfsdataset_id}: {e}"
            )
        except json.JSONDecodeError as e:
            logging.error(
                f"Error parsing JSON for gtfsdataset ID {gtfsdataset_id}: {e}"
            )
        except Exception as e:
            logging.error(f"Error processing gtfsdataset ID {gtfsdataset_id}: {e}")

    try:
        session.commit()
        logging.info("Database changes committed.")
        session.close()
        return total_changes_count
    except Exception as e:
        logging.error("Error committing changes:", e)
        session.rollback()
        session.close()
        raise Exception(f"Error creating dataset: {e}")


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
        logging.error(f"Error setting the datasets service date range values: {error}")
        return f"Error setting the datasets service date range values: {error}", 500

    return f"Script executed successfully. {change_count} datasets updated", 200
