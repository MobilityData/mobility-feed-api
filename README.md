# Mobility Feed API

![Deploy Feeds API - QA](https://github.com/MobilityData/mobility-feed-api/workflows/Deploy%20Feeds%20API%20-%20QA/badge.svg?branch=main)
![Deploy Web App - QA](https://github.com/MobilityData/mobility-feed-api/actions/workflows/web-app.yml/badge.svg?branch=main)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

The Mobility Feed API service a list of open mobility data sources from across the world. This repository is the effort the initial effort to convert the current [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs) in an API service.

# Work in Progress Status

Mobility Feed API is not released yet; any code or service hosted is considered as **Work in Progress**. For more information regarding the current Mobility Database Catalog, go to [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs).

# Viewing the API with Swagger.

Follow this [link](https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html).

# Local development

Folder `api` contains source code of the API implementation. This repository relies on [openapi-generator](https://openapi-generator.tech/) for spec-first development with [fastapi](https://openapi-generator.tech/docs/generators/python-fastapi) as the server stub generator. Generated files are placed in `src\feeds_gen`; this folder is ignored in git as it should not be modified. API's endpoint classes and methods are located in `src\feeds\impl`.

## Requirements.

Python <= 3.10

### Python 3.11 incompatibility notice

This project uses [sqlacodegen](https://github.com/agronholm/sqlacodegen) to generate ORM models. This project is also depending on [SqlAlchemy]https://www.sqlalchemy.org/. This combination od dependencies doesn't support **yet**(August 2023) Python 3.11 due to [bpo-45320](https://github.com/python/cpython/issues/89483).

Related issues:

- [bpo-45320](https://github.com/python/cpython/issues/89483)
- [sqlacodegen failing with Error: import name 'ArgSpec' from 'inspect'](https://github.com/agronholm/sqlacodegen/issues/239)
- [fix function name in codegen.py for python v3.11](https://github.com/agronholm/sqlacodegen/issues/274)

## Installation & Usage

- As a one time step, download the `openapi-generator-cli.sh` script using:

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
docker-compose --env-file ./config/.env.local up -d --force-recreate
```

- Generates the api and database stubs on first run and everytime the schema changes

```bash
scripts/api-gen.sh
scripts/db-gen.sh
```

In case you modify the database schema, you can run
`docker-compose --env-file ./config/.env.local  up schemaspy -d --force-recreate` which will update your local instance of the database and the related schema documentation located in `docs/schemapy-dev/index.html`.

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

## Running with Docker

Before starting the docker container make sure the OpenApi generated files are present by running:

```bash
scripts/api-gen.sh
```

To run the server on a Docker container, please execute the following from the root directory:

```bash
(cd api && docker-compose up --build)
```
