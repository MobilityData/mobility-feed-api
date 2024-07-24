import base64
import json
import os
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

import numpy as np
from faker import Faker
from geoalchemy2 import WKTElement

from extract_bb.src.main import (
    create_polygon_wkt_element,
    update_dataset_bounding_box,
    get_gtfs_feed_bounds,
    extract_bounding_box,
    extract_bounding_box_pubsub,
)
from test_utils.database_utils import default_db_url
from cloudevents.http import CloudEvent


faker = Faker()


class TestExtractBoundingBox(unittest.TestCase):
    def test_create_polygon_wkt_element(self):
        bounds = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        wkt_polygon: WKTElement = create_polygon_wkt_element(bounds)
        self.assertIsNotNone(wkt_polygon)

    def test_update_dataset_bounding_box(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none = MagicMock()
        update_dataset_bounding_box(session, faker.pystr(), MagicMock())
        session.commit.assert_called_once()

    def test_update_dataset_bounding_box_exception(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.one_or_none = None
        try:
            update_dataset_bounding_box(session, faker.pystr(), MagicMock())
            assert False
        except Exception:
            assert True

    @patch("gtfs_kit.read_feed")
    def test_get_gtfs_feed_bounds_exception(self, mock_gtfs_kit):
        mock_gtfs_kit.side_effect = Exception(faker.pystr())
        try:
            get_gtfs_feed_bounds(faker.url(), faker.pystr())
            assert False
        except Exception:
            assert True

    @patch("gtfs_kit.read_feed")
    def test_get_gtfs_feed_bounds(self, mock_gtfs_kit):
        expected_bounds = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        feed_mock = MagicMock()
        feed_mock.compute_bounds.return_value = expected_bounds
        mock_gtfs_kit.return_value = feed_mock
        bounds = get_gtfs_feed_bounds(faker.url(), faker.pystr())
        self.assertEqual(len(bounds), len(expected_bounds))
        for i in range(4):
            self.assertEqual(bounds[i], expected_bounds[i])

    @patch("extract_bb.src.main.Logger")
    def test_extract_bb_exception(self, _):
        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        # Creating attributes for CloudEvent, including required fields
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )

        try:
            extract_bounding_box_pubsub(cloud_event)
            self.assertTrue(False)
        except Exception:
            self.assertTrue(True)

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
        },
    )
    @patch("extract_bb.src.main.get_gtfs_feed_bounds")
    @patch("extract_bb.src.main.update_dataset_bounding_box")
    @patch("extract_bb.src.main.Logger")
    def test_extract_bb(self, _, update_bb_mock, get_gtfs_feed_bounds_mock):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )

        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )

        # Creating attributes for CloudEvent, including required fields
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )
        extract_bounding_box_pubsub(cloud_event)
        update_bb_mock.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
        },
    )
    @patch("extract_bb.src.main.get_gtfs_feed_bounds")
    @patch("extract_bb.src.main.update_dataset_bounding_box")
    @patch("extract_bb.src.main.Logger")
    def test_extract_bb_cloud_event(self, _, update_bb_mock, get_gtfs_feed_bounds_mock):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )

        file_name = faker.file_name()
        resource_name = (
            f"{faker.uri_path()}/{faker.pystr()}/{faker.pystr()}/{file_name}"
        )
        bucket_name = faker.pystr()

        data = {
            "protoPayload": {"resourceName": resource_name},
            "resource": {"labels": {"bucket_name": bucket_name}},
        }
        cloud_event = MagicMock()
        cloud_event.data = data

        extract_bounding_box(cloud_event)
        update_bb_mock.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
        },
    )
    @patch("extract_bb.src.main.get_gtfs_feed_bounds")
    @patch("extract_bb.src.main.update_dataset_bounding_box")
    @patch("extract_bb.src.main.Logger")
    def test_extract_bb_cloud_event_error(
        self, _, update_bb_mock, get_gtfs_feed_bounds_mock
    ):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )
        bucket_name = faker.pystr()

        # data with missing protoPayload
        data = {
            "resource": {"labels": {"bucket_name": bucket_name}},
        }
        cloud_event = MagicMock()
        cloud_event.data = data

        extract_bounding_box(cloud_event)
        update_bb_mock.assert_not_called()

    @mock.patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
        },
    )
    @patch("extract_bb.src.main.get_gtfs_feed_bounds")
    @patch("extract_bb.src.main.update_dataset_bounding_box")
    @patch("extract_bb.src.main.Logger")
    def test_extract_bb_exception_2(self, _, update_bb_mock, get_gtfs_feed_bounds_mock):
        get_gtfs_feed_bounds_mock.return_value = np.array(
            [faker.longitude(), faker.latitude(), faker.longitude(), faker.latitude()]
        )

        data = {
            "stable_id": faker.pystr(),
            "dataset_id": faker.pystr(),
            "url": faker.url(),
        }
        update_bb_mock.side_effect = Exception(faker.pystr())
        message_data = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )
        attributes = {
            "type": "com.example.someevent",
            "source": "https://example.com/event-source",
        }

        # Constructing the CloudEvent object
        cloud_event = CloudEvent(
            attributes=attributes, data={"message": {"data": message_data}}
        )

        try:
            extract_bounding_box_pubsub(cloud_event)
            assert False
        except Exception:
            assert True
