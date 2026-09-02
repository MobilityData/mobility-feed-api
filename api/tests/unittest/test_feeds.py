import contextlib
import copy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl
from feeds_gen.models.gtfs_feed_continuous_coverage import GtfsFeedContinuousCoverage
from feeds_gen.models.gtfs_feed_continuous_coverage_file import GtfsFeedContinuousCoverageFile
from feeds_gen.models.service_date_window import ServiceDateWindow
from shared.common.continuous_coverage import COVERAGE_FILES
from shared.database_gen.sqlacodegen_models import GtfsFeedAvailabilityCheck as DbAvailabilityCheck
from shared.common.error_handling import InternalHTTPException, unknown_seal_criterion
from shared.db_models.feed_impl import FeedImpl
from shared.db_models.feed_reliability_report_impl import FeedReliabilityReportImpl
from shared.db_models.gtfs_feed_availability_check_impl import GtfsFeedAvailabilityCheckImpl
from shared.db_models.gtfs_feed_continuous_coverage_impl import GtfsFeedContinuousCoverageImpl
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Externalid,
    Gtfsdataset,
    Redirectingid,
    Gtfsfeed,
    Gtfsrealtimefeed,
    FeedReliabilitySeal,
    SealCriterion,
)
from shared.feed_filters.feed_filter import FeedFilter
from tests.test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID
from tests.test_utils.token import authHeaders

SEAL_NOW = datetime.now(timezone.utc)

target_feed = Feed(stable_id="test_target_id")
redirect_target_id = "test_target_id"
redirect_comment = "Some comment"
expected_redirect_response = {"target_id": redirect_target_id, "comment": redirect_comment}

mock_feed = Feed(
    stable_id="test_id",
    data_type="gtfs",
    status="active",
    seasonal=False,
    provider="test_provider",
    feed_name="test_feed_name",
    created_at=datetime.fromisoformat("2023-07-10T22:06:00+00:00"),
    note="test_note",
    feed_contact_email="test_feed_contact_email",
    producer_url="test_producer_url",
    authentication_type="1",
    authentication_info_url="test_authentication_info_url",
    api_key_parameter_name="test_api_key_parameter_name",
    license_url="test_license_url",
    externalids=[
        Externalid(
            associated_id="test_associated_id",
            source="test_source",
        )
    ],
    redirectingids=[
        Redirectingid(
            source_id="source_id",
            target_id="test_target_id",
            redirect_comment="Some comment",
            target=Feed(stable_id="test_target_id"),
        )
    ],
)

expected_feed_response = json.loads(
    FeedImpl(
        id="test_id",
        data_type="gtfs",
        created_at="2023-07-10T22:06:00Z",
        status="active",
        provider="test_provider",
        feed_name="test_feed_name",
        note="test_note",
        feed_contact_email="test_feed_contact_email",
        source_info={
            "authentication_type": 1,
            "authentication_info_url": "test_authentication_info_url",
            "api_key_parameter_name": "test_api_key_parameter_name",
            "license_url": "test_license_url",
            "producer_url": "test_producer_url",
        },
        external_ids=[{"external_id": "test_associated_id", "source": "test_source"}],
        related_links=[],
        redirects=[{"comment": "Some comment", "target_id": "test_target_id"}],
    ).model_dump_json()
)


def check_redirect(response: dict):
    assert (
        response["redirects"][0] == expected_redirect_response
    ), f'Response feed redirect was {response["redirects"][0]} instead of {expected_redirect_response}'


def test_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    # Build the chain of calls to mimic what is done in impl.feeds_api_impl.FeedsApiImpl.get_feeds
    mock_filter = mocker.patch.object(FeedFilter, "filter")
    mock_filter_limit = Mock()
    mock_filter_offset = Mock()
    mock_filter_order_by = Mock()
    mock_options = Mock()
    mock_filter.return_value.filter.return_value.order_by.return_value = mock_filter_order_by
    mock_filter_order_by.options.return_value = mock_options
    mock_options.limit.return_value = mock_filter_limit
    mock_filter_limit.offset.return_value = mock_filter_offset
    # Target is set to None as deep copy is failing for unknown reasons
    # At the end of the test, the target is set back to the original value
    mock_feed.redirectingids[0].target = None
    mock_feed_2 = copy.deepcopy(mock_feed)
    # Target is set back to the original value
    mock_feed.redirectingids[0].target = target_feed
    mock_feed_2.stable_id = "test_id_2"
    mock_feed_2.redirectingids[0].target = target_feed
    mock_filter_offset.all.return_value = [mock_feed, mock_feed_2]

    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feeds = response.json()
    assert len(response_feeds) == 2, f"Response feeds length was {len(response_feeds)} instead of 2"
    assert (
        response_feeds[0] == expected_feed_response
    ), f"Response feed was {response_feeds[0]} instead of {expected_feed_response}"
    assert (
        response_feeds[1]["id"] == "test_id_2"
    ), f"Response feed id was {response_feeds[1]['id']} instead of test_id_2"


