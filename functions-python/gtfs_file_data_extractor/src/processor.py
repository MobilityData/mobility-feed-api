import io
import logging
from typing import Tuple

import flask
import pandas as pd
import requests
from sqlalchemy.orm import Session

from extractors.registry import get_extractor
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsdataset

ERROR_STATUS_CODE = 500
REQUIRED_PARAMETERS = ("stable_id", "dataset_id", "file_name", "file_url")


def parse_request_parameters(request: flask.Request) -> Tuple[str, str, str, str]:
    """
    Parse and validate the Cloud Task payload.

    Expected JSON body:
    {
        "stable_id": "<feed stable id>",
        "dataset_id": "<dataset stable id>",
        "file_name": "feed_info.txt",
        "file_url": "<hosted_url of the GTFS file>"
    }
    """
    request_json = request.get_json(silent=True)
    logging.info("Request JSON: %s", request_json)
    if not request_json:
        raise ValueError("Missing or invalid JSON body.")
    missing = [key for key in REQUIRED_PARAMETERS if not request_json.get(key)]
    if missing:
        raise ValueError(f"Missing required parameters: {missing}.")
    return (
        request_json["stable_id"],
        request_json["dataset_id"],
        request_json["file_name"],
        request_json["file_url"],
    )


def load_dataset(dataset_id: str, db_session: Session) -> Gtfsdataset:
    dataset = (
        db_session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if not dataset:
        raise ValueError(
            f"Dataset with ID {dataset_id} does not exist in the database."
        )
    return dataset


def read_csv_from_url(file_url: str) -> pd.DataFrame:
    response = requests.get(file_url)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.content.decode("utf-8")))


@with_db_session
def process_file_data(
    request: flask.Request, db_session: Session = None
) -> Tuple[str, int]:
    """
    Download a single GTFS file and dispatch it to the registered extractor,
    which persists the extracted data to the database.
    """
    try:
        stable_id, dataset_id, file_name, file_url = parse_request_parameters(request)
    except ValueError as error:
        logging.error("Invalid request: %s", error)
        return str(error), 400

    extractor = get_extractor(file_name)
    if extractor is None:
        message = f"No extractor registered for file '{file_name}'. Skipping."
        logging.info(message)
        return message, 200

    try:
        dataset = load_dataset(dataset_id, db_session)
        df = read_csv_from_url(file_url)
        extractor.extract(df, dataset, db_session)
        db_session.commit()
    except Exception as error:
        db_session.rollback()
        logging.error(
            "Error extracting data from %s for dataset %s: %s",
            file_name,
            dataset_id,
            error,
        )
        return f"Error extracting data from {file_name}: {error}", ERROR_STATUS_CODE

    message = f"Successfully extracted data from {file_name} for dataset {dataset_id}."
    logging.info(message)
    return message, 200
