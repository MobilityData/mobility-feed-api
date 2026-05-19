import os
import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    Gtfsfeed,
    Gtfsrealtimefeed,
)
from tasks.data_import.cal_itp.import_cal_itp_feeds import (
    import_cal_itp_handler,
    _get_license_url,
    _probe_head_format,
    _get_entity_types_from_resource,
    _is_bay_area_511,
    _is_customer_facing,
    _filter_cal_itp_records,
    _validate_required_cal_itp_fields,
    InvalidCalItpFeedError,
    CAL_ITP_SQL_QUERY_URL,
)
from test_shared.test_utils.database_utils import default_db_url


# ─────────────────────────────────────────────────────────────────────────────
# Fake HTTP doubles
# ─────────────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(
        self,
        body: Dict[str, Any] | None = None,
        status: int = 200,
        headers: Dict[str, str] | None = None,
    ):
        self._body = body or {}
        self.status_code = status
        self.headers = headers or {"Content-Type": "application/json; charset=utf-8"}

    def json(self):
        return self._body

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSessionOK:
    """
    Fake HTTP session for Cal-ITP:
      - GET on CAL_ITP_SQL_QUERY_URL returns 1 dataset record with:
          * 1 valid GTFS schedule resource
          * 1 trip_updates RT resource
      - HEAD on the GTFS URL returns a zip content-type
    """

    def get(self, url, timeout=60, headers=None):
        if url.startswith(CAL_ITP_SQL_QUERY_URL):
            return _FakeResponse(
                {
                    "result": {
                        "records": [
                            {
                                "service_source_record_id": "svc-1",
                                "service_name": "Transit Service One",
                                "organization_source_record_id": "org-1",
                                "organization_name": "CA Transit Agency",
                                "caltrans_district_name": "San Bernardino",
                                "schedule_source_record_id": "sched-1",
                                "schedule_gtfs_dataset_name": "Schedule Feed",
                                "schedule_dataset_url": "https://cal-itp.example/gtfs.zip",
                                "trip_updates_source_record_id": "tu-1",
                                "trip_updates_gtfs_dataset_name": "TU Feed",
                                "trip_updates_dataset_url": "https://cal-itp.example/tu.pb",
                                "vehicle_positions_source_record_id": None,
                                "vehicle_positions_gtfs_dataset_name": None,
                                "vehicle_positions_dataset_url": None,
                                "service_alerts_source_record_id": None,
                                "service_alerts_gtfs_dataset_name": None,
                                "service_alerts_dataset_url": None,
                                "regional_feed_type": None,
                                "gtfs_service_data_customer_facing": "true",
                            }
                        ]
                    }
                }
            )
        return _FakeResponse({}, status=404)

    def head(self, url, allow_redirects=True, timeout=15):
        # Treat the GTFS URL as a valid zip; everything else unknown
        if url == "https://cal-itp.example/gtfs.zip":
            return _FakeResponse(
                status=200,
                headers={"Content-Type": "application/zip"},
            )
        return _FakeResponse(
            status=200,
            headers={"Content-Type": "application/octet-stream"},
        )


class _FakeSessionError:
    """
    Fake HTTP session that always fails on GET.
    Used to test graceful handling of HTTP errors at the list-fetch level.
    """

    def get(self, url, timeout=60, headers=None):
        raise RuntimeError("network down")

    def head(self, url, allow_redirects=True, timeout=15):
        raise RuntimeError("network down")


# ─────────────────────────────────────────────────────────────────────────────
# Record-builder helper for filter tests
# ─────────────────────────────────────────────────────────────────────────────


