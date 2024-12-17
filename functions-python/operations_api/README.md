# Operations API
The Operations API is a function that exposes the operations API.
The operations API schema is located at ../../docs/OperationsAPI.yml.

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
docker compose --env-file ./config/.env.local up -d liquibase-test


# Local development
The local development of this function follows the same steps as the other functions. Please refer to the [README.md](../README.md) file for more information.