def test_feed_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_filter = mocker.patch.object(FeedFilter, "filter")
    # FeedsApiImpl.get_feed() builds a query like
    # filter().outerjoin().options().filter().first(); mimic that so FeedImpl.from_orm
    # receives the actual Feed ORM instead of a MagicMock chain.
    chain = Mock()
    for method in ("filter", "outerjoin", "options", "order_by", "limit", "offset"):
        getattr(chain, method).return_value = chain
    chain.first.return_value = mock_feed
    mock_filter.return_value = chain

    response = client.request(
        "GET",
        "/v1/feeds/test_id",
        headers=authHeaders,
    )

    assert mock_filter.call_count == 1, (
        f"create_feed_filter() was called {mock_filter.call_count} times instead of 1 " f"time"
    )
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feed = response.json()

    assert (
        response_feed == expected_feed_response
    ), f"Response feed was {response_feed} instead of {expected_feed_response.dict()}"


def test_gtfs_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feeds
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        feed_mdb_10 = db.get_query_model(session, Gtfsfeed).filter(Gtfsfeed.stable_id == "mdb-10").first()
        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_feed = response.json()[0]
        assert_gtfs(feed_mdb_10, response_gtfs_feed)


def test_gtfs_feeds_get_no_bounding_box(client: TestClient, mocker):
    """
    Testing for issue #431 where latest_dataset would be None if bounding_box was None.
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_id")
    mock_latest_datasets = Gtfsdataset(stable_id="test_latest_dataset_id", hosted_url="test_hosted_url")

    mock_select.return_value = [
        [
            (
                mock_feed,
                None,  # redirect_id
                None,  # external_id
                None,  # redirect_comment
                mock_latest_datasets,
                None,  # Set the bounding_box to None
                None,  # locations
            )
        ]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
    )

    response_gtfs_feed = response.json()[0]
    assert response_gtfs_feed["latest_dataset"] is not None, "Response feed latest dataset was None"


def test_gtfs_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feed
    """
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{TEST_GTFS_FEED_STABLE_IDS[0]}",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        gtfs_feed = (
            db.get_query_model(session, Gtfsfeed).filter(Gtfsfeed.stable_id == TEST_GTFS_FEED_STABLE_IDS[0]).first()
        )
        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_feed = response.json()
        assert_gtfs(gtfs_feed, response_gtfs_feed)


def test_gtfs_rt_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feeds
    """
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        gtfs_rt_feed = (
            db.get_query_model(session, Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == TEST_GTFS_RT_FEED_STABLE_ID)
            .first()
        )

        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_rt_feed = response.json()[0]
        assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed)


def test_gtfs_rt_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feed
    """
    response = client.request(
        "GET",
        f"/v1/gtfs_rt_feeds/{TEST_GTFS_RT_FEED_STABLE_ID}",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_rt_feed = response.json()
    db = Database()
    with db.start_db_session() as session:
        gtfs_rt_feed = (
            db.get_query_model(session, Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == TEST_GTFS_RT_FEED_STABLE_ID)
            .first()
        )
        assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed)