def _make_record(
    service_id="svc-1",
    schedule_name=None,
    sa_name=None,
    tu_name=None,
    vp_name=None,
    regional_feed_type=None,
    customer_facing="true",
):
    return {
        "service_source_record_id": service_id,
        "schedule_gtfs_dataset_name": schedule_name,
        "service_alerts_gtfs_dataset_name": sa_name,
        "trip_updates_gtfs_dataset_name": tu_name,
        "vehicle_positions_gtfs_dataset_name": vp_name,
        "regional_feed_type": regional_feed_type,
        "gtfs_service_data_customer_facing": customer_facing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCalItpHelpers(unittest.TestCase):
    def test_get_license_url_mapping_and_unknown(self):
        # Known (case-insensitive)
        self.assertEqual(
            _get_license_url("odc-odbl"),
            "https://opendatacommons.org/licenses/odbl/1.0/",
        )
        self.assertEqual(
            _get_license_url("ODC-ODBL"),
            "https://opendatacommons.org/licenses/odbl/1.0/",
        )

        # Unknown and None
        self.assertIsNone(_get_license_url("some-other-license"))
        self.assertIsNone(_get_license_url(None))

    def test_probe_head_format_detects_zip_and_csv(self):
        sess = MagicMock()

        zip_resp = _FakeResponse(
            status=200, headers={"Content-Type": "application/zip"}
        )
        csv_resp = _FakeResponse(
            status=200, headers={"Content-Type": "text/csv; charset=utf-8"}
        )

        sess.head.side_effect = [zip_resp, csv_resp]

        status, ctype, detected = _probe_head_format(
            sess, "https://example.com/file.zip"
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/zip")
        self.assertEqual(detected, "zip")

        status2, ctype2, detected2 = _probe_head_format(
            sess, "https://example.com/file.csv"
        )
        self.assertEqual(status2, 200)
        self.assertTrue(ctype2.startswith("text/csv"))
        self.assertEqual(detected2, "csv")

    def test_probe_head_format_empty_url(self):
        sess = MagicMock()
        status, ctype, detected = _probe_head_format(sess, "")
        self.assertIsNone(status)
        self.assertIsNone(ctype)
        self.assertEqual(detected, "unknown")
        sess.head.assert_not_called()

    def test_probe_head_format_network_error(self):
        sess = MagicMock()
        sess.head.side_effect = RuntimeError("timeout")
        status, ctype, detected = _probe_head_format(
            sess, "https://example.com/file.zip"
        )
        self.assertIsNone(status)
        self.assertIsNone(ctype)
        self.assertEqual(detected, "unknown")

    def test_get_entity_types_from_resource_with_list(self):
        resource = {
            "entity_type": [
                "trip_updates",
                "vehicle_positions",
                "SERVICE_ALERTS",
                "something_else",
            ]
        }
        entity_types = _get_entity_types_from_resource(resource)
        self.assertEqual(sorted(entity_types), ["sa", "tu", "vp"])

    def test_get_entity_types_from_resource_empty(self):
        self.assertEqual(_get_entity_types_from_resource({}), [])
        self.assertEqual(_get_entity_types_from_resource({"entity_type": None}), [])
        self.assertEqual(_get_entity_types_from_resource({"entity_type": []}), [])

    def test_validate_required_fields_schedule(self):
        resource = {
            "service_source_record_id": "svc-1",
            "format": "gtfs",
            "schedule_source_record_id": "sched-1",
            "schedule_gtfs_dataset_name": "Schedule Feed",
            "schedule_dataset_url": "https://example.com/gtfs.zip",
        }
        service_id, res_format, res_id, res_name, res_url, feed_type = (
            _validate_required_cal_itp_fields(resource)
        )
        self.assertEqual(service_id, "svc-1")
        self.assertEqual(res_format, "gtfs")
        self.assertEqual(res_id, "sched-1")
        self.assertEqual(res_name, "Schedule Feed")
        self.assertEqual(res_url, "https://example.com/gtfs.zip")
        self.assertEqual(feed_type, "schedule")

    def test_validate_required_fields_rt_trip_updates(self):
        resource = {
            "service_source_record_id": "svc-1",
            "format": "gtfs_rt",
            "trip_updates_source_record_id": "tu-1",
            "trip_updates_gtfs_dataset_name": "TU Feed",
            "trip_updates_dataset_url": "https://example.com/tu.pb",
        }
        service_id, res_format, res_id, res_name, res_url, feed_type = (
            _validate_required_cal_itp_fields(resource)
        )
        self.assertEqual(service_id, "svc-1")
        self.assertEqual(res_format, "gtfs_rt")
        self.assertEqual(res_id, "tu-1")
        self.assertEqual(res_name, "TU Feed")
        self.assertEqual(res_url, "https://example.com/tu.pb")
        self.assertEqual(feed_type, "trip_updates")

    def test_validate_required_fields_rt_vehicle_positions(self):
        resource = {
            "service_source_record_id": "svc-2",
            "format": "gtfs_rt",
            "vehicle_positions_source_record_id": "vp-1",
            "vehicle_positions_gtfs_dataset_name": "VP Feed",
            "vehicle_positions_dataset_url": "https://example.com/vp.pb",
        }
        service_id, res_format, res_id, res_name, res_url, feed_type = (
            _validate_required_cal_itp_fields(resource)
        )
        self.assertEqual(service_id, "svc-2")
        self.assertEqual(res_format, "gtfs_rt")
        self.assertEqual(res_id, "vp-1")
        self.assertEqual(res_name, "VP Feed")
        self.assertEqual(res_url, "https://example.com/vp.pb")
        self.assertEqual(feed_type, "vehicle_positions")

    def test_validate_required_fields_unknown_format(self):
        resource = {
            "service_source_record_id": "svc-1",
            "format": "csv",
        }
        with self.assertRaises(InvalidCalItpFeedError):
            _validate_required_cal_itp_fields(resource)

    def test_validate_required_fields_rt_no_entity_type(self):
        resource = {
            "service_source_record_id": "svc-1",
            "format": "gtfs_rt",
            # No *_gtfs_dataset_name keys -> feed_type is None -> error
        }
        with self.assertRaises(InvalidCalItpFeedError):
            _validate_required_cal_itp_fields(resource)


# ─────────────────────────────────────────────────────────────────────────────
# Record filtering tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIsBayArea511(unittest.TestCase):
    def test_match_in_schedule_name(self):
        rec = _make_record(schedule_name="Bay Area 511 Regional GTFS")
        self.assertTrue(_is_bay_area_511(rec))

    def test_match_in_vehicle_positions_name(self):
        rec = _make_record(vp_name="Bay Area 511 Regional VP")
        self.assertTrue(_is_bay_area_511(rec))

    def test_no_match(self):
        rec = _make_record(schedule_name="Some Other Feed")
        self.assertFalse(_is_bay_area_511(rec))

    def test_none_values(self):
        rec = _make_record()
        self.assertFalse(_is_bay_area_511(rec))


class TestIsCustomerFacing(unittest.TestCase):
    def test_true_string(self):
        self.assertTrue(
            _is_customer_facing({"gtfs_service_data_customer_facing": "true"})
        )

    def test_yes_string(self):
        self.assertTrue(
            _is_customer_facing({"gtfs_service_data_customer_facing": "Yes"})
        )

    def test_false_string(self):
        self.assertFalse(
            _is_customer_facing({"gtfs_service_data_customer_facing": "false"})
        )

    def test_missing_key(self):
        self.assertFalse(_is_customer_facing({}))


class TestFilterCalItpRecords(unittest.TestCase):
    def test_bay_area_picks_highest_priority_type(self):
        """Regional Precursor Feed should win over Regional Subfeed."""
        records = [
            _make_record(
                service_id="bay-1",
                schedule_name="Bay Area 511 Regional GTFS",
                regional_feed_type="Regional Subfeed",
            ),
            _make_record(
                service_id="bay-1",
                schedule_name="Bay Area 511 Regional GTFS",
                regional_feed_type="Regional Precursor Feed",
            ),
            _make_record(
                service_id="bay-1",
                schedule_name="Bay Area 511 Regional GTFS",
                regional_feed_type="Combined Regional Feed",
            ),
        ]
        result = _filter_cal_itp_records(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["regional_feed_type"], "Regional Precursor Feed")

    def test_bay_area_subfeed_when_no_precursor(self):
        """Regional Subfeed wins when no Precursor exists."""
        records = [
            _make_record(
                service_id="bay-2",
                sa_name="Bay Area 511 Regional SA",
                regional_feed_type="Regional Subfeed",
            ),
            _make_record(
                service_id="bay-2",
                sa_name="Bay Area 511 Regional SA",
                regional_feed_type="Combined Regional Feed",
            ),
        ]
        result = _filter_cal_itp_records(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["regional_feed_type"], "Regional Subfeed")

    def test_bay_area_keeps_all_matching_highest_priority(self):
        """Multiple records with the same highest-priority type are all kept."""
        records = [
            _make_record(
                service_id="bay-3",
                tu_name="Bay Area 511 Regional TU",
                regional_feed_type="Regional Subfeed",
            ),
            _make_record(
                service_id="bay-3",
                tu_name="Bay Area 511 Regional TU",
                regional_feed_type="Regional Subfeed",
            ),
        ]
        result = _filter_cal_itp_records(records)
        self.assertEqual(len(result), 2)

    def test_bay_area_fallback_keeps_all(self):
        """If no priority type exists, keep all records as fallback."""
        records = [
            _make_record(
                service_id="bay-4",
                vp_name="Bay Area 511 Regional VP",
                regional_feed_type="Unknown Type",
            ),
            _make_record(
                service_id="bay-4",
                vp_name="Bay Area 511 Regional VP",
                regional_feed_type=None,
            ),
        ]
        result = _filter_cal_itp_records(records)
        self.assertEqual(len(result), 2)

    def test_non_bay_area_filters_customer_facing(self):
        """Non-Bay Area: only customer-facing records kept."""
        records = [
            _make_record(service_id="other-1", customer_facing="true"),
            _make_record(service_id="other-1", customer_facing="false"),
            _make_record(service_id="other-1", customer_facing="Yes"),
        ]
        result = _filter_cal_itp_records(records)
        self.assertEqual(len(result), 2)

    def test_mixed_services(self):
        """Bay Area and non-Bay Area services in the same batch."""
        records = [
            # Bay Area service with two types
            _make_record(
                service_id="bay-5",
                schedule_name="Bay Area 511 Regional GTFS",
                regional_feed_type="Combined Regional Feed",
            ),
            _make_record(
                service_id="bay-5",
                schedule_name="Bay Area 511 Regional GTFS",
                regional_feed_type="Regional Subfeed",
            ),
            # Non-Bay Area service
            _make_record(service_id="normal-1", customer_facing="true"),
            _make_record(service_id="normal-1", customer_facing="false"),
        ]
        result = _filter_cal_itp_records(records)
        # Bay Area: Regional Subfeed wins (1 record)
        # Normal: customer_facing=true kept (1 record)
        self.assertEqual(len(result), 2)
        bay_results = [
            r for r in result if r["service_source_record_id"] == "bay-5"
        ]
        self.assertEqual(len(bay_results), 1)
        self.assertEqual(bay_results[0]["regional_feed_type"], "Regional Subfeed")
        normal_results = [
            r for r in result if r["service_source_record_id"] == "normal-1"
        ]
        self.assertEqual(len(normal_results), 1)

    def test_empty_input(self):
        self.assertEqual(_filter_cal_itp_records([]), [])

    def test_bay_area_detected_from_any_name_column(self):
        """Bay Area marker in service_alerts column triggers regional filtering."""
        records = [
            _make_record(
                service_id="bay-6",
                sa_name="Bay Area 511 Regional SA",
                regional_feed_type="Combined Regional Feed",
                customer_facing="false",
            ),
        ]
        result = _filter_cal_itp_records(records)
        # Should use Bay Area path (not customer-facing path), so record is kept
        self.assertEqual(len(result), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Import tests (end-to-end with DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestImportCalItp(unittest.TestCase):
    @with_db_session(db_url=default_db_url)
    def test_import_creates_gtfs_and_rt(self, db_session: Session):
        """
        Happy-path test:
          - 1 dataset record with 1 GTFS schedule + 1 trip_updates RT
          - GTFS feed is created with stable_id cal_itp-svc-1-s
          - RT feed is created with stable_id cal_itp-svc-1-tu and linked to schedule
          - trigger_dataset_download is called once (for the new GTFS feed)
        """
        mock_trigger = MagicMock()

        with patch(
            "tasks.data_import.cal_itp.import_cal_itp_feeds.requests.Session",
            return_value=_FakeSessionOK(),
        ), patch(
            "tasks.data_import.cal_itp.import_cal_itp_feeds.REQUEST_TIMEOUT_S",
            0.01,
        ), patch(
            "tasks.data_import.cal_itp.import_cal_itp_feeds.trigger_dataset_download",
            mock_trigger,
        ), patch.dict(
            os.environ,
            {"COMMIT_BATCH_SIZE": "1", "ENV": "test"},
            clear=False,
        ):
            result = import_cal_itp_handler({"dry_run": False})

        # Summary: we expect 1 GTFS + 1 RT, processed 2 items.
        self.assertEqual(
            result,
            {
                "message": "Cal-ITP import executed successfully.",
                "created_gtfs": 1,
                "updated_gtfs": 0,
                "created_rt": 1,
                "total_processed_items": 2,
                "params": {"dry_run": False},
            },
        )

        # Check the schedule feed in DB
        sched: Optional[Gtfsfeed] = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.stable_id == "cal_itp-svc-1-s")
            .first()
        )
        self.assertIsNotNone(sched)
        sched = db_session.merge(sched)  # attach to session for relationships

        self.assertEqual(sched.feed_name, "Schedule Feed")
        self.assertEqual(sched.provider, "CA Transit Agency")
        self.assertEqual(sched.producer_url, "https://cal-itp.example/gtfs.zip")
        self.assertEqual(sched.operational_status, "published")

        # Check RT feed in DB and its links
        rt: Optional[Gtfsrealtimefeed] = (
            db_session.query(Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == "cal_itp-svc-1-tu")
            .first()
        )
        self.assertIsNotNone(rt)
        rt = db_session.merge(rt)

        self.assertEqual(rt.producer_url, "https://cal-itp.example/tu.pb")

        # RT should be linked to the schedule feed
        rt_sched_ids = [f.id for f in rt.gtfs_feeds]
        self.assertEqual(rt_sched_ids, [sched.id])

        # trigger_dataset_download should have been called once for the new GTFS feed
        mock_trigger.assert_called_once()
        called_args = mock_trigger.call_args[0]
        self.assertGreaterEqual(len(called_args), 2)
        detached_feed = called_args[0]
        merged_feed = db_session.merge(detached_feed)
        self.assertEqual(
            getattr(merged_feed, "stable_id", None), "cal_itp-svc-1-s"
        )
        self.assertIsInstance(called_args[1], str)  # execution_id

    @with_db_session(db_url=default_db_url)
    def test_import_http_failure_graceful(self, db_session: Session):
        """
        If the initial Cal-ITP datasets fetch fails, the handler should return
        a failure summary but not raise.
        """
        with patch(
            "tasks.data_import.cal_itp.import_cal_itp_feeds.requests.Session",
            return_value=_FakeSessionError(),
        ), patch(
            "tasks.data_import.cal_itp.import_cal_itp_feeds.REQUEST_TIMEOUT_S",
            0.01,
        ):
            out = import_cal_itp_handler({"dry_run": True})

        self.assertEqual(out["message"], "Failed to fetch Cal-ITP datasets.")
        self.assertIn("error", out)
        self.assertEqual(out["created_gtfs"], 0)
        self.assertEqual(out["updated_gtfs"], 0)
        self.assertEqual(out["created_rt"], 0)
        self.assertEqual(out["total_processed_items"], 0)


if __name__ == "__main__":
    unittest.main()
