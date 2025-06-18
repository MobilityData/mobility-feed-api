# coding: utf-8
import pytest
from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders

# Test the populate script. The assumption is that the populate script is called to populate the database for these
# tests, so we can check if certain behaviours are correct.


@pytest.mark.parametrize(
    "values",
    [
        {
            "feed_id": "mdb-40",
            "expected_official": True,
            "assert_fail_message": "mdb-40, changed is_official from TRUE to empty. Should retain True in the DB",
        },
        {
            "feed_id": "mdb-50",
            "expected_official": False,
            "assert_fail_message": "mdb-50, changed is_official from FALSE to empty. Should retain False in the DB",
        },
        {
            "feed_id": "mdb-1562",
            "expected_official": True,
            "assert_fail_message": "mdb-1562, changed is_official from FALSE to TRUE. Should change to True in the DB",
        },
        {
            "feed_id": "mdb-1563",
            "expected_official": False,
            "assert_fail_message": "mdb-1563, changed is_official from TRUE to FALSE. Should change to False in the DB",
        },
    ],
    ids=[
        "official_change_true_to_empty",
        "official_change_false_to_empty",
        "official_change_false_to_true",
        "official_change_true_to_false",
    ],
)
def test_is_official_overwrite(client: TestClient, values):
    """Test case for feeds_gtfs_id_get with a non-existent feed"""
    feed_id = values["feed_id"]
    expected_official = values["expected_official"]

    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=feed_id),
        headers=authHeaders,
    )

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["official"] is expected_official, values["assert_fail_message"]


def create_gbfs_systems_csv(file_path, data):
    """Helper function to create a GBFS systems.csv file."""
    import pandas as pd

    df = pd.DataFrame(data)
    # Ensure all required columns are present, even if empty
    required_columns = [
        "System ID",
        "Name",
        "URL",
        "Country Code",
        "Location",
        "Auto-Discovery URL",
        "Authentication Info URL",  # Added to prevent filtering by GBFSDatabasePopulateHelper.filter_data
    ]
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
    df.to_csv(file_path, index=False)


def test_deprecate_gbfs_feed(test_database, tmp_path):
    """
    Tests that GBFS feeds are correctly deprecated when they are removed from the systems.csv file.
    """
    from scripts.populate_db_gbfs import GBFSDatabasePopulateHelper
    from shared.database_gen.sqlacodegen_models import Gbfsfeed

    # Define feed data
    feed_a_id = "test_feed_a"
    feed_b_id = "test_feed_b"
    common_feed_data = {
        "Name": "Test Feed",
        "URL": "http://test.com",
        "Country Code": "US",
        "Location": "Test Location",
        "Auto-Discovery URL": "http://test.com/gbfs.json",
        "Authentication Info URL": None,  # Ensure it's not filtered out
    }
    initial_feeds_data = [
        {"System ID": feed_a_id, **common_feed_data, "Name": "Feed A"},
        {"System ID": feed_b_id, **common_feed_data, "Name": "Feed B"},
    ]

    # Create initial systems.csv
    initial_csv_path = tmp_path / "initial_systems.csv"
    create_gbfs_systems_csv(initial_csv_path, initial_feeds_data)

    # Run populate script with initial CSV
    populate_helper_initial = GBFSDatabasePopulateHelper([str(initial_csv_path)])
    # We pass fetch_url=False because these are dummy URLs and we don't want to try fetching them.
    # The comparison logic (which leads to deprecation) does not depend on fetched data.
    populate_helper_initial.initialize(trigger_downstream_tasks=False, fetch_url=False)

    # Verify initial state
    with test_database.start_db_session() as session:
        feed_a_initial = session.query(Gbfsfeed).filter(Gbfsfeed.stable_id == f"gbfs-{feed_a_id}").one_or_none()
        feed_b_initial = session.query(Gbfsfeed).filter(Gbfsfeed.stable_id == f"gbfs-{feed_b_id}").one_or_none()

        assert feed_a_initial is not None, "Feed A should exist after initial population."
        assert feed_a_initial.status != "deprecated", "Feed A should not be deprecated initially."
        assert feed_a_initial.operational_status == "published", "Feed A should be published initially."

        assert feed_b_initial is not None, "Feed B should exist after initial population."
        assert feed_b_initial.status != "deprecated", "Feed B should not be deprecated initially."
        assert feed_b_initial.operational_status == "published", "Feed B should be published initially."

    # Define data for updated CSV (Feed B removed)
    updated_feeds_data = [
        {"System ID": feed_a_id, **common_feed_data, "Name": "Feed A (updated)"}, # Name change to test updates too
    ]

    # Create updated systems.csv
    updated_csv_path = tmp_path / "updated_systems.csv"
    create_gbfs_systems_csv(updated_csv_path, updated_feeds_data)

    # Run populate script with updated CSV
    populate_helper_updated = GBFSDatabasePopulateHelper([str(updated_csv_path)])
    populate_helper_updated.initialize(trigger_downstream_tasks=False, fetch_url=False)

    # Verify final state
    with test_database.start_db_session() as session:
        feed_a_final = session.query(Gbfsfeed).filter(Gbfsfeed.stable_id == f"gbfs-{feed_a_id}").one_or_none()
        feed_b_final = session.query(Gbfsfeed).filter(Gbfsfeed.stable_id == f"gbfs-{feed_b_id}").one_or_none()

        assert feed_a_final is not None, "Feed A should still exist."
        assert feed_a_final.status != "deprecated", "Feed A should not be deprecated."
        # Check if name was updated
        assert feed_a_final.operator == "Feed A (updated)", "Feed A's name should have been updated."


        assert feed_b_final is not None, "Feed B should still exist (soft deleted)."
        assert feed_b_final.status == "deprecated", "Feed B should now be deprecated."
