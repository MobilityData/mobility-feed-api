# Mobility Feed API

The Mobility Feed API service a list of open mobility data sources from across the world. This repository is the effort the initial effort to convert the current [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs) in an API service.

# Work in Progress Status

Mobility Feed API is not released yet; any code or service hosted is considered as **Work in Progress**. For more information regarding the current Mobility Database Catalog, go to [The Mobility Database Catalogs](https://github.com/MobilityData/mobility-database-catalogs).

# Viewing the API with Swagger. 

Follow this [link](https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html).

# Local development

Folder `api` contains source code of the API implementation.

## Requirements.

Python >= 3.7

## Installation & Usage

To run the server, please execute the following from the root directory:

```bash
cd api
pip3 install -r requirements.txt
cd src
uvicorn feeds.main:app --host 0.0.0.0 --port 8080
```

and open your browser at `http://localhost:8080/docs/` to see the docs.

## Running with Docker

To run the server on a Docker container, please execute the following from the root directory:

```bash
docker-compose up --build
```

## Tests

To run the tests:

```bash
cd api
pip3 install -r requirements_dev.txt
PYTHONPATH=src pytest tests
```