def assert_gtfs(gtfs_feed, response_gtfs_feed):
    assert (
        response_gtfs_feed["id"] == gtfs_feed.stable_id
    ), f"Response feed id was {response_gtfs_feed['id']} instead of {gtfs_feed.stable_id}"
    assert (
        response_gtfs_feed["external_ids"][0]["external_id"]
        == sorted(gtfs_feed.externalids, key=lambda x: x.associated_id)[0].associated_id
    ), f'Response feed external id was {response_gtfs_feed["external_ids"][0]["external_id"]} \
        instead of {gtfs_feed.externalids[0].associated_id}'
    assert response_gtfs_feed["external_ids"][0]["source"] == gtfs_feed.externalids[0].source, (
        f'Response feed source was {response_gtfs_feed["external_ids"][0]["source"]} instead of '
        f"{gtfs_feed.externalids[0].source}"
    )
    assert (
        response_gtfs_feed["redirects"][0]["target_id"]
        == sorted(gtfs_feed.redirectingids, key=lambda x: x.target.stable_id)[0].target.stable_id
    ), (
        f'Response feed redirect was {response_gtfs_feed["redirects"][0]["target_id"]} instead of '
        f"{gtfs_feed.redirectingids[0].target.stable_id}"
    )
    assert (
        response_gtfs_feed["locations"][0]["country_code"] == gtfs_feed.locations[0].country_code
    ), f'Response feed country code was {response_gtfs_feed["locations"][0]["country_code"]} \
        instead of {gtfs_feed.locations[0].country_code}'
    assert (
        response_gtfs_feed["locations"][0]["subdivision_name"] == gtfs_feed.locations[0].subdivision_name
    ), f'Response feed subdivision name was {response_gtfs_feed["locations"][0]["subdivision_name"]} \
        instead of {gtfs_feed.locations[0].subdivision_name}'
    assert (
        response_gtfs_feed["locations"][0]["municipality"] == gtfs_feed.locations[0].municipality
    ), f'Response feed municipality was {response_gtfs_feed["locations"][0]["municipality"]} \
        instead of {gtfs_feed.locations[0].municipality}'
    # It seems the resulting are not always in the same order, so find the latest instead of using a hardcoded index
    # latest_dataset = next((dataset for dataset in gtfs_feed.gtfsdatasets if dataset.latest), None)
    if gtfs_feed.latest_dataset is not None:
        assert (
            response_gtfs_feed["latest_dataset"]["id"] == gtfs_feed.latest_dataset.stable_id
        ), f'Response feed latest dataset id was {response_gtfs_feed["latest_dataset"]["id"]} \
            instead of {gtfs_feed.latest_dataset.stable_id}'
    else:
        raise Exception("No latest dataset found")

    assert (
        response_gtfs_feed["latest_dataset"]["hosted_url"] == gtfs_feed.latest_dataset.hosted_url
    ), f'Response feed hosted url was {response_gtfs_feed["latest_dataset"]["hosted_url"]} \
        instead of test_hosted_url'
    assert response_gtfs_feed["latest_dataset"]["bounding_box"] is not None, "Response feed bounding_box was None"
    assert response_gtfs_feed["created_at"] is not None, "Response feed created_at was None"


def assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed):
    assert (
        response_gtfs_rt_feed["id"] == gtfs_rt_feed.stable_id
    ), f"Response feed id was {response_gtfs_rt_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_rt_feed["external_ids"][0]["external_id"]
        == sorted(gtfs_rt_feed.externalids, key=lambda x: x.associated_id)[0].associated_id
    ), f'Response feed external id was {response_gtfs_rt_feed["external_ids"][0]["external_id"]} \
        instead of {gtfs_rt_feed.externalids[0].associated_id}'
    assert response_gtfs_rt_feed["external_ids"][0]["source"] == gtfs_rt_feed.externalids[0].source, (
        f'Response feed source was {response_gtfs_rt_feed["external_ids"][0]["source"]} instead of '
        f"{gtfs_rt_feed.externalids[0].source}"
    )
    assert (
        response_gtfs_rt_feed["redirects"][0]["target_id"]
        == sorted(gtfs_rt_feed.redirectingids, key=lambda x: x.target_id)[0].target.stable_id
    ), (
        f'Response feed redirect was {response_gtfs_rt_feed["redirects"][0]["target_id"]} instead of '
        f"{gtfs_rt_feed.redirectingids[0].target.stable_id}"
    )
    assert response_gtfs_rt_feed["entity_types"][0] == gtfs_rt_feed.entitytypes[0].name, (
        f'Response feed entity type was {response_gtfs_rt_feed["entity_types"][0]}'
        f"instead of {gtfs_rt_feed.entitytypes[0].name}"
    )
    assert (
        response_gtfs_rt_feed["feed_references"][0] == gtfs_rt_feed.gtfs_feeds[0].stable_id
    ), f'response feed feed reference was {response_gtfs_rt_feed["feed_references"][0]} instead of test_feed_reference'
    assert response_gtfs_rt_feed["created_at"] is not None, "Response feed created_at was None"


# ---- Unit tests for availability endpoint helpers ----


def _make_db_check(**kwargs):
    """Create a minimal mock DB availability check."""
    defaults = {
        "checked_at": datetime(2025, 1, 10, 10, 0, 0),
        "success": True,
        "request_type": "http_head",
        "status_code": 200,
        "latency_ms": 150,
        "error_type": None,
    }
    defaults.update(kwargs)
    check = MagicMock(spec=DbAvailabilityCheck)
    for k, v in defaults.items():
        setattr(check, k, v)
    return check


