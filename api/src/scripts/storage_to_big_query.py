import json

from google.cloud import bigquery, storage
from google.cloud.bigquery.job import LoadJobConfig, SourceFormat

# Set up your Google Cloud project and bucket details
project_id = 'mobility-feeds-dev'
bucket_name = 'mobilitydata-datasets-dev'
dataset_id = 'gtfs_analytics'
table_id = 'validation_report'

# Initialize clients
storage_client = storage.Client(project=project_id)
bigquery_client = bigquery.Client(project=project_id)


# Create a BigQuery dataset if it doesn't exist
def create_bigquery_dataset():
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        bigquery_client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_id} already exists.")
    except:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "northamerica-northeast1"  # Set to your preferred location
        bigquery_client.create_dataset(dataset)
        print(f"Created dataset {dataset_id}.")


# Create a BigQuery table
def create_bigquery_table():
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    table_ref = dataset_ref.table(table_id)

    try:
        bigquery_client.get_table(table_ref)
        print(f"Table {table_id} already exists.")
    except Exception as e:
        schema = [
            bigquery.SchemaField("summary", "RECORD", mode="NULLABLE", fields=[
                bigquery.SchemaField("validatorVersion", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("validatedAt", "TIMESTAMP", mode="NULLABLE"),
                bigquery.SchemaField("gtfsInput", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("threads", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("outputDirectory", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("systemErrorsReportName", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("validationReportName", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("htmlReportName", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("countryCode", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("dateForValidation", "DATE", mode="NULLABLE"),
                bigquery.SchemaField("feedInfo", "RECORD", mode="NULLABLE", fields=[
                    bigquery.SchemaField("publisherName", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("publisherUrl", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("feedLanguage", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("feedStartDate", "DATE", mode="NULLABLE"),
                    bigquery.SchemaField("feedEndDate", "DATE", mode="NULLABLE"),
                ]),
                bigquery.SchemaField("agencies", "RECORD", mode="REPEATED", fields=[
                    bigquery.SchemaField("name", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("phone", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("email", "STRING", mode="NULLABLE"),
                ]),
                bigquery.SchemaField("files", "STRING", mode="REPEATED"),
                bigquery.SchemaField("counts", "RECORD", mode="NULLABLE", fields=[
                    bigquery.SchemaField("Shapes", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("Stops", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("Routes", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("Trips", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("Agencies", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("Blocks", "INTEGER", mode="NULLABLE"),
                ]),
                bigquery.SchemaField("gtfsFeatures", "STRING", mode="REPEATED"),
            ]),
            bigquery.SchemaField("notices", "RECORD", mode="REPEATED", fields=[
                bigquery.SchemaField("code", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("severity", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("totalNotices", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("sampleNotices", "STRING", mode="NULLABLE"),
            ]),
            bigquery.SchemaField("feedId", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("datasetId", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("validatedAt", "TIMESTAMP", mode="NULLABLE"),
        ]

        table = bigquery.Table(table_ref, schema=schema)
        table = bigquery_client.create_table(table)
        print(f"Created table {table.project}.{table.dataset_id}.{table.table_id}")


# Access the bucket and process JSON files
def process_bucket_files():
    bucket = storage_client.get_bucket(bucket_name)
    blobs = storage_client.list_blobs(bucket_name)

    for blob in blobs:
        if 'report_' in blob.name and blob.name.endswith('.json'):
            feed_id = blob.name.split('/')[0]
            feed_dataset_id = blob.name.split('/')[1]
            report_id = '.'.join(blob.name.split('/')[2].split('.')[:-1])
            json_data = json.loads(blob.download_as_string().decode('utf-8'))

            # Add feedId to the JSON data
            json_data['feedId'] = feed_id
            json_data['datasetId'] = feed_dataset_id

            # Extract validatedAt and add it to the same level
            validated_at = json_data['summary'].get('validatedAt', None)
            json_data['validatedAt'] = validated_at

            # Convert sampleNotices to JSON strings
            for notice in json_data.get('notices', []):
                if 'sampleNotices' in notice:
                    notice['sampleNotices'] = json.dumps(notice['sampleNotices'], separators=(',', ':'))

            # Convert the JSON data to a single NDJSON record (one line)
            ndjson_content = json.dumps(json_data, separators=(',', ':'))
            ndjson_blob_name = f"ndjson/{feed_id}/{feed_dataset_id}/{report_id}.ndjson"
            ndjson_blob = bucket.blob(ndjson_blob_name)
            ndjson_blob.upload_from_string(ndjson_content + '\n')
            print(f"Processed and uploaded {ndjson_blob_name}")


# Load NDJSON data to BigQuery
def load_data_to_bigquery():
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    table_ref = dataset_ref.table(table_id)
    source_uris = []
    blobs = storage_client.list_blobs(bucket_name, prefix='ndjson/')
    for blob in blobs:
        uri = f"gs://{bucket_name}/{blob.name}"
        source_uris.append(uri)

    if len(source_uris) > 0:
        job_config = LoadJobConfig()
        job_config.source_format = SourceFormat.NEWLINE_DELIMITED_JSON

        load_job = bigquery_client.load_table_from_uri(
            source_uris,
            table_ref,
            job_config=job_config
        )
        try:
            load_job.result()  # Wait for the job to complete
            print(
                f"Loaded {len(source_uris)} files into {table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}")
        except Exception as e:
            print(f"An error occurred while loading data to BigQuery: {e}")
            for error in load_job.errors:
                print(f"Error: {error['message']}")
                if 'location' in error:
                    print(f"Location: {error['location']}")
                if 'debugInfo' in error:
                    print(f"Debug Info: {error['reason']}")


def main():
    create_bigquery_dataset()
    create_bigquery_table()
    process_bucket_files()
    load_data_to_bigquery()


if __name__ == "__main__":
    main()
