# Integration Tests for Mobility Feeds API

## Overview
This suite of integration tests validates the functionality and reliability of the Mobility Feeds API. It covers various scenarios to ensure accurate data retrieval and verify the API's response codes, content types, and payload structures.
The integration test suite sends _user-agent_ header as `MobilityData Feed API Integration Tests (Python {platform.python_version()})`, this is useful to identify the usage of this suite on the target platform.

## Setup

## Getting Started

### Prerequisites
- Python 3.x
- pip for installing Python packages
- Bash environment for running scripts

### Installation
Install the required Python libraries using pip:

```bash
pip install -r requirements.txt
```

## Adding New Tests

### Create Test Classes
Add new test classes to the `endpoints` directory. Each test class should inherit from the base `IntegrationTests` class for shared functionality or setup.

### Implement Test Methods
Implement test methods within your test class. Prefix each test method with `test_` to be automatically recognized and executed as part of the test suite. Use assertions to validate API responses.

### Register Test Classes
Ensure your test class is discoverable by adding it to the appropriate module within the `endpoints` package. The test runner dynamically imports all modules from this package.

## Running Tests

### Script Usage
Use the bash script with necessary arguments to specify the API URL, a refresh token for authentication, and the data file path. An optional argument allows filtering which test classes to execute.

```bash
export REFRESH_TOKEN="your_refresh_token"
./scripts/integration-tests.sh -u <API URL> -f <FILE PATH> [-c <CLASS NAMES>]
```

#### Options
- `-u` URL of the API to test against
- `-f` File path for the data file to be used in tests
- `-c` Optional, comma-separated list of test class names to include for targeted testing

### Example
```bash
./scripts/integration-tests.sh -u "http://0.0.0.0:8080" -f "/path/to/your/data_file.csv" -c "ClassName1,ClassName2"
```

This command runs the integration tests against the specified API URL and data file, filtering the tests to only include those from `ClassName1` and `ClassName2`.

### Where the tests run
- **Pull requests** (`integration-tests-pr.yml`): every endpoint of the Feeds API and the User Service, against an API started on the runner and a database seeded only from `integration-tests/fixtures`:
  - `sources.csv`: 24 GTFS and GTFS-RT feeds, the file the tests read with `-f`.
  - `gbfs_systems.csv` and `gbfs_versions.json`: the GBFS feeds.
  - `test_data.json`: licenses and rules, datasets, validation reports, availability checks, the Seal of Reliability, geopolygons, and the test user with its feature flags.

  `CatalogEndpointTests` and `UserServiceEndpointTests` expect the exact fixture values, so a fixture change usually needs a test change. The Garage and the Brevo-backed endpoints (announcements sync and opt-in) are not covered.
- **Deployed environments** (`integration-tests.yml`, after each DEV, QA and prod deployment): the metadata checks and `SmokeEndpointTests` only, with the few feeds in `fixtures/smoke_sources.csv`.

### Running Locally Against a Seeded Database
`scripts/integration-tests-local.sh` reproduces the PR workflow on your machine: it rebuilds the local test database (`postgres-test`) from the branch's Liquibase changelogs, regenerates the API code, seeds it from `integration-tests/fixtures`, starts the API against it and runs the tests. No token, GCP access or download is needed, and the main local database is not touched.

The test database (`./data-test`) is the one the unit tests use. After a run, reset it with `./scripts/docker-localdb-rebuild-data.sh --use-test-db` before running the unit tests.

```bash
./scripts/integration-tests-local.sh                          # full run
./scripts/integration-tests-local.sh --skip-seed --skip-gen   # rerun against the previously seeded database
./scripts/integration-tests-local.sh --skip-seed -c GBFSFeedsEndpointTests
```

Options: `--csv <path>` seeds and tests with another `sources.csv` instead of `fixtures/sources.csv`, `-c`/`-x` include or exclude test classes (the metadata classes, which need the version file the workflow writes, and `SmokeEndpointTests` are excluded by default). The API logs are kept in `.integration-tests/`.

## Test Configuration

### Optional Class Filtering
The `--include_classes` argument is optional. When specified, it filters the execution to only include tests from the provided comma-separated list of class names.

## Report
After test execution, a summary report is displayed, and a detailed log is saved to `integration_tests_log.html`.
