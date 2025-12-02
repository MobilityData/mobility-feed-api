## Adding Tests to populate_tests

To add a test in `populate_tests`, you need to work with 3 `sources_test.csv` files in sequence:

1. **`tests/test_data/sources_test.csv`** - The base test data file
2. **`tests/integration/test_data/sources_test.csv`** - The intermediate file where data is accumulated
3. **`tests/integration/populate_tests/test_data/sources_test.csv`** - The final file where your changes are visible

### Workflow

When running `populate_tests`:
1. It starts from the base file (`tests/test_data/sources_test.csv`)
2. Adds/merges it to the integration test data (`tests/integration/test_data/sources_test.csv`)
3. You see your final changes in the populate_tests data (`tests/integration/populate_tests/test_data/sources_test.csv`)

### Example

If you want to test a new feed scenario (like the `gtfs realtime feed references` overwrite behavior in `test_populate.py`):
1. Modify the entry in `tests/test_data/sources_test.csv` with your test data
2. Write your test assertions in `test_populate.py` to validate the expected behavior
3. Run the populate script/tests
4. Verify the results appear correctly in `tests/integration/populate_tests/test_data/sources_test.csv`


---

This cascading approach ensures that base test data flows through the system and allows you to verify how the populate process handles data merging and updates.