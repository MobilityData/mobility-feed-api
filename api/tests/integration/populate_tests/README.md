## Adding Tests to populate_tests

To add a test in `populate_tests`, you need to work with 3 `sources_test.csv` files in sequence:

1. **`tests/test_data/sources_test.csv`** - The base test data file. The data from this file is common to all tests in the tests directory (and subdirectories)
2. **`tests/integration/test_data/sources_test.csv`** - The data from this file is loaded in the DB on top of the previous content. Data from this file is common to all tests in the tests/integration directory (and subdirectories).
3. **`tests/integration/populate_tests/test_data/sources_test.csv`** - Similarly, the data of this file is loaded in the DB on top of the previous content.

This allows having common data for certain tests according to the directory structure.
Note also that data in a given sources_test.csv can overwrite data from the previous files (for example, to test an update scenario).

### Example

We want to test that for a realtime feed that has a certain static reference, we can change the reference and it will remove the original one and keep the new one (the current bug is that both feed references are kept in the DB)
1. `tests/test_data/integration/source_tests.csv` contains the rt feed 1562 with the static reference 40. After the file is loaded, that is what put in the DB.
2. `tests/test_data/integration/populate_tests/source_tests.csv` has a line for rt feed 1562 that modifies the static reference from 40 to 50. 
2. Write your test assertions in `test_populate.py` to validate the expected behavior. In our example, we want to check that the static reference for feed 1562 is 50, and not both 40 and 50. 
3. Run the populate script/tests