def test_map_availability_check_http_head():
    """http_head maps to HEAD."""
    db_check = _make_db_check(request_type="http_head")
    result = GtfsFeedAvailabilityCheckImpl.from_orm(db_check)
    assert result.request_method == "HEAD"


def test_map_availability_check_http_get():
    """http_get maps to GET."""
    db_check = _make_db_check(request_type="http_get")
    result = GtfsFeedAvailabilityCheckImpl.from_orm(db_check)
    assert result.request_method == "GET"


def test_map_availability_check_latency_ms_cast_to_float():
    """latency_ms integer is cast to float."""
    db_check = _make_db_check(latency_ms=250)
    result = GtfsFeedAvailabilityCheckImpl.from_orm(db_check)
    assert result.latency_ms == 250.0
    assert isinstance(result.latency_ms, float)


def test_map_availability_check_latency_ms_none():
    """latency_ms None stays None."""
    db_check = _make_db_check(latency_ms=None)
    result = GtfsFeedAvailabilityCheckImpl.from_orm(db_check)
    assert result.latency_ms is None


def test_map_availability_check_failure():
    """Failed check maps success=False and preserves error_type."""
    db_check = _make_db_check(success=False, status_code=503, error_type="http_error")
    result = GtfsFeedAvailabilityCheckImpl.from_orm(db_check)
    assert result.success is False
    assert result.status_code == 503
    assert result.error_type == "http_error"


# ---- Unit tests for the Seal of Reliability endpoint ----


@contextlib.contextmanager
def _seal_rows(feed_stable_id: str, has_seal: bool, criteria: dict):
    """Seed a feed's seal tables for the duration of a test, then remove them.

    Writes through `__table__` (a Core insert) so the seal row's surrogate `id` falls back to its
    `gen_random_uuid()` default and the per-criterion rows go in without instantiating mapped objects.
    """
    db = Database()
    with db.start_db_session() as session:
        feed_id = session.query(Gtfsfeed).filter(Gtfsfeed.stable_id == feed_stable_id).first().id
        session.execute(
            FeedReliabilitySeal.__table__.insert().values(
                feed_id=feed_id,
                has_seal=has_seal,
                seal_earned_at=SEAL_NOW - timedelta(days=200),
                seal_lost_at=None if has_seal else SEAL_NOW - timedelta(days=20),
            )
        )
        for criterion, values in criteria.items():
            session.execute(SealCriterion.__table__.insert().values(feed_id=feed_id, criterion=criterion, **values))
        session.commit()
    try:
        yield
    finally:
        with db.start_db_session() as session:
            session.execute(SealCriterion.__table__.delete().where(SealCriterion.__table__.c.feed_id == feed_id))
            session.execute(
                FeedReliabilitySeal.__table__.delete().where(FeedReliabilitySeal.__table__.c.feed_id == feed_id)
            )
            session.commit()


