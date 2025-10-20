import os
import sys
import json
import types
import unittest
from unittest.mock import patch

from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gbfsfeed, Gtfsfeed
from tasks.geojson.update_geojson_files_precision import (
    process_geojson,
    update_geojson_files_precision_handler,
    GEOLOCATION_FILENAME,
)
from test_shared.test_utils.database_utils import default_db_url


class _FakeBlobContext:
    def __init__(self, bucket, name, blob_exists=True):
        self.bucket = bucket
        self.name = name
        self.blob_exists = blob_exists

    def __enter__(self):
        return self

    def exists(self):
        return self.blob_exists

    def download_as_text(self):
        return self.bucket.initial_blobs[self.name]


class _FakeUploadBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name

    def upload_from_string(self, content, content_type=None):
        # store as text for assertions
        self.bucket.uploaded[self.name] = content

    def make_public(self):
        return


class FakeBucket:
    def __init__(self, initial_blobs=None):
        # mapping name -> text
        self.initial_blobs = initial_blobs or {}
        self.uploaded = {}

    def blob(self, name):
        # return an upload-capable blob
        return _FakeUploadBlob(self, name)


class FakeClient:
    def __init__(self, bucket):
        self._bucket = bucket

    def bucket(self, name):
        return self._bucket


class FakeStorageModule:
    def __init__(self, bucket, blob_exists=True):
        self._bucket = bucket
        self._blob_exists = blob_exists

    def Client(self):
        return FakeClient(self._bucket)

    # storage.Blob(...) used as a context manager in the handler
    def Blob(self, *, bucket, name):
        return _FakeBlobContext(bucket, name, self._blob_exists)


