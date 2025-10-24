# Operations API
The Operations API is a Google Cloud Function exposing internal operations endpoints for the Mobility Database.
The Operations API OpenAPI schema lives at `../../docs/OperationsAPI.yaml`.

> Note: generated server stubs are created from the schema. Do not edit generated code under `src/feeds_gen/`; put implementation under `src/feeds_operations/impl/`.

# Function configuration
The function is configured using the following environment variables:
- `FEEDS_DATABASE_URL`: The URL of the feeds database.
- `GOOGLE_CLIENT_ID`: The Google client ID used for authentication.

# Useful scripts
- To locally execute a function use the following command:
```
./scripts/function-python-run.sh --function_name operations_api
```
- To locally create a distribution zip use the following command:
```
./scripts/function-python-build.sh --function_name operations_api
```
- Start local and test database
```
# from the repository root
docker compose --env-file ./config/.env.local up -d liquibase-test
```
- Update OperationsAPI OpenAPI components with Mobility Database Catalog API components
```
./scripts/api-operations-update-schema.sh
```


## Development process

Follow these steps when working on the Operations API:

1) Prerequisites
- Install OpenAPI Generator (one-time):
	```
	./scripts/setup-openapi-generator.sh
	```
- Ensure yq v4+ is available (required by the schema sync script). On macOS:
	```
	brew install yq
	```

2) Start databases locally (from repo root)
```
docker compose --env-file ./config/.env.local up -d liquibase-test
```

3) Sync Operations schema components from the Catalog API
- When the Catalog API schemas (`docs/DatabaseCatalogAPI.yaml`) change, update Operations to keep shared data models in sync while preserving operation-only ones:
	```
	./scripts/api-operations-update-schema.sh
	```
	This replaces `components.schemas` in `docs/OperationsAPI.yaml` with those from the Catalog, but preserves only schemas marked `x-operation: true` in Operations (non-operation dest-only schemas are removed).

4) Regenerate Operations API server stubs
```
./scripts/api-operations-gen.sh
```
Generated code goes to `functions-python/operations_api/src/feeds_gen/`.

5) Implement or update handlers
- Extend the generated base classes under `src/feeds_gen/` in your implementation files under:
	- `src/feeds_operations/impl/feeds_operations_impl.py`
	- `src/feeds_operations/impl/models/*`

6) Run locally
```
./scripts/function-python-run.sh --function_name operations_api
```

7) Run tests
- Using the repo test runner (recommended):
	```bash
	./scripts/api-tests.sh --folder functions-python/operations_api
	```

8) Build an artifact (zip) for deployment
```
./scripts/function-python-build.sh --function_name operations_api
```


# Local development
The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.