def test_gtfs_feed_reliability_never_evaluated(client: TestClient):
    """A feed the nightly job has not reached returns a full report, not a 404."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{TEST_GTFS_FEED_STABLE_IDS[0]}/reliability",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    body = response.json()
    assert body["feed_id"] == TEST_GTFS_FEED_STABLE_IDS[0]
    assert body["has_seal"] is False
    assert body["seal_status"] == "never_evaluated", "no criterion row at all, so nothing was ever decided"
    assert body["on_probation"] is False
    assert len(body["criteria"]) == 6
    assert {criterion["status"] for criterion in body["criteria"]} == {"never_evaluated"}


def test_gtfs_feed_reliability_with_criteria(client: TestClient):
    """A feed with stored criteria reports each verdict, including the at-risk and probation states."""
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[1]
    criteria = {
        "official": {"observed_status": "pass", "confirmed_status": "pass", "evaluated_at": SEAL_NOW},
        "compliant": {
            "observed_status": "fail",
            "confirmed_status": "pass",
            "evaluated_at": SEAL_NOW,
            "first_observed_failure_at": SEAL_NOW - timedelta(days=2),
            "last_observed_failure_at": SEAL_NOW,
        },
        "available": {
            "observed_status": "pass",
            "confirmed_status": "pass",
            "evaluated_at": SEAL_NOW,
            "probation_start": SEAL_NOW - timedelta(days=10),
        },
    }
    with _seal_rows(feed_stable_id, has_seal=False, criteria=criteria):
        response = client.request(
            "GET",
            f"/v1/gtfs_feeds/{feed_stable_id}/reliability",
            headers=authHeaders,
        )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    body = response.json()
    by_name = {criterion["criterion"]: criterion for criterion in body["criteria"]}

    assert body["has_seal"] is False
    assert body["lost_at"] is not None
    assert by_name["official"]["status"] == "pass"
    # Failing its daily check but inside its 30-day grace window, so it still counts towards the
    # seal: `pass` plus the at-risk flag, rather than a confirmed loss.
    assert by_name["compliant"]["status"] == "pass"
    assert by_name["compliant"]["in_grace_period"] is True
    assert by_name["compliant"]["grace_period_ends_at"] is not None
    # Passing its check yet still serving probation, which is why the feed has no seal.
    assert by_name["available"]["status"] == "pass"
    assert by_name["available"]["on_probation"] is True
    assert by_name["available"]["probation_ends_at"] is not None
    assert by_name["stable"]["status"] == "never_evaluated"
    assert body["on_probation"] is True
    assert body["probation_ends_at"] == by_name["available"]["probation_ends_at"]


def test_gtfs_feed_reliability_not_found(client: TestClient):
    """An unknown feed id is a 404."""
    response = client.request(
        "GET",
        "/v1/gtfs_feeds/does-not-exist/reliability",
        headers=authHeaders,
    )

    assert response.status_code == 404, f"Response status code was {response.status_code} instead of 404"


def test_gtfs_feed_reliability_unknown_criterion_is_reported(client: TestClient, mocker):
    """A criterion this build does not know about surfaces as a 500 carrying the reason.

    The `seal_criterion_name` DB enum makes the value unstorable, so this is mocked at the impl:
    what is under test is that the InternalHTTPException raised under `shared/` is converted to an
    HTTPException instead of escaping as an opaque error.
    """
    mocker.patch.object(
        FeedReliabilityReportImpl,
        "from_orm",
        side_effect=InternalHTTPException(status_code=500, detail=unknown_seal_criterion.format("future_criterion")),
    )

    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{TEST_GTFS_FEED_STABLE_IDS[0]}/reliability",
        headers=authHeaders,
    )

    assert response.status_code == 500, f"Response status code was {response.status_code} instead of 500"
    assert "future_criterion" in response.json()["detail"]


def test_gtfs_feed_get_embeds_reliability_seal(client: TestClient):
    """The feed-detail response carries the seal summary, so the badge needs no second call."""
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[2]
    criteria = {"official": {"observed_status": "pass", "confirmed_status": "pass", "evaluated_at": SEAL_NOW}}
    with _seal_rows(feed_stable_id, has_seal=True, criteria=criteria):
        response = client.request("GET", f"/v1/gtfs_feeds/{feed_stable_id}", headers=authHeaders)

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    seal = response.json()["reliability_seal"]
    assert seal is not None
    assert seal["has_seal"] is True
    assert seal["on_probation"] is False
    assert seal["evaluated_at"] is not None


def test_gtfs_feed_reliability_reports_an_undecided_seal_as_unknown(client: TestClient):
    """`has_seal: false` covers three different things; `seal_status` is what separates them.

    A feed whose criteria have not all been judged is not a feed that was judged and failed, and a
    client has to be able to tell those apart. The status is derived from the criterion rows rather
    than stored, so one passing criterion beside one never-evaluated one is all it takes.
    """
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[2]
    criteria = {
        "official": {"observed_status": "pass", "confirmed_status": "pass", "evaluated_at": SEAL_NOW},
        "available": {"observed_status": "unknown", "confirmed_status": "never_evaluated", "evaluated_at": SEAL_NOW},
    }
    with _seal_rows(feed_stable_id, has_seal=False, criteria=criteria):
        response = client.request("GET", f"/v1/gtfs_feeds/{feed_stable_id}/reliability", headers=authHeaders)

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    body = response.json()
    assert body["has_seal"] is False
    assert body["seal_status"] == "unknown"


def test_gtfs_feed_reliability_reports_a_judged_seal_as_granted(client: TestClient):
    """The other side of the same coin: every criterion in scope judged, and all passing."""
    feed_stable_id = TEST_GTFS_FEED_STABLE_IDS[3]
    criteria = {
        criterion: {"observed_status": "pass", "confirmed_status": "pass", "evaluated_at": SEAL_NOW}
        for criterion in ("official", "stable", "available", "compliant", "fresh_coverage", "fresh_continuous")
    }
    with _seal_rows(feed_stable_id, has_seal=True, criteria=criteria):
        response = client.request("GET", f"/v1/gtfs_feeds/{feed_stable_id}/reliability", headers=authHeaders)

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    assert response.json()["seal_status"] == "granted"


def test_gtfs_feed_get_without_seal_reports_null(client: TestClient):
    """A feed that has never been evaluated reports a null summary rather than an empty object."""
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{TEST_GTFS_FEED_STABLE_IDS[0]}",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    assert response.json()["reliability_seal"] is None


# ---- Unit tests for the continuous coverage endpoint's `latest_*` root fields ----


def test_latest_continuous_coverage_no_latest_dataset():
    """A feed with no `latest_dataset_id` has no latest dataset to summarize."""
    feed = Gtfsfeed(latest_dataset_id=None)
    assert FeedsApiImpl._latest_continuous_coverage(feed, MagicMock()) is None


def test_latest_continuous_coverage_dataset_not_found():
    """`latest_dataset_id` pointing at a row the query can't find is treated as no latest dataset."""
    feed = Gtfsfeed(latest_dataset_id="dataset-latest")
    feed_datasets = MagicMock()
    feed_datasets.filter.return_value.options.return_value.first.return_value = None

    assert FeedsApiImpl._latest_continuous_coverage(feed, feed_datasets) is None


