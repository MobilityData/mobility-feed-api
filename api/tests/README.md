# Mobility Feed API Tests

The tests in this directory are run with the [scripts/api-tests.sh](https://github.com/MobilityData/mobility-feed-api/blob/main/scripts/api-tests.sh) script using pytest.

pytest will recursively go down in all subdirectories and look for test files.

The code fills the test DB with data found in the test_date directory, namely [sources_test.csv](https://github.com/MobilityData/mobility-feed-api/blob/main/api/tests/test_data/sources_test.csv) and [extra_test_data.json](https://github.com/MobilityData/mobility-feed-api/blob/main/api/tests/test_data/extra_test_data.json).

Each subdirectory containing tests can also specify more data to add to the DB in their own test_data/sources_test.csv and test_data/extra_test_data.json.
Each directory containing tests should have a conftest.py file. It should be modeled after integration/conftest.py

The data in the DB is cleaned after test are run in each directories.

So, using the current integration and unittests directories as examples, here is what is done:

- Go down into the integration directory
- clean the test DB
- Load the test DB with data from tests/test_data
- Add the data from integration/test_data
- Run the tests in integration
- Go down into the unittests directory
- Clean the test DB
- Load the test DB with data from tests/test_data
- There's no unittests/test_data, so no data is added
- Run the tests in unittests



