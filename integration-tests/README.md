# Integration Tests for Mobility Feeds API

## Overview
This suite of integration tests validates the functionality and reliability of the Mobility Feeds API. It covers various scenarios to ensure accurate data retrieval and verify the API's response codes, content types, and payload structures.

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
./integration-tests.sh -u <API URL> -f <FILE PATH> [-c <CLASS NAMES>]
```

#### Options
- `-u` URL of the API to test against
- `-f` File path for the data file to be used in tests
- `-c` Optional, comma-separated list of test class names to include for targeted testing

### Example
```bash
./integration-tests.sh -u "http://0.0.0.0:8080" -f "/path/to/your/data_file.csv" -c "ClassName1,ClassName2"
```

This command runs the integration tests against the specified API URL and data file, filtering the tests to only include those from `ClassName1` and `ClassName2`.

## Test Configuration

### Optional Class Filtering
The `--include_classes` argument is optional. When specified, it filters the execution to only include tests from the provided comma-separated list of class names.

## Report
After test execution, a summary report is displayed, and a detailed log is saved to `integration_tests_log.html`.