def test_latest_continuous_coverage_delegates_to_the_model_impl(mocker):
    """The snapshot is computed the same way as an `items[]` entry - `is_latest=True`, and measured
    against its own predecessor rather than whichever dataset happens to lead the requested page."""
    feed = Gtfsfeed(latest_dataset_id="dataset-latest")
    latest_dataset = Gtfsdataset(id="dataset-latest", stable_id="dataset-latest")
    previous_dataset = Gtfsdataset(id="dataset-previous", stable_id="dataset-previous")

    feed_datasets = MagicMock()
    feed_datasets.filter.return_value.options.return_value.first.return_value = latest_dataset
    mocker.patch.object(FeedsApiImpl, "_previous_dataset", return_value=previous_dataset)
    from_orm = mocker.patch.object(GtfsFeedContinuousCoverageImpl, "from_orm")

    result = FeedsApiImpl._latest_continuous_coverage(feed, feed_datasets)

    feed_datasets.filter.assert_called_once()
    from_orm.assert_called_once_with(latest_dataset, previous_dataset=previous_dataset, is_latest=True)
    assert result is from_orm.return_value


def test_get_gtfs_feed_continuous_coverage_maps_latest_fields(mocker):
    """The response's root `latest_*` fields are the `_latest_continuous_coverage` snapshot, not the
    first item of whatever page was requested."""
    feed = Gtfsfeed(latest_dataset_id="dataset-latest")
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    latest_coverage = GtfsFeedContinuousCoverage(
        dataset_id="dataset-latest",
        is_latest=True,
        coverage_window=ServiceDateWindow(start=date(2026, 9, 16), end=date(2027, 7, 28), days=316),
        coverage_window_source="service_dates",
        within_max_coverage_window=True,
        service_window=ServiceDateWindow(start=date(2026, 9, 16), end=date(2027, 7, 28), days=316),
        feed_info_window=None,
        feed_info_matches=None,
        overlap_days=15,
        gap_days=None,
        files=[GtfsFeedContinuousCoverageFile(name=name, present=True) for name in COVERAGE_FILES],
    )
    mocker.patch.object(FeedsApiImpl, "_latest_continuous_coverage", return_value=latest_coverage)

    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.count.return_value = 0
    empty_page = db_session.query.return_value.filter.return_value.order_by.return_value
    empty_page.offset.return_value.limit.return_value.options.return_value.all.return_value = []

    response = FeedsApiImpl().get_gtfs_feed_continuous_coverage(
        id="mdb-1",
        downloaded_after=None,
        downloaded_before=None,
        limit=20,
        offset=0,
        db_session=db_session,
    )

    assert response.latest_coverage_window.start == date(2026, 9, 16)
    assert response.latest_coverage_window_source == "service_dates"
    assert response.latest_within_max_coverage_window is True
    assert response.latest_service_window.end == date(2027, 7, 28)
    assert response.latest_feed_info_window is None
    assert response.latest_feed_info_matches is None
    assert response.latest_overlap_days == 15
    assert response.latest_gap_days is None
    assert [f.present for f in response.latest_files] == [True] * len(COVERAGE_FILES)


