# Operations API
This folder contains the GCP Cloud Function that serve the operations API.

# Function configuration
The function is configured using the following environment variables:
- `FEEDS_DATABASE_URL`: The URL of the feeds database.

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
docker compose --env-file ./config/.env.local up -d liquibase-test
```

# Local development
The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.