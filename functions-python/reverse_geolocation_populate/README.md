# Reverse Geolocation Populate

## Function Workflow

The `Reverse Geolocation Populate` function is a GCP Cloud Function that initializes and populates the database with administrative boundary polygons and metadata for specified country codes. It fetches data from OpenStreetMap (OSM) using BigQuery, processes it, and stores the results in the PostgreSQL database. The function queries the `bigquery-public-data.geo_openstreetmap.planet_features_multipolygons` dataset.

### Key Steps:

1. **Input Validation**  
   - Validates the `country_code` parameter in the HTTP request.  
   - Optionally accepts a list of administrative levels (`admin_levels`) to filter the data.

2. **Administrative Level Retrieval**  
   For the given `country_code`, the function retrieves:  
   - **Country administrative levels** (e.g., level 2) based on a boundary polygon with an `ISO3166-1` code matching the `country_code`.  
   - **Subdivision administrative levels** (e.g., levels 3–8) using boundary polygons with a geographic area within the country boundary and an `ISO3166-2` code where the prefix matches the `country_code`.  
   - **Locality administrative levels** (e.g., levels 3–8). If not provided in the request, they are determined by:  
     - The `locality_admin_levels.json` file, which maps country codes to default locality levels. This file should be kept up-to-date for efficiency.  
     - If no mapping exists, up to two levels higher than the highest subdivision level found (capped at level 8) are used.

3. **Data Fetching**  
   - Queries OSM data in BigQuery to retrieve boundary polygons and metadata for the specified administrative levels.

4. **Data Processing and Storage**  
   - Processes and stores data in the PostgreSQL database by creating `Geopolygon` entities with the following attributes:  
     - `osm_id`: OSM identifier of the boundary polygon.  
     - `admin_level`: Administrative level of the boundary polygon.  
     - `name`: The `name:en` tag if available; otherwise, the local `name` tag.  
     - `iso_3166_1`: The ISO 3166-1 code for country boundaries.  
     - `iso_3166_2`: The ISO 3166-2 code for subdivisions.  
     - `geometry`: The spatial geometry of the boundary polygon.

---

## Expected Behavior

### Input
The function expects an HTTP POST request with a JSON payload:

```json
{
  "country_code": "FR", 
  "admin_levels": "2,4,6"
}
```

- **`country_code`** (required): The ISO 3166-1 alpha-2 code of the country (e.g., `"FR"` for France).  
- **`admin_levels`** (optional): Comma-separated administrative levels (e.g., `"2,4,6"`). If not provided, levels are determined automatically.

### Output
- On success:  
  `Database initialized for <country_code>.`  
- On error:  
  Returns an error message with an appropriate `400` or `500` HTTP status code.

---

## Configuration

### Environment Variables
- **`FEEDS_DATABASE_URL`**: PostgreSQL connection string for storing geolocation data.

---

## Trigger

This Cloud Function is triggered by an HTTP POST request. It is typically called through the `reverse_geolocation_populate` workflow defined in the `reverse_geolocation_populate.yaml` file, which iterates over all ISO 3166-1 alpha-2 country codes.

---

## Local Development

Local development of these functions should follow standard practices for GCP serverless functions. For general instructions on setting up the development environment, refer to the main [README.md](../README.md) file.