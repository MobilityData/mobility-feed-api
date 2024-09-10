# Mobility Feed API

![Deploy Feeds API - QA](https://github.com/MobilityData/mobility-feed-api/workflows/Deploy%20Feeds%20API%20-%20QA/badge.svg?branch=main)
![Deploy Web App - QA](https://github.com/MobilityData/mobility-feed-api/actions/workflows/web-qa.yml/badge.svg?branch=main)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

The Mobility Feed API service a list of open mobility data sources from across the world. This repository is the effort the initial effort to convert the current [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs) in an API service.

# Work in Progress Status

Mobility Feed API is not released yet; any code or service hosted is considered as **Work in Progress**. For more information regarding the current Mobility Database Catalog, go to [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs).

## GBFS Feeds
The repository also includes GBFS feeds extracted from [`systems.csv`](https://github.com/MobilityData/gbfs/blob/master/systems.csv) in the [GBFS repository](https://github.com/MobilityData/gbfs). However, these feeds are not being served yet. The supported versions of these feeds are specified in the file [api/src/scripts/gbfs_utils/gbfs_versions.py](https://github.com/MobilityData/mobility-feed-api/blob/main/api/src/scripts/gbfs_utils/gbfs_versions.py).

# Authentication

To access the Mobility Feed API, users need to authenticate using an access token. Here is the step-by-step process to obtain and use an access token:

## Registering for an Account

1. **Sign up** at [mobilitydatabase.org](https://mobilitydatabase.org) to create an account.
2. Once registered, you can view your **refresh token** on the Account Details screen. This token is used to generate your access token.

## Generating an Access Token

You can generate an access token either via the UI on the website or using a `curl` command:

- **Via UI**: After logging in, navigate to the account page to generate or obtain your access token.
- **Via Command Line**:
  ```bash
  curl --location 'https://api.mobilitydatabase.org/v1/tokens' \
  --header 'Content-Type: application/json' \
  --data '{ "refresh_token": "[Your Refresh Token]" }'
  Replace `[Your Refresh Token]` with the refresh token obtained after registration.
  ```

## Using the Access Token

Once you have the access token, you can use it to make authenticated requests to the API.
For Testing Access:

```bash
curl --location 'https://api.mobilitydatabase.org/v1/metadata' \
--header 'Accept: application/json' \
--header 'Authorization: Bearer [Your Access Token]'
```

Replace `[Your Access Token]` with your actual access token.

### Via Swagger UI

You can also use the [Swagger UI](https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html) to make requests. Input your access token in the required field in the Swagger interface.

## Refreshing the Access Token

Access tokens are subject to expiration. Use your refresh token to generate a new access token when necessary.

# Local development

Folder `api` contains source code of the API implementation. This repository relies on [openapi-generator](https://openapi-generator.tech/) for spec-first development with [fastapi](https://openapi-generator.tech/docs/generators/python-fastapi) as the server stub generator. Generated files are placed in `src\feeds_gen`; this folder is ignored in git as it should not be modified. API's endpoint classes and methods are located in `src\feeds\impl`.

## Requirements.

The tested and recommended with the following versions:
- Python: `~=3.11`
- Docker: `>=20.10`

### External dependencies
 - docker
 - docker-compose
 - wget
 - Postgresql
 - sed

## Installation & Usage

- As a one-time step, download the `openapi-generator-cli.sh` script using:

```bash
scripts/setup-openapi-generator.sh
```

- Install dependencies

```bash
cd api
pip3 install -r requirements.txt
pip3 install -r requirements_dev.txt
```

- Generates an instance of the database locally using docker-compose

```bash
docker-compose --env-file ./config/.env.local  up -d --force-recreate
```

- Generates the api and database stubs on the first run and every time the schema changes

```bash
scripts/api-gen.sh
scripts/db-gen.sh
```

In case you modify the database schema, you can run
`docker-compose --env-file ./config/.env.local  up schemaspy -d --force-recreate` which will update your local instance of the database and the related schema documentation located in `docs/schemapy-dev/index.html`.

- Reset the local database and apply liquibase changes(Only on schema changes)
This command is very useful when switching branches that potentially have different DB schema definitions.
**All the data within the database will be lost**

```bash
./scripts/populate-db.sh <path to local sources.csv>
```

- Reset the local database and populate it with the catalog content`(Optional)`
  - Note: the wget command has to be available.
```bash
./scripts/docker-localdb-rebuild-data.sh --populate-db
```
Datasets are not part of the catalog. If you need to test or debug a feature that requires dataset entities use the following command:
```bash
./scripts/docker-localdb-rebuild-data.sh --populate-db --populate-test-data
```


- Run local API

```bash
scripts/api-start.sh
```

## Linter

This repository uses Flak8 and Black for code styling

To run linter checks:

```bash
scripts/lint-tests.sh
```

You can also use the pre-commit installed through [requirements_dev.txt](api%2Frequirements_dev.txt) with

```bash
pre-commit install
pre-commit run --all-files
```

## Local swagger documentation

To have access to the API's produced swagger documentation:

```bash
scripts/api-start.sh
```

and open your browser at `http://localhost:8080/docs/` to see the docs.

## IDE Python modules

If your Python's IDE is not able to resolve the python module; make sure the api/src folder is marked as `source` directory.

## Tests

To run the all tests:

```bash
scripts/api-tests.sh
```

To run a single test file:

```bash
scripts/api-tests.sh <my_test_filename>.py
```

Note: the tests rely on having an empty local test DB instance. If you have data in your local test DB, you can run the following command to reset the DB before running the tests
```bash
./scripts/docker-localdb-rebuild-data.sh --use-test-db
```


## Running with Docker

Before starting the docker container make sure the OpenApi generated files are present by running:

```bash
scripts/api-gen.sh
```

To run the server on a Docker container, please execute the following from the root directory:

```bash
(cd api && docker-compose up --build)
```

## API error responses

The API HTTP error responses follow the FastAPI structure. Example:

```
{
  "details": "The error message"
}
```

To simplify and standardize HTTP error responses use the helpers function located in [api/src/feeds/impl/error_handling.py](api/src/feeds/impl/error_handling.py). Also keep the error messages as Finals of the mentioned file, this will make it easier to locate and reuse error messages.
