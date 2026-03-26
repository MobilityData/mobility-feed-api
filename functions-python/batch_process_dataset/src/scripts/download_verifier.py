import logging
import os

from main import DatasetProcessor
from gcp_storage_emulator.server import create_server

HOST = "localhost"
PORT = 9023
BUCKET_NAME = "verifier"
PRODUCER_URL = "https://example.com/dataset.zip"  # Replace with actual producer URL


def verify_download_content(producer_url: str):
    """
    Verifies the download_content is able to retrieve the file
    This is useful to simulate the download code locally and test issues related with user-agent and downloaded content.
    Not supported authenticated feeds currently.
    """
    logging.info("Verifying downloaded content... (not implemented)")

    logging.info(f"Producer URL: {producer_url}")

    processor = DatasetProcessor(
        producer_url=producer_url,
        feed_id=None,
        feed_stable_id=None,
        execution_id=None,
        latest_hash=None,
        bucket_name=None,
        authentication_type=0,
        api_key_parameter_name=None,
        public_hosted_datasets_url=None,
    )
    tempfile = processor.generate_temp_filename()
    logging.info(f"Temp filename: {tempfile}")
    file_hash, is_zip = processor.download_content(tempfile, "feed_id")
    logging.info(f"Downloaded file from {producer_url} is a valid ZIP file: {is_zip}")
    logging.info(f"File hash: {file_hash}")


def verify_upload_dataset(producer_url: str):
    """
    Verifies the upload_dataset is able to upload the dataset to the GCP storage emulator.
    This is useful to simulate the upload code locally and test issues related with user-agent and uploaded content.
    This function also tests the DatasetProcessor class methods for generating a temporary filename
    and uploading the dataset.
    :param producer_url:
    :return:
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
    logging.info(f"Temp filename: {tempfile}")
    dataset_file = processor.transfer_dataset("feed_id_2126", False)
    logging.info(f"Dataset File: {dataset_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Replace with actual producer URL
    try:
        os.environ["STORAGE_EMULATOR_HOST"] = f"http://{HOST}:{PORT}"
        os.environ["WORKING_DIR"] = "/tmp/verifier"
        # create working dir if not exists
        if not os.path.exists(os.environ["WORKING_DIR"]):
            os.makedirs(os.environ["WORKING_DIR"])

        server = create_server(
            host=HOST, port=PORT, in_memory=False, default_bucket=BUCKET_NAME
        )
        server.start()

        verify_download_content(producer_url=PRODUCER_URL)
        logging.info("Download content verification completed successfully.")
        verify_upload_dataset(producer_url=PRODUCER_URL)
    except Exception as e:
        logging.error(f"Error verifying download content: {e}")
    finally:
        server.stop()
        logging.info("Verification completed.")