class TestUpdateGeojsonFilesPrecision(unittest.TestCase):
    def setUp(self):
        os.environ["DATASETS_BUCKET_NAME"] = "mock_bucket"

    def test_process_geojson_round_and_remove_osm_keys(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [12.3456789, -98.7654321],
                    },
                    "properties": {
                        "name": "A",
                        "osm_id": 123,
                        "@id": "node/1",
                        "id": "way/2",
                        "keep": "yes",
                    },
                }
            ],
        }

        out = process_geojson(fc, precision=5)
        self.assertIsNotNone(out)
        coords = out["features"][0]["geometry"]["coordinates"]
        self.assertEqual(coords, [round(12.3456789, 5), round(-98.7654321, 5)])

        props = out["features"][0]["properties"]
        self.assertNotIn("osm_id", props)
        self.assertNotIn("@id", props)
        self.assertNotIn("id", props)
        self.assertEqual(props.get("name"), "A")
        self.assertEqual(props.get("keep"), "yes")

    def test_process_geojson_single_feature_and_list_variants(self):
        feat = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1.23456789, 2.3456789]},
            "properties": {"id": "123", "osm": "should_remove"},
        }
        out1 = process_geojson(feat, precision=4)
        self.assertIsInstance(out1, dict)
        self.assertEqual(
            out1["geometry"]["coordinates"], [round(1.23456789, 4), round(2.3456789, 4)]
        )
        self.assertNotIn("osm", out1.get("properties", {}))

        lst = [feat]
        out2 = process_geojson(lst, precision=3)
        self.assertIsInstance(out2, list)
        self.assertEqual(
            out2[0]["geometry"]["coordinates"],
            [round(1.23456789, 3), round(2.3456789, 3)],
        )

    @with_db_session(db_url=default_db_url)
    def test_handler_uploads_and_updates_gtfs_feed_info(self, db_session: Session):
        geo = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [100.1234567, 0.9876543],
                    },
                    "properties": {"id": "node/1", "keep": "x"},
                }
            ],
        }
        testing_feed = db_session.query(Gtfsfeed).limit(1).first()
        feed_stable_id = testing_feed.stable_id
        blob_name = f"{feed_stable_id}/{GEOLOCATION_FILENAME}"

        fake_bucket = FakeBucket(initial_blobs={blob_name: json.dumps(geo)})
        fake_storage = FakeStorageModule(fake_bucket, blob_exists=True)

        # create module objects for google and google.cloud and inject via sys.modules
        cloud_mod = types.ModuleType("google.cloud")
        # 'from google.cloud import storage' in handler will bind 'storage' to this attribute
        cloud_mod.storage = fake_storage
        google_mod = types.ModuleType("google")
        google_mod.cloud = cloud_mod

        payload = {
            "bucket_name": "any-bucket",
            "dry_run": False,
            "precision": 5,
            "limit": 1,
        }

        # Inject modules into sys.modules for the duration of the handler call
        with patch.dict(sys.modules, {"google.cloud": cloud_mod, "google": google_mod}):
            # call wrapped handler to provide fake db_session
            result = update_geojson_files_precision_handler(
                payload, db_session=db_session
            )

        # verify upload happened
        self.assertIn(blob_name, fake_bucket.uploaded)
        uploaded_text = fake_bucket.uploaded[blob_name]
        uploaded_geo = json.loads(uploaded_text)
        coords = uploaded_geo.get("features")[0]["geometry"]["coordinates"]
        self.assertEqual(coords, [round(100.1234567, 5), round(0.9876543, 5)])

        self.assertEqual(
            {
                "total_processed_files": 1,
                "errors": [],
                "not_found_file": 0,
                "params": {
                    "dry_run": False,
                    "precision": 5,
                    "limit": 1,
                },
            },
            result,
        )
        # feed updated
        reloaded_testing_feed = (
            db_session.query(Gtfsfeed)
            .filter(Gtfsfeed.id.__eq__(testing_feed.id))
            .limit(1)
            .first()
        )
        self.assertIsNotNone(reloaded_testing_feed.geolocation_file_dataset_id)
        self.assertIsNotNone(reloaded_testing_feed.geolocation_file_created_date)

    @with_db_session(db_url=default_db_url)
    def test_handler_uploads_and_updates_gbfs_feed_info(self, db_session: Session):
        geo = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [100.1234567, 0.9876543],
                    },
                    "properties": {"id": "node/1", "keep": "x"},
                }
            ],
        }
        testing_gbfs_feed = db_session.query(Gbfsfeed).limit(1).first()
        self.assertIsNotNone(testing_gbfs_feed)
        feed_stable_id = testing_gbfs_feed.stable_id
        blob_name = f"{feed_stable_id}/{GEOLOCATION_FILENAME}"

        fake_bucket = FakeBucket(initial_blobs={blob_name: json.dumps(geo)})
        fake_storage = FakeStorageModule(fake_bucket, blob_exists=True)

        # create module objects for google and google.cloud and inject via sys.modules
        cloud_mod = types.ModuleType("google.cloud")
        # 'from google.cloud import storage' in handler will bind 'storage' to this attribute
        cloud_mod.storage = fake_storage
        google_mod = types.ModuleType("google")
        google_mod.cloud = cloud_mod

        payload = {
            "bucket_name": "any-bucket",
            "dry_run": False,
            "data_type": "gbfs",
            "precision": 5,
            "limit": 1,
        }

        # Inject modules into sys.modules for the duration of the handler call
        with patch.dict(sys.modules, {"google.cloud": cloud_mod, "google": google_mod}):
            # call wrapped handler to provide fake db_session
            result = update_geojson_files_precision_handler(
                payload, db_session=db_session
            )

        # verify upload happened
        self.assertIn(blob_name, fake_bucket.uploaded)
        uploaded_text = fake_bucket.uploaded[blob_name]
        uploaded_geo = json.loads(uploaded_text)
        coords = uploaded_geo.get("features")[0]["geometry"]["coordinates"]
        self.assertEqual(coords, [round(100.1234567, 5), round(0.9876543, 5)])

        self.assertEqual(
            {
                "total_processed_files": 1,
                "errors": [],
                "not_found_file": 0,
                "params": {
                    "dry_run": False,
                    "precision": 5,
                    "limit": 1,
                },
            },
            result,
        )
        # feed updated
        reloaded_testing_feed = (
            db_session.query(Gbfsfeed)
            .filter(Gbfsfeed.id.__eq__(testing_gbfs_feed.id))
            .limit(1)
            .first()
        )
        self.assertIsNotNone(reloaded_testing_feed.geolocation_file_created_date)

    @with_db_session(db_url=default_db_url)
    def test_handler_file_dont_exists(self, db_session: Session):
        fake_bucket = FakeBucket(initial_blobs={})
        fake_storage = FakeStorageModule(fake_bucket, blob_exists=False)

        # create module objects for google and google.cloud and inject via sys.modules
        cloud_mod = types.ModuleType("google.cloud")
        # 'from google.cloud import storage' in handler will bind 'storage' to this attribute
        cloud_mod.storage = fake_storage
        google_mod = types.ModuleType("google")
        google_mod.cloud = cloud_mod

        payload = {
            "bucket_name": "any-bucket",
            "dry_run": False,
            "precision": 5,
            "limit": 1,
        }

        # Inject modules into sys.modules for the duration of the handler call
        with patch.dict(sys.modules, {"google.cloud": cloud_mod, "google": google_mod}):
            # call wrapped handler to provide fake db_session
            result = update_geojson_files_precision_handler(
                payload, db_session=db_session
            )
            self.assertEqual(
                {
                    "total_processed_files": 0,
                    "errors": [],
                    "not_found_file": 1,
                    "params": {
                        "dry_run": False,
                        "precision": 5,
                        "limit": 1,
                    },
                },
                result,
            )

    @with_db_session(db_url=default_db_url)
    def test_handler_file_not_valid_file(self, db_session: Session):
        geo = "{}"
        testing_feed = db_session.query(Gtfsfeed).limit(1).first()
        feed_stable_id = testing_feed.stable_id
        blob_name = f"{feed_stable_id}/{GEOLOCATION_FILENAME}"

        fake_bucket = FakeBucket(initial_blobs={blob_name: geo})
        fake_storage = FakeStorageModule(fake_bucket, blob_exists=True)

        # create module objects for google and google.cloud and inject via sys.modules
        cloud_mod = types.ModuleType("google.cloud")
        # 'from google.cloud import storage' in handler will bind 'storage' to this attribute
        cloud_mod.storage = fake_storage
        google_mod = types.ModuleType("google")
        google_mod.cloud = cloud_mod

        payload = {
            "bucket_name": "any-bucket",
            "dry_run": False,
            "precision": 5,
            "limit": 1,
        }
        testing_feed = db_session.query(Gtfsfeed).limit(1).first()
        # Inject modules into sys.modules for the duration of the handler call
        with patch.dict(sys.modules, {"google.cloud": cloud_mod, "google": google_mod}):
            # call wrapped handler to provide fake db_session
            result = update_geojson_files_precision_handler(
                payload, db_session=db_session
            )
            self.assertEqual(
                {
                    "total_processed_files": 0,
                    "errors": [testing_feed.stable_id],
                    "not_found_file": 0,
                    "params": {
                        "dry_run": False,
                        "precision": 5,
                        "limit": 1,
                    },
                },
                result,
            )


if __name__ == "__main__":
    unittest.main()
