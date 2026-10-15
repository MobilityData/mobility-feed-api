# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mobility Feed API — a FastAPI service that serves open mobility data (GTFS, GTFS-RT, GBFS feeds) from across the world, backing [mobilitydatabase.org](https://mobilitydatabase.org).

Three main runtime components:
- **`api/`** — the FastAPI service (Feeds API + User Service), spec-first via OpenAPI Generator.
- **`functions-python/`** — Google Cloud Functions (Gen2) for background processing: batch dataset downloads, GBFS/GTFS validation, BigQuery ingestion, notifications, reverse geolocation, etc.
- **PostgreSQL + PostGIS**, schema-migrated with **Liquibase** (`liquibase/`), geospatial support for location-based feed queries.

`infra/` holds Terraform for GCP infra (dev/qa/prod). `integration-tests/` is a separate Python suite that hits a *live deployed* API.

## Ground Rules

- **Never commit, push, or comment on PRs unless explicitly asked.** Prepare changes and leave them for review.
- **Preserve backward compatibility on the public surface.** `docs/DatabaseCatalogAPI.yaml` and `docs/UserServiceAPI.yaml` are consumed by real external clients (see README's access-token flow), and the Liquibase-managed DB schema is relied on by both the API and `functions-python/`. If a change would break an existing endpoint, response shape, or column, flag it explicitly instead of making it silently — don't assume a breaking change is fine just because tests still pass.

## Code Generation Split (critical)

This repo is spec-first. Never hand-edit generated code:
- `docs/DatabaseCatalogAPI.yaml` → generates `api/src/feeds_gen/` via `scripts/api-gen.sh` (config `scripts/gen-config.yaml`).
- `docs/UserServiceAPI.yaml` → generates `api/src/user_service_gen/` via `scripts/api-user-service-gen.sh` (config `scripts/gen-user-service-config.yaml`).
- `liquibase/changelog.xml` (+ `changes/`) → generates `api/src/shared/database_gen/sqlacodegen_models.py` (SQLAlchemy ORM) via `scripts/db-gen.sh`.
- `liquibase/changelog_user.xml` (+ `changes_user/`) → generates `api/src/shared/users_database_gen/` via `scripts/db-gen-user.sh`.

Workflow when changing the API schema or DB schema:
1. Edit the OpenAPI yaml (`docs/DatabaseCatalogAPI.yaml` or `docs/UserServiceAPI.yaml`) and/or add a Liquibase changeset.
2. Re-run the matching `scripts/*-gen.sh` script.
3. Implement/adjust business logic in `feeds/impl/` or `user_service/impl/` — never in the `_gen` folders.

Generated code (`feeds_gen/`, `user_service_gen/`, `shared/database_gen/`, `shared/users_database_gen/`) is excluded from black/flake8 (see `api/pyproject.toml`, `api/.flake8`) and should be treated as read-only.

## Common Commands

All commands assume repo root unless noted.

```bash
# One-time setup
scripts/setup-openapi-generator.sh
cd api && pip3 install -r requirements.txt -r requirements_dev.txt

# Local Postgres + Liquibase migrations
docker-compose --env-file ./config/.env.local up -d --force-recreate

# Re-init local env after checking out a branch: rebuilds main+test DBs, regenerates
# SQLAlchemy models, FastAPI stubs (Feeds + User Service + Operations API), and
# re-symlinks all functions' shared code. Prefer this over the individual steps below
# whenever the branch you just checked out changed the schema/spec files.
scripts/init-local-folder.sh                  # migrations only, no data
scripts/init-local-folder.sh --populate-db    # also pulls latest CSV from GCS into the main DB

# Regenerate stubs individually (after schema changes)
scripts/api-gen.sh                # Feeds API -> feeds_gen
scripts/api-user-service-gen.sh    # User Service API -> user_service_gen
scripts/db-gen.sh                  # DB schema -> database_gen
scripts/db-gen-user.sh             # User DB schema -> users_database_gen

# Reset local DB and (re)populate from a catalog sources.csv (destructive — wipes local DB)
./scripts/populate-db.sh <path to sources.csv>
./scripts/docker-localdb-rebuild-data.sh --populate-db
./scripts/docker-localdb-rebuild-data.sh --populate-db --populate-test-data   # also loads dataset entities
./scripts/docker-localdb-rebuild-data.sh --use-test-db                       # reset the empty test DB before running tests

# Run the API locally (Swagger UI at http://localhost:8080/docs/)
scripts/api-start.sh

# Lint (flake8 + black) across api/, functions-python/, integration-tests/
scripts/lint-tests.sh
pre-commit install && pre-commit run --all-files   # same check, runs lint-tests.sh as a hook

# Tests
scripts/api-tests.sh                                          # all `api/` tests + coverage (branch coverage must be >= 80%)
scripts/api-tests.sh --test_file <path/to/test_file.py>
scripts/api-tests.sh --folder functions-python                # every function under functions-python/ with a tests/ dir
scripts/api-tests.sh --folder functions-python/<function_name> # a single Cloud Function
scripts/api-tests.sh --html_report                             # also emit HTML coverage under scripts/coverage_reports

# Run/test a single Cloud Function locally
scripts/function-python-setup.sh --function_name <name>   # symlinks shared code (see below) into src/shared and tests/test_shared
scripts/function-python-run.sh --function_name <name>     # installs deps into a venv, runs via functions-framework --debug
scripts/function-python-build.sh --function_name <name>   # zips into .dist/ for deploy
```

`api-tests.sh` copies `config/.env.local` to `.env` before running, so local env vars match the docker-compose Postgres instance.

## Architecture Notes

### `api/src/` layout
- `feeds/impl/*_api_impl.py` — one impl class per resource (`FeedsApiImpl`, `DatasetsApiImpl`, `SearchApiImpl`, `MetadataApiImpl`, `LicensesApiImpl`), each subclassing a generated `Base*Api` from `feeds_gen`. `user_service/impl/*_api_impl.py` mirrors this for `UsersApiImpl`, `NotificationsApiImpl`, `SubscriptionsApiImpl`.
- `main.py` — a single FastAPI `app` mounts routers from **both** `feeds_gen` and `user_service_gen`; user-service routes are wrapped with `offload_blocking_routes()` (`utils/route_offload.py`) since those impls make blocking DB/Brevo HTTP calls. CORS is configured via raw Starlette middleware, not FastAPI's, due to a known FastAPI CORS bug — don't "simplify" this.
- `shared/` — code shared between the API and the Cloud Functions:
  - `database_gen/sqlacodegen_models.py` — generated ORM models; `Feed` is a polymorphic base with `GtfsFeed`, `GbfsFeed`, `GtfsRTFeed` subclasses.
  - `db_models/` — hand-written business-logic wrappers per entity (`feed_impl.py`, `gtfs_feed_impl.py`, etc.) layered over the generated models.
  - `database/` — `Database`, `with_db_session` decorator (use this for any DB-touching function), `users_database.py`.
  - `feed_filters/` — query-parameter filter builders per feed type.
  - `common/` — `error_handling.py`, `logging_utils.py`, `config_reader.py`, `gcp_utils.py`, `rate_limiter.py`, `brevo.py` (email), `entity_type_enum.py`.
  - `notifications/` — notification event service + Brevo sender.
- `middleware/request_context.py` — the de facto auth layer (no file is literally named `auth.py`): decodes the GCP IAP JWT (`x-goog-iap-jwt-assertion` header) via `decode_jwt`/`resolve_google_public_keys`, exposes `extract_user_id`, `is_user_email_restricted()`, and builds a `RequestContext`. `request_context_middleware.py` wires this in as ASGI middleware and logs API access.
- `scripts/` (under `api/src/`, distinct from repo-root `scripts/`) — DB population scripts (`populate_db*.py`), `gbfs_utils/` (also defines the supported GBFS versions map referenced from the README).

### Error handling convention
- Raise `shared.common.error_handling.InternalHTTPException` internally; convert to `HTTPException` via `feeds.impl.error_handling.convert_exception()`.
- Keep error message strings as `Final`s in `api/src/feeds/impl/error_handling.py` so they're reusable and easy to locate.
- Responses follow `{"details": "the error message"}`.

### `functions-python/` — Cloud Functions
Each function directory follows the same shape:
```
functions-python/<name>/
  src/main.py           # @functions_framework.http (or event-triggered) entry point
  src/shared/           # gitignored symlinks into api/src/shared/*, created by function-python-setup.sh
  tests/                # pytest; tests/test_shared/ is also symlinked (test_utils, etc.)
  function_config.json  # entry_point, runtime, memory, timeout, trigger, include_folders/include_api_folders, secrets, scaling
  requirements.txt / requirements_dev.txt
```
`function_config.json`'s `include_folders` (from `functions-python/`) and `include_api_folders` (from `api/src/shared/`) tell `function-python-setup.sh` what to symlink in — that's how functions share DB models and helpers with the API without a package dependency. Non-deployed shared support code (e.g. `helpers/`, `test_utils/`) uses `test_config.json` instead.

Functions have no direct interdependencies on each other; shared logic lives in `functions-python/helpers`, `functions-python/dataset_service`, `functions-python/test_utils`, or `api/src/shared/*`.

**Gotcha**: `functions-python/database_gen` at the top level is a stray, gitignored, stale copy — it is *not* the symlink target and can be out of sync with the real source of truth, `api/src/shared/database_gen/sqlacodegen_models.py`. Don't treat it as canonical.

### Database migrations
Liquibase changelogs live in `liquibase/` (`changelog.xml` + `changes/` for the main schema, `changelog_user.xml` + `changes_user/` for the user-service schema). `docker-compose.yaml` runs `liquibase`/`liquibase-test`/`liquibase-user`/`liquibase-user-test` services to apply them to local Postgres containers before `db-gen.sh`/`db-gen-user.sh` regenerate the SQLAlchemy models.

### Integration tests
`integration-tests/` is a separate suite that runs against a *live* API URL (not the local unit-test DB). New tests: add a class under `endpoints/` inheriting from the base `IntegrationTests` class, prefix methods with `test_`. Run via `./scripts/integration-tests.sh -u <API URL> -f <data file> [-c <ClassName1,ClassName2>]`.
