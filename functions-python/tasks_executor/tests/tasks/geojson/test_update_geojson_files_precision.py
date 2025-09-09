import os
import sys
import json
import types
import unittest
from unittest.mock import patch

from tasks.geojson.update_geojson_files_precision import (
    process_geojson,
    update_geojson_files_precision_handler,
    GEOLOCATION_FILENAME,
)


class _FakeBlobContext:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exists(self):
        return self.name in self.bucket.initial_blobs

    def download_as_text(self):
        return self.bucket.initial_blobs[self.name]


class _FakeUploadBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name

    def upload_from_string(self, content, content_type=None):
        # store as text for assertions
        self.bucket.uploaded[self.name] = content


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
    def __init__(self, bucket):
        self._bucket = bucket

    def Client(self):
        return FakeClient(self._bucket)

    # storage.Blob(...) used as a context manager in the handler
    def Blob(self, *, bucket, name):
        return _FakeBlobContext(bucket, name)


class TestUpdateGeojsonFilesPrecision(unittest.TestCase):
    def setUp(self):
        os.environ["DATASETS_BUCKET_NAME"] = "mock_bucket"

    def test_process_geojson_round_and_remove_osm_keys(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [12.3456789, -98.7654321]},
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
        self.assertEqual(out1["geometry"]["coordinates"], [round(1.23456789, 4), round(2.3456789, 4)])
        self.assertNotIn("osm", out1.get("properties", {}))

        lst = [feat]
        out2 = process_geojson(lst, precision=3)
        self.assertIsInstance(out2, list)
        self.assertEqual(out2[0]["geometry"]["coordinates"], [round(1.23456789, 3), round(2.3456789, 3)])

    @patch("tasks.geojson.update_geojson_files_precision.query_unprocessed_feeds")
    def test_handler_uploads_and_updates_feed_info(self, mock_query):
        geo = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [100.1234567, 0.9876543]},
                    "properties": {"id": "node/1", "keep": "x"},
                }
            ],
        }
        feed_stable_id = "feed_123"
        blob_name = f"{feed_stable_id}/{GEOLOCATION_FILENAME}"

        fake_bucket = FakeBucket(initial_blobs={blob_name: json.dumps(geo)})
        fake_storage = FakeStorageModule(fake_bucket)

        # create module objects for google and google.cloud and inject via sys.modules
        cloud_mod = types.ModuleType("google.cloud")
        # 'from google.cloud import storage' in handler will bind 'storage' to this attribute
        cloud_mod.storage = fake_storage
        google_mod = types.ModuleType("google")
        google_mod.cloud = cloud_mod

        fake_feed = types.SimpleNamespace(
            stable_id=feed_stable_id,
            geolocation_file_created_date=None,
            gtfsdatasets=[types.SimpleNamespace(bounding_box=types.SimpleNamespace(id="bbid"), downloaded_date=None)],
        )

        mock_query.return_value = [fake_feed]

        # fake db session
        class FakeExecResult:
            def scalar(self):
                return "NOW_TS"

        class FakeDBSession:
            def execute(self, q):
                return FakeExecResult()

            def commit(self):
                return None

        fake_db = FakeDBSession()

        payload = {"bucket_name": "any-bucket", "dry_run": False, "precision": 5, "limit": 1}

        # Inject modules into sys.modules for the duration of the handler call
        with patch.dict(sys.modules, {"google.cloud": cloud_mod, "google": google_mod}):
            # call wrapped handler to provide fake db_session
            update_geojson_files_precision_handler(payload, db_session=fake_db)

        # verify upload happened
        self.assertIn("geolocation.geojson", fake_bucket.uploaded)
        uploaded_text = fake_bucket.uploaded["geolocation.geojson"]
        uploaded_geo = json.loads(uploaded_text)
        coords = uploaded_geo.get("features")[0]["geometry"]["coordinates"]
        self.assertEqual(coords, [round(100.1234567, 5), round(0.9876543, 5)])

        # feed updated
        self.assertEqual(fake_feed.geolocation_file_created_date, "NOW_TS")


if __name__ == "__main__":
    unittest.main()