def test_get_gtfs_feed_continuous_coverage_no_latest_dataset(mocker):
    """A feed with no datasets still returns the required `latest_files` list, with every file
    reported absent rather than the field being omitted."""
    feed = Gtfsfeed(latest_dataset_id=None)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.count.return_value = 0
    empty_page = db_session.query.return_value.filter.return_value.order_by.return_value
    empty_page.offset.return_value.limit.return_value.options.return_value.all.return_value = []

    response = FeedsApiImpl().get_gtfs_feed_continuous_coverage(
        id="mdb-1",
        downloaded_after=None,
        downloaded_before=None,
        limit=20,
        offset=0,
        db_session=db_session,
    )

    assert response.latest_coverage_window is None
    assert [f.name for f in response.latest_files] == list(COVERAGE_FILES)
    assert [f.present for f in response.latest_files] == [False] * len(COVERAGE_FILES)


# ---- Regression tests: `datetime.fromisoformat` parses `Z`-suffixed dates directly on Python
# 3.11+ (https://github.com/python/cpython/issues/80010), so `downloaded_after`/`downloaded_before`/
# `_from`/`to` no longer need a `Z` -> `+00:00` rewrite before parsing. ----


def test_get_gtfs_feed_continuous_coverage_accepts_z_suffixed_dates(mocker):
    """A `Z`-suffixed `downloaded_after`/`downloaded_before` - what GTFS timestamps actually look
    like - must parse without raising, now that the manual rewrite is gone."""
    feed = Gtfsfeed(latest_dataset_id=None)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    feed_datasets = MagicMock()
    feed_datasets.filter.return_value = feed_datasets  # chained `.filter()` calls stay on one mock
    feed_datasets.count.return_value = 0
    feed_datasets.order_by.return_value.offset.return_value.limit.return_value.options.return_value.all.return_value = (
        []
    )

    db_session = MagicMock()
    db_session.query.return_value = feed_datasets

    response = FeedsApiImpl().get_gtfs_feed_continuous_coverage(
        id="mdb-1",
        downloaded_after="2024-01-01T00:00:00Z",
        downloaded_before="2024-06-01T00:00:00Z",
        limit=20,
        offset=0,
        db_session=db_session,
    )

    assert response.total == 0
    assert response.items == []


def test_get_gtfs_feed_availability_accepts_z_suffixed_dates(mocker):
    """Same guarantee for the availability endpoint's `_from`/`to` parameters."""
    feed = Gtfsfeed(id=1)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    query = MagicMock()
    query.filter.return_value = query
    query.count.return_value = 0
    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    db_session = MagicMock()
    db_session.query.return_value = query

    response = FeedsApiImpl().get_gtfs_feed_availability(
        id="mdb-1",
        _from="2024-01-01T00:00:00Z",
        to="2024-06-01T00:00:00Z",
        limit=20,
        offset=0,
        sort="desc",
        db_session=db_session,
    )

    assert response.total == 0
    assert response.checks == []


