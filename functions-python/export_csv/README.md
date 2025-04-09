# Export and Upload Feeds to CSV  
This cloud function reads feed data from the database, processes it to extract relevant information, exports it to a CSV file, and uploads the file to a specified Google Cloud Storage bucket.

## Overview  
The function performs the following steps:  
1. Retrieves GTFS and GTFS-RT feeds from the database.  
2. Processes each feed to extract essential details, including location, provider, URLs, and features.  
3. Exports the processed data to a local CSV file.  
4. Uploads the CSV file to a Google Cloud Storage bucket.  
5. Returns an HTTP response indicating the success or failure of the operation.  

## Project Structure  

- **`main.py`**: The main file containing the cloud function implementation and utility functions.

## Function Configuration
The function requires the following environment variables to be set:
- `FEEDS_DATABASE_URL`: URL to access the feeds database.
- `DATASETS_BUCKET_NAME`: Name of the Google Cloud Storage bucket.

## Local Development

For local development, follow the same steps as for other functions in the project. Please refer to the [README.md](../README.md) file in the parent directory for detailed instructions.
