# Mobility Feed API - AI Coding Assistant Instructions

## Project Architecture

This is a **mobility data API service** built with FastAPI, serving open mobility data from across the world. The architecture follows a **code-generation pattern** with clear separation between generated and implementation code.

### Core Components

- **`api/`**: Main FastAPI application with spec-first development using OpenAPI Generator
- **`functions-python/`**: Google Cloud Functions for data processing (batch jobs, validation, analytics)
- **`web-app/`**: Frontend application
- **PostgreSQL + PostGIS**: Database with geospatial support for mobility data

### Key Generated vs Implementation Split

- **Generated code** (never edit): `api/src/feeds_gen/` and `api/src/shared/database_gen/`
- **Implementation code**: `api/src/feeds/impl/` contains actual business logic
- **Schema source**: `docs/DatabaseCatalogAPI.yaml` drives code generation

## Critical Development Workflows

### Initial Setup
```bash
# One-time OpenAPI setup
scripts/setup-openapi-generator.sh

# Install dependencies
cd api && pip3 install -r requirements.txt -r requirements_dev.txt

# Start local database
docker-compose --env-file ./config/.env.local up -d --force-recreate

# Generate API stubs (run after schema changes)
scripts/api-gen.sh
scripts/db-gen.sh
```

### Common Development Commands
```bash
# Start API server (includes Swagger UI at http://localhost:8080/docs/)
scripts/api-start.sh

# Run tests with coverage
scripts/api-tests.sh
# Run specific test file
scripts/api-tests.sh my_test_file.py

# Lint checks (Flake8 + Black)
scripts/lint-tests.sh

# Reset and populate local database
./scripts/docker-localdb-rebuild-data.sh --populate-db
# Include test datasets
./scripts/docker-localdb-rebuild-data.sh --populate-db --populate-test-data
```

## Project-Specific Patterns

### Error Handling Convention
- Use `shared.common.error_handling.InternalHTTPException` for internal errors
- Convert to FastAPI HTTPException using `feeds.impl.error_handling.convert_exception()`
- Store error messages as Finals in `api/src/feeds/impl/error_handling.py`
- Error responses follow: `{"details": "The error message"}`

### Database Patterns
- **Polymorphic inheritance**: `Feed` base class with `GtfsFeed`, `GbfsFeed`, `GtfsRTFeed` subclasses
- **SQLAlchemy ORM**: Models in `shared/database_gen/sqlacodegen_models.py` (generated)
- **Session management**: Use `@with_db_session` decorator for database operations
- **Unique IDs**: Generate with `generate_unique_id()` (36-char UUID4)

### API Implementation Structure
- Endpoints in `feeds/impl/*_api_impl.py` extend generated base classes from `feeds_gen/`
- Filter classes in `shared/feed_filters/` for query parameter handling
- Model implementations in `feeds/impl/models/` extend generated models

### Code Generation Workflow
1. Modify `docs/DatabaseCatalogAPI.yaml` for API changes
2. Run `scripts/api-gen.sh` to regenerate FastAPI stubs
3. Run `scripts/db-gen.sh` for database schema changes
4. Implement business logic in `feeds/impl/` classes

### Testing Patterns
- Tests use empty local test DB (reset with `--use-test-db` flag)
- Coverage reports in `scripts/coverage_reports/`
- Python path configured to `src/` in `pyproject.toml`

### Functions Architecture
- **Google Cloud Functions** in `functions-python/` for background processing
- Shared database models via `database_gen/` symlink
- Each function has its own deployment configuration
- Tasks include: validation reports, batch datasets, GBFS validation, BigQuery ingestion

### Authentication
- **OAuth2 Bearer tokens** for API access
- Refresh tokens from mobilitydatabase.org account
- Access tokens valid for 1 hour
- Test endpoint: `/v1/metadata` with Bearer token

## Integration Points

- **BigQuery**: Analytics data pipeline via `big_query_ingestion/` function  
- **PostGIS**: Geospatial queries for location-based feed filtering
- **Liquibase**: Database schema migrations in `liquibase/` directory
- **Docker**: Multi-service setup with PostgreSQL, test DB, and schema documentation

## File Exclusions for AI Context
- Skip `src/feeds_gen/*` and `src/shared/database_gen/*` (generated code)
- Skip `data/` and `data-test/` (database volumes)
- Skip `htmlcov/` (coverage reports)
- Black formatter excludes these paths automatically