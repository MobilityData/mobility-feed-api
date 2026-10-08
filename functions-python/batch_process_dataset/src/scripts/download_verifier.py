import argparse
import json
import logging
import os

from main import DatasetProcessor
from gcp_storage_emulator.server import create_server
from shared.helpers.utils import FeedDownloadError

HOST = "localhost"
PORT = 9023
BUCKET_NAME = "verifier"


def verify_download_content(producer_url: str, feed_id=None):
    """
    Verifies the download_content is able to retrieve the file.
    This is useful to simulate the download code locally and test issues related with
    user-agent and downloaded content.
    Authenticated feeds are not supported currently.

    Pass feed_id to apply the per-feed feed_download/http_headers override from the
    config database, as the nightly run does.
    """
    logging.info("Producer URL: %s", producer_url)

    processor = DatasetProcessor(
        producer_url=producer_url,
        feed_id=feed_id,
        feed_stable_id=None,
        execution_id=None,
        latest_hash=None,
        bucket_name=None,
        authentication_type=0,
        api_key_parameter_name=None,
        public_hosted_datasets_url=None,
    )
    tempfile = processor.generate_temp_filename()
    logging.info("Temp filename: %s", tempfile)
    try:
        file_hash, is_zip = processor.download_content(tempfile, feed_id)
    except FeedDownloadError as exc:
        logging.error("Download failed")
        logging.error(json.dumps(exc.diagnostics.as_dict(), indent=2, default=str))
        raise
    logging.info(
        "Downloaded file from %s is a valid ZIP file: %s", producer_url, is_zip
    )
    logging.info("File hash: %s", file_hash)


def verify_upload_dataset(producer_url: str):
    """
    Verifies the upload_dataset is able to upload the dataset to the GCP storage emulator.
    This is useful to simulate the upload code locally and test issues related with
    user-agent and uploaded content.
    This function also tests the DatasetProcessor class methods for generating a temporary
    filename and uploading the dataset.
    """
    processor = DatasetProcessor(
        producer_url=producer_url,
        feed_id="feed_id_2126",
        feed_stable_id="feed_stable_id",
        execution_id=None,
        latest_hash="123",
        bucket_name=BUCKET_NAME,
        authentication_type=0,
        api_key_parameter_name=None,
        public_hosted_datasets_url=None,
    )
    tempfile = processor.generate_temp_filename()
    logging.info("Temp filename: %s", tempfile)
    dataset_file = processor.transfer_dataset("feed_id_2126", False)
    logging.info("Dataset File: %s", dataset_file)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a GTFS feed through the shared download code and print the "
        "request and response detail of the attempt."
    )
    parser.add_argument("--url", required=True, help="Producer URL of the feed.")
    parser.add_argument(
        "--feed_id",
        default=None,
        help="Feed UUID, to apply the per-feed http_headers config override.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Only verify the download, skipping the GCP storage emulator.",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    os.environ["WORKING_DIR"] = "/tmp/verifier"
    os.makedirs(os.environ["WORKING_DIR"], exist_ok=True)

    if args.skip_upload:
        verify_download_content(producer_url=args.url, feed_id=args.feed_id)
        logging.info("Download content verification completed successfully.")
        return

    os.environ["STORAGE_EMULATOR_HOST"] = f"http://{HOST}:{PORT}"
    server = create_server(
        host=HOST, port=PORT, in_memory=False, default_bucket=BUCKET_NAME
    )
    server.start()
    try:
        verify_download_content(producer_url=args.url, feed_id=args.feed_id)
        logging.info("Download content verification completed successfully.")
        verify_upload_dataset(producer_url=args.url)
    finally:
        server.stop()
        logging.info("Verification completed.")


if __name__ == "__main__":
    main()
