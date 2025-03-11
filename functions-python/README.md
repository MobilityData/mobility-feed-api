# Python Functions

This folder contains Python functions. These functions should not have interdependencies. However, common code can be shared across multiple functions if they are in folders that don't contain functions.

# Python function folders
On each function folder, a file should contain all related configurations. Currently, there is no automated process to deploy all functions; this is why, to be able to deploy it the function should be added to the terraform scripts. In the future, we should automate the deployment.

# Function folder structure
Each function folder should contain the following files:
- `main.py`: The main file that contains the function code.
- `function_config.json`: The configuration of the function. This file is used to configure the cloud function on the terraform file.
- `requirements.txt`: The dependencies of the function.
- `requirements_dev.txt`: The dependencies of the function for local development.
- `tests`: The folder that contains the unit tests of the function.

# Function configuration(function_config.json)
The function configuration file contains the following properties:
- `name`: The name of the function.
- `description`: The description of the function.
- `entry_point`: The name of the function to be executed.
- `runtime`: The runtime of the function. Currently, only `python310` is supported.
- `timeout`: The timeout of the function in seconds. The default value is 60 seconds.
- `memory`: The memory of the function in MB. The default value is 128 MB.
- `trigger_http`: A boolean value that indicates if the function is triggered by an HTTP request. The default value is `false`.
- `include_folders`: A list of folders from functions-python to be included in the function zip. By default, the function zip will include all the files in the function folder.
- `include_api_folders`: A list of folders from the api folder to be included in the function zip. By default, the function zip will include all the files in the function folder.
- `secret_environment_variables`: A list of objects, each representing a secret environment variable. These are securely used within the function. Each object should include:
  - `key`: The name of the environment variable as used in the function, acting as the secret's identifier.
  - `secret` [Optional]: The specific GCP secret to be used. If omitted, a default secret name is generated using the environment prefix (`DEV`, `QA`, or `PROD`) followed by an underscore and the `key` value. For example, if `key` is `api_key` in the `DEV` environment, the default secret name is `DEV_api_key`.
- `ingress_settings`: The ingress settings of the function.
- `max_instance_request_concurrency`: The maximum number of concurrent requests allowed for a function instance.
- `max_instance_count`: The maximum number of function instances that can be created in response to a load.
- `min_instance_count`: The minimum number of function instances that can be created in response to a load.
- `available_cpu_count`: The number of CPU cores that are available to the function.
- `available_memory`: The amount of memory available to the function.

# Test configuration(test_config.json)
Some folders in functions-python are not destined to be deployed functions but are in support for other functions (e.g. helpers)m
Some of these folders contain tests and the `test_config.json` file is used to configure the tests.
The test configuration file contains the following properties:
- `include_folders`: A list of folders from functions-python used in the tests.
- `include_api_folders`: A list of folders from the api folder to be included in the tests.

# Local Setup

## Requirements
The requirements to run the functions locally might differ depending on the Google cloud dependencies. Please refer to each function to make sure all the requirements are met.

## Install the Google Cloud SDK
To be able to run the functions locally, the Google Cloud SDK should be installed. Please refer to the [Google Cloud SDK documentation](https://cloud.google.com/sdk/docs/install) for more information.

## Install the Google Cloud Emulators

```bash
gcloud components install cloud-datastore-emulator
```

- Install the Pub/Sub emulator
```bash
gcloud components install pubsub-emulator
```

# Useful scripts

The following sections uses `batch_datasets` as an example function. Replace `batch_datasets` with the function name you want to work with.

## Setting up an environment for editing and testing a function
- To setup an self-contained environment specific to a function, you can use the following command:
```
./scripts/function-python-setup.sh --function_name batch_datasets
```
This will create a `shared` folder in the function's folder (e.g. batch_datasets/src/shared) 
with symbolic links to the necessary packages to run the function locally.
It will also create a `test_shared` folder in the function's test folder (e.g. batch_datasets/tests/test_shared) 
e.g.:
   - functions-python/batch_datasets/src/shared
      - database_gen -> symlink to api/database_gen
      - dataset_service	-> symlink to functions-python/dataset_service
      - helpers -> symlink to functions-python/helpers
   - functions-python/batch_datasets/tests/test_shared
     - test_utils -> symlink to functions-python/test_utils

The python code should refer to these shared folders to import the necessary modules.
e.g. in `batch_datasets/src/main.py` we use the import:
```
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsdataset
```
and in `batch_datasets/tests/testbatch_datasets_main.py` we use the import:
```
from test_shared.test_utils.database_utils import get_testing_session, default_db_url
```
Notice the `shared` and `test_shared` prefixes in the import path.

- Also you can do a setup for all functions by running:
```
./scripts/function-python-setup.sh --all
```
- And remove the shared and test_shared folders by running:
```
./scripts/function-python-setup.sh --function_name batch_datasets --clean
```
or
```
./scripts/function-python-setup.sh --all --clean
```

## Creating a distribution zip

- To locally create a distribution zip use the following command:
```
./scripts/function-python-build.sh --function_name batch_datasets
```
or 
```
./scripts/function-python-build.sh --all
```
This script will create a .dist folder in the function's folder with the distribution zip and a build folder with the necessary files.
e.g. 
```
functions-python/batch_datasets/.dist/batch_datasets.zip
functions-python/batch_datasets/build/
```

## Executing a function
- To locally execute a function use the following command:
```
./scripts/function-python-run.sh --function_name batch_datasets
```
This will create a virtual environment specific to the function (i.e with the specific requirements.txt installed) 
and run the function locally using function-framework

## Start local and test database

```
docker compose --env-file ./config/.env.local up -d liquibase-test
```

# Local variables
To be able to set environment variables, add a file `.env.local` file to a function's folder and provide the name-value pair as follows:
```
export MY_AWESOME_KEY=MY_AWESOME_VALUE
```

# Unit tests
If a folder `tests` is added to a function's folder, the script `api-tests.sh` will execute the tests without any further configuration.
Make sure the testing database is running before executing the tests.
```
docker compose --env-file ./config/.env.local up -d liquibase-test
```

To run the tests:
```
scripts/api-tests.sh --folder functions-python/batch_datasets
```
or
```
scripts/api-tests.sh --folder functions-python
```

To run the tests and generate the html coverage report:
```
scripts/api-tests.sh --folder functions-python --html_report
```
_The coverage reports are located in `{project}/scripts/coverage_reports` as individual folder per function._

This will 
- run the `function-python-setup.sh` script for the function (ie create the `shared` and `test_shared` folders with symlinks) 
- Create a python virtual environment in the function folder, e.g.: `functions-python/batch_datasets/venv`
- Install the requirements.txt and requirements_dev.txt specific to the function
- Run the tests with coverage using installed virtual environment
- If there is any requirements missing you should be able to catch it at this point.

# Development using Pycharm

- You can open the function directly in Pycharm, e.g. open `functions-python/batch_datasets` directly.
- You need to set `batch_datasets/src` as the source root in Pycharm.
- You need to set the python interpreter to the one in the virtual environment created by 
the `function-python-build.sh` or `api-tests.sh` script, i.e. `functions-python/batch_datasets/venv`
- This will provide an environment the same or similar to the one used in deployment and allow you to catch issues early.
