import logging
import os

from main import DatasetProcessor


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
    file_hash, is_zip, extracted_files_path = processor.download_content(tempfile)
    are_files_extracted = os.path.exists(extracted_files_path)
    logging.info(f"File hash: {file_hash}")
    logging.info(
        f"File path: {extracted_files_path} "
        f"- { 'Files extracted' if are_files_extracted else 'Files not extracted'}"
    )
    logging.info(f"Downloaded file path: {extracted_files_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Replace with actual producer URL
    verify_download_content(
        producer_url="https://files.mobilitydatabase.org"
        "/mdb-1891/mdb-1891-202507020119/mdb-1891-202507020119.zip"
    )
