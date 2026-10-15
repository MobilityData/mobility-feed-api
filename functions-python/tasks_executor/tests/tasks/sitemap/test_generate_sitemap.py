#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Unit tests for the sitemap rendering and lastmod rules (no database)."""

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from tasks.sitemap.generate_sitemap import (
    LASTMOD_FLOOR,
    PRIORITY,
    SitemapEntry,
    build_sitemap_xml,
    resolve_lastmod,
    to_utc_date,
    upload_sitemap,
)

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class TestToUtcDate(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(to_utc_date(None))

    def test_date_passes_through(self):
        self.assertEqual(to_utc_date(date(2026, 5, 1)), date(2026, 5, 1))

    def test_naive_datetime_read_as_utc(self):
        self.assertEqual(
            to_utc_date(datetime(2026, 5, 1, 23, 30)),
            date(2026, 5, 1),
        )

    def test_aware_datetime_converted_to_utc_before_taking_the_date(self):
        """23:30 on May 1st at UTC-6 is already May 2nd in UTC."""
        tz_minus_six = timezone(timedelta(hours=-6))
        self.assertEqual(
            to_utc_date(datetime(2026, 5, 1, 23, 30, tzinfo=tz_minus_six)),
            date(2026, 5, 2),
        )


class TestResolveLastmod(unittest.TestCase):
    def test_no_candidates_returns_the_floor(self):
        self.assertEqual(resolve_lastmod(), LASTMOD_FLOOR)

    def test_all_none_returns_the_floor(self):
        self.assertEqual(resolve_lastmod(None, None), LASTMOD_FLOOR)

    def test_candidate_older_than_the_floor_is_raised_to_the_floor(self):
        older = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(resolve_lastmod(older), LASTMOD_FLOOR)

    def test_candidate_newer_than_the_floor_wins(self):
        newer = datetime(2026, 7, 4, tzinfo=timezone.utc)
        self.assertEqual(resolve_lastmod(newer), date(2026, 7, 4))

    def test_most_recent_of_several_candidates_wins(self):
        self.assertEqual(
            resolve_lastmod(
                datetime(2026, 4, 1, tzinfo=timezone.utc),
                None,
                datetime(2026, 9, 9, tzinfo=timezone.utc),
                datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
            date(2026, 9, 9),
        )

    def test_explicit_floor_is_honoured(self):
        self.assertEqual(
            resolve_lastmod(None, floor=date(2026, 1, 1)), date(2026, 1, 1)
        )


class TestSitemapEntry(unittest.TestCase):
    def test_loc_uses_the_data_type_and_stable_id(self):
        entry = SitemapEntry("gtfs_rt", "mdb-3486", LASTMOD_FLOOR)
        self.assertEqual(
            entry.loc("https://mobilitydatabase.org"),
            "https://mobilitydatabase.org/feeds/gtfs_rt/mdb-3486",
        )

    def test_loc_does_not_double_up_a_trailing_slash(self):
        entry = SitemapEntry("gbfs", "gbfs-dott-presov", LASTMOD_FLOOR)
        self.assertEqual(
            entry.loc("https://mobilitydatabase.org/"),
            "https://mobilitydatabase.org/feeds/gbfs/gbfs-dott-presov",
        )


class TestBuildSitemapXml(unittest.TestCase):
    entries = [
        SitemapEntry("gtfs", "mdb-460", date(2026, 3, 5)),
        SitemapEntry("gtfs_rt", "mdb-3486", date(2026, 7, 1)),
        SitemapEntry("gbfs", "gbfs-donkey_aarhus", date(2026, 6, 21)),
    ]

    def render(self):
        return build_sitemap_xml(self.entries, "https://mobilitydatabase.org")

    def test_output_is_well_formed_xml_in_the_sitemap_namespace(self):
        root = ElementTree.fromstring(self.render())
        self.assertEqual(root.tag, f"{SITEMAP_NS}urlset")

    def test_one_url_element_per_entry_in_order(self):
        root = ElementTree.fromstring(self.render())
        locs = [url.find(f"{SITEMAP_NS}loc").text for url in root]
        self.assertEqual(
            locs,
            [
                "https://mobilitydatabase.org/feeds/gtfs/mdb-460",
                "https://mobilitydatabase.org/feeds/gtfs_rt/mdb-3486",
                "https://mobilitydatabase.org/feeds/gbfs/gbfs-donkey_aarhus",
            ],
        )

    def test_lastmod_is_rendered_as_an_iso_date(self):
        root = ElementTree.fromstring(self.render())
        lastmods = [url.find(f"{SITEMAP_NS}lastmod").text for url in root]
        self.assertEqual(lastmods, ["2026-03-05", "2026-07-01", "2026-06-21"])

    def test_every_priority_is_flat(self):
        root = ElementTree.fromstring(self.render())
        priorities = {url.find(f"{SITEMAP_NS}priority").text for url in root}
        self.assertEqual(priorities, {PRIORITY})

    def test_changefreq_is_never_emitted(self):
        self.assertNotIn("changefreq", self.render())

    def test_empty_entry_list_still_renders_a_valid_urlset(self):
        root = ElementTree.fromstring(build_sitemap_xml([], "https://example.org"))
        self.assertEqual(root.tag, f"{SITEMAP_NS}urlset")
        self.assertEqual(len(root), 0)

    def test_stable_ids_needing_escaping_are_escaped(self):
        xml = build_sitemap_xml(
            [SitemapEntry("gtfs", "weird&id", LASTMOD_FLOOR)], "https://example.org"
        )
        self.assertIn("weird&amp;id", xml)
        root = ElementTree.fromstring(xml)
        self.assertEqual(
            root[0].find(f"{SITEMAP_NS}loc").text,
            "https://example.org/feeds/gtfs/weird&id",
        )


class TestUploadSitemap(unittest.TestCase):
    def setUp(self):
        patcher = patch("tasks.sitemap.generate_sitemap.storage.Client")
        self.client_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.blob = MagicMock()
        self.client_cls.return_value.bucket.return_value.blob.return_value = self.blob

    def test_uploads_the_xml_to_the_requested_bucket_and_object(self):
        upload_sitemap("<xml/>", "a-bucket", "sitemap.xml", make_public=False)
        self.client_cls.return_value.bucket.assert_called_once_with("a-bucket")
        self.client_cls.return_value.bucket.return_value.blob.assert_called_once_with(
            "sitemap.xml"
        )
        self.blob.upload_from_string.assert_called_once_with(
            "<xml/>", content_type="application/xml; charset=utf-8"
        )

    def test_sets_a_cache_control_header(self):
        upload_sitemap("<xml/>", "a-bucket", "sitemap.xml", make_public=False)
        self.assertEqual(self.blob.cache_control, "public, max-age=3600")

    def test_make_public_false_leaves_the_acl_alone(self):
        upload_sitemap("<xml/>", "a-bucket", "sitemap.xml", make_public=False)
        self.blob.make_public.assert_not_called()

    def test_make_public_true_sets_the_acl(self):
        upload_sitemap("<xml/>", "a-bucket", "sitemap.xml", make_public=True)
        self.blob.make_public.assert_called_once()

    def test_a_rejected_public_acl_does_not_fail_the_upload(self):
        """Uniform bucket-level access rejects per-object ACLs; the upload still stands."""
        self.blob.make_public.side_effect = Exception("uniform bucket-level access")
        upload_sitemap("<xml/>", "a-bucket", "sitemap.xml", make_public=True)
        self.blob.upload_from_string.assert_called_once()


if __name__ == "__main__":
    unittest.main()
