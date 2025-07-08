# Refresh Materialized View Cloud Function

This Google Cloud Function refreshes a materialized view using the `CONCURRENTLY` command to avoid table locks.

## Purpose

The function allows you to refresh PostgreSQL materialized views without blocking other database operations. It uses the `REFRESH MATERIALIZED VIEW CONCURRENTLY` command, which requires the materialized view to have a unique index.

## Usage

### HTTP Request

The function accepts both GET and POST requests:

#### GET Request

```
GET /refresh-materialized-view?view_name=your_view_name
```

#### POST Request

```
POST /refresh-materialized-view
Content-Type: application/json

{
  "view_name": "your_view_name"
}
```

### Parameters

- `view_name` (required): The name of the materialized view to refresh. Can include schema prefix (e.g., `schema_name.view_name`).

### Response

#### Success Response

```json
{
  "message": "Successfully refreshed materialized view: your_view_name"
}
```

#### Error Response

```json
{
  "error": "Error refreshing materialized view"
}
```

## Security

The function validates the view name to prevent SQL injection attacks. Only alphanumeric characters, underscores, and dots are allowed in view names.

## Requirements

- The materialized view must have a unique index for the `CONCURRENTLY` option to work
- The database user must have appropriate permissions to refresh materialized views

## Environment Variables

- `FEEDS_DATABASE_URL`: PostgreSQL database connection string

## Error Handling

The function handles various error scenarios:

- Missing view name parameter
- Invalid view name format
- Database connection issues
- View refresh failures

All errors are logged and returned with appropriate HTTP status codes.
