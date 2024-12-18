# Reverse Geolocation Populate

## Function Workflow

The `Reverse Geolocation Populate` function is a GCP Cloud Function that initializes and populates the database with administrative boundary polygons and metadata for specified country codes. It fetches data from OpenStreetMap (OSM) using BigQuery, processes it, and stores the results in the Postgres database.

### Key Steps:
1. **Input Validation**:
   - The function validates the `country_code` parameter in the HTTP request.
   - Optionally, it accepts a list of administrative levels (`admin_levels`) to filter the data.

2. **Administrative Level Retrieval**:
   - For the given `country_code`, the function retrieves:
     - Country administrative levels (e.g., level 2).
     - Subdivision administrative levels (e.g., levels 3–8).

3. **Data Fetching**:
   - The function queries OSM data using BigQuery to retrieve boundary polygons and associated metadata for the specified administrative levels.

4. **Data Processing and Storage**:
   - The function processes the retrieved data and saves it into a PostgreSQL database, using the `geoalchemy2` library for spatial data.

5. **Error Handling**:
   - Any errors in data fetching or processing are logged and returned in the HTTP response.

---

## Expected Behavior

### Input
The function expects an HTTP POST request with a JSON payload containing:
- **`country_code`** (required): The ISO 3166-1 alpha-2 code of the country (e.g., `"FR"` for France).
- **`admin_levels`** (optional): A comma-separated list of administrative levels to process (e.g., `"2,4,6"`). If not provided, the function calculates levels automatically.

### Output
- If successful, the function initializes or updates the database with the administrative boundary data for the given country and returns: "Database initialized for <country_code>."
- If an error occurs, the function returns an appropriate error message and a `400` or `500` HTTP status code.

---

## Function Configuration

### Environment Variables
- **`FEEDS_DATABASE_URL`**: Connection string for the PostgreSQL database where geolocation data will be stored.
- **`reverse_geolocation_populate_url`**: URL of the Cloud Function for batch workflow calls.

### BigQuery Access
- The function queries the `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons` dataset. Ensure the function has the necessary permissions to access this dataset.

---

## Local Development

Local development of these functions should follow standard practices for GCP serverless functions. For general instructions on setting up the development environment, refer to the main [README.md](../README.md) file.