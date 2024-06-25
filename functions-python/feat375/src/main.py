import io
import logging
import os
from urllib.parse import urlparse

import functions_framework
import pandas as pd
from google.cloud import storage

from helpers.utils import download_url_content

logging.basicConfig(level=logging.INFO)
env = os.getenv("ENV", "dev").lower()
destination_bucket_name = f"catalog-analytics-{env}"
source_bucket_name = "mdb-latest"
sources_csv_link = "https://bit.ly/catalogs-csv"
analytics_object_name = "lts_datasets_hashes.json"
storage_client = storage.Client()


def get_blob(bucket_name, source_blob_name, bucket=None):
    """Gets a blob from the bucket."""
    if bucket is None:
        bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    return blob


def get_object_name_from_url(url):
    """Extracts the object name from a Google Cloud Storage URL."""
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split("/")

    # The object name is the segment after '/o/'
    try:
        object_index = path_segments.index("o") + 1
        object_name = "/".join(path_segments[object_index:])
    except ValueError:
        raise ValueError("Invalid URL format for extracting object name.")

    return object_name


def extend_dataframe(df1, df2):
    """Extends df1 with df2 after verifying one is empty or both have the same columns."""
    if df1.empty:
        # If the first DataFrame is empty, return the second DataFrame
        return df2
    elif set(df1.columns) == set(df2.columns):
        # If both DataFrames have the same columns, concatenate them
        return pd.concat([df1, df2], ignore_index=True)
    else:
        raise ValueError(
            "The DataFrames do not have the same columns and df1 is not empty."
        )


@functions_framework.http
def retrieve_datasets_hash(request):
    logging.info("Retrieving datasets hash function started")
    today = pd.Timestamp.now().date().strftime("%Y-%m-%d")

    # 1. Read existing summary file
    analytics_blob = get_blob(destination_bucket_name, analytics_object_name)
    try:
        analytics_blob.reload()
        analytics_content = analytics_blob.download_as_string()
        analytics_df = pd.read_json(io.BytesIO(analytics_content), orient="records")
        logging.info(f"Analytics file has {len(analytics_df)} entries")
    except Exception as e:
        logging.error(f"Error reading analytics file: {e}")
        analytics_df = pd.DataFrame()

    # 2. Retrieve sources CSV
    sources_csv_string = download_url_content(sources_csv_link)
    try:
        sources_df = pd.read_csv(io.BytesIO(sources_csv_string))
        logging.info(f"Sources dataframe has {len(sources_df)} entries")
    except Exception as e:
        logging.error(f"Error reading sources CSV as DataFrame: {e}")
        return "Error reading sources CSV", 500

    gtfs_feeds = sources_df[sources_df["data_type"] == "gtfs"]
    logging.info(f"Getting hash for {len(gtfs_feeds)} GTFS feeds")

    # 3. Get hash for each feed
    source_bucket = storage_client.bucket(source_bucket_name)
    lts_datasets_hashes = []
    time_now = pd.Timestamp.now()

    for _, row in gtfs_feeds.iterrows():
        feed_id = f"mdb-{row['mdb_source_id']}"
        try:
            url = row["urls.latest"]
            object_name = get_object_name_from_url(url)
            if not object_name.endswith(".zip"):
                logging.error(
                    f"Feed {feed_id} with object {object_name} is not a zip file"
                )
                continue

            logging.info(f"Getting hash for feed {feed_id} -- {object_name}")
            object_blob = get_blob(
                source_bucket_name, object_name, bucket=source_bucket
            )
            if not object_blob.exists():
                logging.error(
                    f"Feed {feed_id} with object {object_name} does not exist"
                )
                continue
            object_blob.reload()
            lts_dataset_hash = object_blob.md5_hash
            if lts_dataset_hash is None:
                logging.error(
                    f"Feed {feed_id} with object {object_name} does not have a hash"
                )
                continue

            logging.info(f"Hash for feed {feed_id}: {lts_dataset_hash}")
            lts_datasets_hashes.append(
                {"feed_id": feed_id, "hash": lts_dataset_hash, "date": today}
            )
        except Exception as e:
            logging.error(f"Error getting hash for dataset {feed_id}: {e}")

    time_taken = pd.Timestamp.now() - time_now
    logging.info(f"Time taken to process all GTFS feeds: {time_taken.seconds} seconds")

    # 4. Append new content to the analytics content
    new_data_df = pd.DataFrame(lts_datasets_hashes)
    analytics_df = extend_dataframe(analytics_df, new_data_df)

    # 5. Upload analytics content to the destination bucket
    try:
        analytics_json = analytics_df.to_json(orient="records")
        analytics_blob.upload_from_string(
            analytics_json, content_type="application/json"
        )
        logging.info(
            f"Uploaded updated analytics content to {destination_bucket_name}/{analytics_object_name}"
            f"\n {analytics_df}"
        )
    except Exception as e:
        logging.error(f"Error uploading updated analytics content: {e}")
        return "Error uploading updated analytics content", 500

    return analytics_json
