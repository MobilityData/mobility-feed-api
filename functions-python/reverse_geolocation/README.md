# Reverse Geolocation

This folder contains the logic necessary to reverse geolocate a GTFS feed. The process consists of multiple cloud functions that handle batch processing, event-driven triggers, and the actual reverse geolocation of GTFS stop coordinates.

## Function Overview

- **[Batch Reverse Geolocation](#1-reverse_geolocation_batch-function) (HTTP function)**: Triggers the reverse geolocation process for a batch of feeds.
- **[Storage & Pub/Sub triggered functions](#2-reverse-geolocation-triggered-functions)**: Handle events from new dataset uploads or messages in the `reverse-geolocation` Pub/Sub topic.
- **[Reverse Geolocation Processor](#3-reverse_geolocation_process-function) (HTTP function)**: Performs the actual reverse geolocation of stop coordinates in a GTFS feed.

---

## 1. `reverse_geolocation_batch` Function

This HTTP function initiates reverse geolocation for multiple feeds. It accepts a POST request with the following optional parameter:

- **`country_codes`** (optional): A comma-separated list of country codes specifying which feeds should be processed.  
  - If not provided, the function processes feeds from all available countries.
- **`include_only_unprocessed`** (optional): A boolean flag indicating whether to include only feeds that have not been processed yet.  
  - If set to `true`, only unprocessed feeds will be considered for reverse geolocation.
  - If set to `false`, all feeds will be processed, regardless of their processing status.
  - Default is `true`.

**Behavior:**  
The function publishes a message to the `reverse-geolocation` Pub/Sub topic for each non deprecated feed that matches the specified country codes.  
Note: The filtering is based on the user-provided location. However, a feed assigned to a specific country (e.g., Germany) may also contain stops from neighboring countries (e.g., France). The reverse geolocation process operates based on actual stop locations rather than predefined country assignments.

Once the message is published, it will trigger the [Pub/Sub function](#2-reverse-geolocation-triggered-functions).

---

## 2. Reverse Geolocation Triggered Functions

These functions initiate reverse geolocation processing based on external events:

- **`reverse_geolocation_storage_trigger`**: Triggered when a new dataset is uploaded to storage.
- **`reverse_geolocation_pubsub`**: Triggered when a message is published to the `reverse-geolocation` topic (e.g., from the [batch function](#1-reverse_geolocation_batch-function)).

### Parameters Extracted:
- `stable_id`: The stable ID of the `Gtfsfeed` entity.
- `dataset_id`: The ID of the latest `Gtfsdataset` related to the feed.
- `url`: The hosted URL of the dataset.

### Processing Steps:
1. The function downloads the `stops.txt` file and stores it in GCP storage. This offloads memory usage from the [`reverse_geolocation_process`](#3-reverse_geolocation_process-function) function.
2. A GCP Task is created to invoke [`reverse_geolocation_process`](#3-reverse_geolocation_process-function), ensuring better queue management and handling long-running tasks.

**Note:**  
Currently, storing `stops.txt` in GCP is a temporary implementation and may be migrated to a dedicated service in the future.

---

## 3. `reverse_geolocation_process` Function

This function performs the core reverse geolocation logic. It processes each stop in `stops.txt` and determines its geographic location.

### Parameters:
- `stable_id`: Identifies the GTFS feed.
- `dataset_id`: Identifies the dataset being processed.
- `stops_url`: URL of the `stops.txt` file.

### Processing Steps:

1. **Load Stop Data**  
   - The function reads `stops.txt` into a Pandas DataFrame, ensuring unique longitude-latitude combinations to avoid redundant processing.

2. **Update Dataset Bounding Box**  
   - The dataset's bounding box is updated using only the extreme coordinate values, forming a rectangular boundary.

3. **Check for Previously Processed Stops**  
   - Stops are matched against existing `Stop` entities in PostgreSQL using geographic coordinates (not `stop_id`).
   - Already processed stops retrieve their corresponding location aggregate instead of being reprocessed.
   - Every 100 processed stops, the database is updated to cache results, allowing failed jobs to resume efficiently.

4. **Reverse Geolocation Matching**  
   - Unmatched stops are processed using PostGIS queries to find overlapping administrative boundaries.
   - Each stop is assigned a **location aggregate**, which consists of multiple related `Geopolygon` entities (e.g., Canada, Quebec, and Montreal together).

5. **Store Results in PostgreSQL**  
   - Unique location aggregates are identified, and stop counts per location are recorded.
   - `Location` entities are created based on the extracted administrative hierarchy.
6. **GeoJSON Generation**  
   - The function creates a **GeoJSON file** containing location aggregates and their corresponding stop counts.  
   - The file is stored in **GCP Storage** following a consistent path format:  
     - **`<feed_stable_id>/geolocation.geojson`**  
   - This file always reflects the **latest dataset** results and is used for **location heatmap visualization on the front end**.
### Location Mapping:
- **`country_code` / `country`**: Taken from the `Geopolygon` with an ISO 3166-1 code.
- **`subdivision_name`**: Derived from the lowest administrative `Geopolygon` with an ISO 3166-2 code, but no ISO 3166-1 code.
- **`municipality`**: Determined from the `Geopolygon` with the highest administrative level.

**Limitations:**  
- The mapping is not guaranteed to be 100% accurate.  
- Some countries and administrative divisions may require manual adjustments in the future.

---

## Notes on Performance

- **Geospatial Queries**:  
  Processing each stop individually is not the most efficient approach, but it is necessary due to database capacity constraints when handling large feeds covering multiple countries.
  
- **Error Handling & Retries**:  
  - Failed tasks do not reprocess already cached stops, reducing redundant computations.  
  - Cloud Tasks ensure processing jobs are queued and executed within their time limits.

---

This logic ensures that GTFS feeds are correctly geolocated based on their actual stop locations rather than predefined user inputs. The resulting location aggregates can be used for various analyses and visualizations.


## Local Development

Local development of these functions should follow standard practices for GCP serverless functions. For general instructions on setting up the development environment, refer to the main [README.md](../README.md) file.