def test_get_gtfs_feed_datasets_accepts_z_suffixed_dates(mocker):
    """Same guarantee for the datasets endpoint, checked precisely: the `Z` suffix must resolve to
    UTC, not be silently dropped as a naive datetime."""
    feed = Gtfsfeed(id=1)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)
    mocker.patch.object(DatasetsApiImpl, "create_dataset_query", return_value=MagicMock())
    mocker.patch.object(DatasetsApiImpl, "get_datasets_gtfs", return_value=[])
    filter_cls = mocker.patch("feeds.impl.feeds_api_impl.GtfsDatasetFilter")

    result = FeedsApiImpl().get_gtfs_feed_datasets(
        gtfs_feed_id="mdb-1",
        latest=False,
        limit=20,
        offset=0,
        downloaded_after="2024-01-01T00:00:00Z",
        downloaded_before="2024-06-01T00:00:00Z",
        db_session=MagicMock(),
    )

    assert result == []
    _, kwargs = filter_cls.call_args
    assert kwargs["downloaded_at__gte"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert kwargs["downloaded_at__lte"] == datetime(2024, 6, 1, tzinfo=timezone.utc)


# ---- Regression tests: one date param carrying a UTC offset and the other not must not raise
# TypeError ("can't compare offset-naive and offset-aware datetimes") - both are equally valid per
# `valid_iso_date`, so `parse_iso_datetime` normalizes an offset-less value to UTC before any
# after/before comparison happens. ----


def test_get_gtfs_feed_continuous_coverage_mixed_naive_and_aware_dates(mocker):
    feed = Gtfsfeed(latest_dataset_id=None)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    feed_datasets = MagicMock()
    feed_datasets.filter.return_value = feed_datasets
    feed_datasets.count.return_value = 0
    feed_datasets.order_by.return_value.offset.return_value.limit.return_value.options.return_value.all.return_value = (
        []
    )

    db_session = MagicMock()
    db_session.query.return_value = feed_datasets

    response = FeedsApiImpl().get_gtfs_feed_continuous_coverage(
        id="mdb-1",
        downloaded_after="2024-01-01T00:00:00",
        downloaded_before="2024-06-01T00:00:00Z",
        limit=20,
        offset=0,
        db_session=db_session,
    )

    assert response.total == 0


def test_get_gtfs_feed_continuous_coverage_mixed_dates_still_validates_order(mocker):
    """Normalizing to UTC must not paper over a genuinely reversed range."""
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=Gtfsfeed(latest_dataset_id=None))

    with pytest.raises(HTTPException) as exc_info:
        FeedsApiImpl().get_gtfs_feed_continuous_coverage(
            id="mdb-1",
            downloaded_after="2024-06-01T00:00:00",
            downloaded_before="2024-01-01T00:00:00Z",
            limit=20,
            offset=0,
            db_session=MagicMock(),
        )
    assert exc_info.value.status_code == 422


def test_get_gtfs_feed_availability_mixed_naive_and_aware_dates(mocker):
    feed = Gtfsfeed(id=1)
    mocker.patch.object(FeedsApiImpl, "_get_gtfs_feed", return_value=feed)

    query = MagicMock()
    query.filter.return_value = query
    query.count.return_value = 0
    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    db_session = MagicMock()
    db_session.query.return_value = query

    response = FeedsApiImpl().get_gtfs_feed_availability(
        id="mdb-1",
        _from="2024-01-01T00:00:00",
        to="2024-06-01T00:00:00Z",
        limit=20,
        offset=0,
        sort="desc",
        db_session=db_session,
    )

    assert response.total == 0


# ---- Unit tests for `_predecessor`: a page row's positional neighbour is only a valid predecessor
# when both rows have a real `downloaded_at`. `_continuous_coverage_order`'s `nullslast` sorts
# undated datasets to the end of the page, so a positional neighbour next to one of them can't be
# trusted - `_predecessor` must fall back to `_previous_dataset` instead. ----


def test_predecessor_uses_positional_next_when_both_dated():
    dataset = Gtfsdataset(id="a", downloaded_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
    next_dataset = Gtfsdataset(id="b", downloaded_at=datetime(2024, 1, 1, tzinfo=timezone.utc))

    assert FeedsApiImpl._predecessor(MagicMock(), dataset, next_dataset) is next_dataset


def test_predecessor_falls_back_when_dataset_itself_is_undated(mocker):
    dataset = Gtfsdataset(id="a", downloaded_at=None)
    next_dataset = Gtfsdataset(id="b", downloaded_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    previous_dataset = mocker.patch.object(FeedsApiImpl, "_previous_dataset", return_value=None)

    result = FeedsApiImpl._predecessor(MagicMock(), dataset, next_dataset)

    assert result is None
    previous_dataset.assert_called_once()


def test_predecessor_falls_back_when_positional_next_is_undated(mocker):
    """A dated dataset immediately followed, in the page, by an undated one must not report that
    undated neighbour as its predecessor - we don't know when it was actually downloaded."""
    dataset = Gtfsdataset(id="a", downloaded_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
    next_dataset = Gtfsdataset(id="b", downloaded_at=None)
    real_previous = Gtfsdataset(id="c", downloaded_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    previous_dataset = mocker.patch.object(FeedsApiImpl, "_previous_dataset", return_value=real_previous)

    result = FeedsApiImpl._predecessor(MagicMock(), dataset, next_dataset)

    assert result is real_previous
    previous_dataset.assert_called_once()


def test_predecessor_falls_back_for_the_last_page_row(mocker):
    """No positional neighbour at all (the page's last row) - unchanged from before this fix."""
    dataset = Gtfsdataset(id="a", downloaded_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
    previous_dataset = mocker.patch.object(FeedsApiImpl, "_previous_dataset", return_value=None)

    result = FeedsApiImpl._predecessor(MagicMock(), dataset, None)

    assert result is None
    previous_dataset.assert_called_once()
