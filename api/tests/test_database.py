import os
import random
import string
import unittest
from typing import List

from sqlalchemy.orm import Query

from database.database import Database
from database_gen.sqlacodegen_models import Gtfsdataset, Feed, Gtfsfeed, Externalid
from feeds.impl.datasets_api_impl import DatasetsApiImpl
from feeds.impl.feeds_api_impl import FeedsApiImpl

# TODO- Need to find a better way to setup the database for unit tests
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "postgres"
os.environ["POSTGRES_DB"] = "MobilityDatabase"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_HOST"] = "localhost"


def test_database_singleton():
    assert Database() is Database()


class TestingBoundingBox(unittest.TestCase):
    def setUp(self):
        super().__init__()
        self.db = Database()
        # latitudes: 37.615264, 38.2321
        # longitudes: -84.8984452721203, -84.4789953029549
        self.base_query = Query([Gtfsdataset, Gtfsdataset.bounding_box.ST_AsGeoJSON()]).filter(
            Gtfsdataset.stable_id == "mdb-1")

    def test_dateset_exists(self):
        self.assertEquals(1, len(self.db.select(query=self.base_query)))

    # TODO (jujiang): Change these datasets to use stable_id the id column are auto-generated in scripts/populate_db.py
    # def test_completed_closed(self):
    #     self._test_bounding("37.7, 38", "-84.7,-84.6", "completely_enclosed", True)
    #     # min latitude is too low
    #     self._test_bounding("37, 38", "-84.7,-84.6", "completely_enclosed", False)
    #     # max latitude is too high
    #     self._test_bounding("37.7, 39", "-84.7,-84.6", "completely_enclosed", False)
    #     # min longitude is too low
    #     self._test_bounding("37.7, 38", "-85,-84.6", "completely_enclosed", False)
    #     # max longitude is too high
    #     self._test_bounding("37.7, 38", "-84.7,-83", "completely_enclosed", False)
    #
    # def test_partial_closed(self):
    #     # completely enclosed, still considered as partially enclosed
    #     self._test_bounding("37.7, 38", "-84.7,-84.6", "partially_enclosed", True)
    #     # min latitude is too low
    #     self._test_bounding("37, 38", "-84.7,-84.6", "partially_enclosed", True)
    #     # max latitude is too high
    #     self._test_bounding("37.7, 39", "-84.7,-84.6", "partially_enclosed", True)
    #     # min longitude is too low
    #     self._test_bounding("37.7, 38", "-85,-84.6", "partially_enclosed", True)
    #     # max longitude is too high
    #     self._test_bounding("37.7, 38", "-84.7,-83", "partially_enclosed", True)
    #     # disjoint
    #     self._test_bounding("1, 2", "3, 4", "partially_enclosed", False)
    #     # contained
    #     self._test_bounding("37, 39", "-85,-83", "partially_enclosed", False)
    #
    # def test_disjoint(self):
    #     # completely enclosed
    #     self._test_bounding("37.7, 38", "-84.7,-84.6", "disjoint", False)
    #     # overlap
    #     self._test_bounding("37, 38", "-84.7,-84.6", "disjoint", False)
    #     # disjoint
    #     self._test_bounding("1, 2", "3, 4", "disjoint", True)
    #     # contained
    #     self._test_bounding("37, 39", "-85,-83", "disjoint", False)
    #
    # def _test_bounding(self, latitudes, longitudes, method, expected_found):
    #     query = DatasetsApiImpl.apply_bounding_filtering(self.base_query, latitudes, longitudes, method)
    #     result = self.db.select(query=query)
    #     if expected_found:
    #         self.assertTrue(result)
    #     else:
    #         self.assertFalse(result)


# class TestDatabaseQuery(unittest.TestCase):
#
#     @staticmethod
#     def _generate_random_feed_id():
#         return ''.join(random.choices(string.ascii_uppercase + string.digits, k=255))
#
#     def setUp(self):
#         self._FEED_ID_1 = "FEED_1"  # self._generate_random_feed_id()
#         self._FEED_ID_2 = "FEED_2"  # self._generate_random_feed_id()
#         self._FEED_ID_3 = "FEED_3"  # self._generate_random_feed_id()
#         self._FEED_ID_4 = "FEED_4"  # self._generate_random_feed_id()
#
#         self.db = Database()
#
#         self.db.merge(Gtfsfeed(id=self._FEED_ID_1))
#         self.db.merge(Gtfsfeed(id=self._FEED_ID_2))
#         self.db.merge(Gtfsfeed(id=self._FEED_ID_3))
#         self.db.merge(Gtfsfeed(id=self._FEED_ID_4))
#
#         self.db.commit()
#
#         self._DATASET_ID_1 = "DATASET_1"
#         self._DATASET_ID_2 = "DATASET_2"
#         self._DATASET_ID_3 = "DATASET_3"
#         self._DATASET_ID_4 = "DATASET_4"
#         self.db.merge(Gtfsdataset(id=self._DATASET_ID_1, feed_id=self._FEED_ID_1, latest=True))
#         self.db.merge(Gtfsdataset(id=self._DATASET_ID_2, feed_id=self._FEED_ID_1))
#         self.db.merge(Gtfsdataset(id=self._DATASET_ID_3, feed_id=self._FEED_ID_2))
#         self.db.merge(Gtfsdataset(id=self._DATASET_ID_4, feed_id=self._FEED_ID_2, latest=True))
#
#         self._EXTERNAL_ID_1 = "EXTERNAL_ID_1"
#         self._EXTERNAL_ID_2 = "EXTERNAL_ID_2"
#         self._EXTERNAL_ID_3 = "EXTERNAL_ID_3"
#         self.db.merge(Externalid(feed_id=self._FEED_ID_1, associated_id=self._EXTERNAL_ID_1, source="source1"))
#         self.db.merge(Externalid(feed_id=self._FEED_ID_1, associated_id=self._EXTERNAL_ID_2, source="source2"))
#         self.db.merge(Externalid(feed_id=self._FEED_ID_2, associated_id=self._EXTERNAL_ID_2, source="source3"))
#         self.db.merge(Externalid(feed_id=self._FEED_ID_2, associated_id=self._EXTERNAL_ID_3, source="source4"))
#         self.db.commit()
#
#         self.db.select(
#             query=f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{self._FEED_ID_1}', '{self._FEED_ID_2}')")
#         self.db.commit()
#         self.db.select(
#             query=f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{self._FEED_ID_2}', '{self._FEED_ID_3}')")
#         self.db.commit()
#         self.db.select(
#             query=f"INSERT INTO redirectingid (source_id, target_id) VALUES ('{self._FEED_ID_2}', '{self._FEED_ID_4}')")
#         # not sure why bulk commit doesn't work here
#         self.db.commit()
#
#     def tearDown(self) -> None:
#         self.db.select(Feed, conditions=[Feed.id == self._FEED_ID_1])
#
#         self.db.select(
#             query=f"DELETE FROM gtfsdataset where feed_id IN "
#                   f"{self._generate_in_clause([self._FEED_ID_1, self._FEED_ID_2, self._DATASET_ID_3, self._DATASET_ID_4])}"
#         )
#         self.db.commit()
#         self.db.select(
#             query=f"DELETE from redirectingid where "
#                   f"source_id IN {self._generate_in_clause([self._FEED_ID_1, self._FEED_ID_2, self._DATASET_ID_3, self._DATASET_ID_4])} "
#                   f"OR target_id IN {self._generate_in_clause([self._FEED_ID_1, self._FEED_ID_2, self._DATASET_ID_3, self._DATASET_ID_4])}")
#         self.db.commit()
#         self.db.commit()
#         self.db.select(
#             query=f"DELETE FROM externalid where associated_id IN ('{self._EXTERNAL_ID_1}', '{self._EXTERNAL_ID_2}',  '{self._EXTERNAL_ID_3}')")
#         self.db.commit()
#         self.db.select(
#             query=f"DELETE FROM gtfsfeed where id IN ('{self._FEED_ID_1}', '{self._FEED_ID_2}', '{self._FEED_ID_3}', '{self._FEED_ID_4}')")
#         self.db.commit()
#         self.db.select(
#             query=f"DELETE FROM feed WHERE id IN ('{self._FEED_ID_1}', '{self._FEED_ID_2}', '{self._FEED_ID_3}', '{self._FEED_ID_4}')")
#         self.db.commit()
#
#     @staticmethod
#     def _generate_in_clause(values: List[str]) -> str:
#         return "(" + ",".join([f"'{x}'" for x in values]) + ")"
#
#     def test_merge_gtfs_feed(self):
#         results = {feed.id: feed for feed in FeedsApiImpl().get_gtfs_feeds(None, None, None, None, None, None, None) if
#                    feed.id in [self._FEED_ID_1, self._FEED_ID_2]}
#         self.assertEquals(2, len(results))
#         feed_1 = results.get(self._FEED_ID_1, None)
#         feed_2 = results.get(self._FEED_ID_2, None)
#
#         self.assertIsNotNone(feed_1)
#         self.assertEquals([self._EXTERNAL_ID_1, self._EXTERNAL_ID_2],
#                           sorted([external_id.external_id for external_id in feed_1.external_ids]))
#         self.assertEquals(["source1", "source2"],
#                           sorted([external_id.source for external_id in feed_1.external_ids]))
#         self.assertEquals(self._DATASET_ID_1, feed_1.latest_dataset.id)
#         self.assertEquals([self._FEED_ID_2], sorted([redirect for redirect in feed_1.redirects]))
#
#         self.assertIsNotNone(feed_2)
#         self.assertEquals([self._EXTERNAL_ID_2, self._EXTERNAL_ID_3],
#                           sorted([external_id.external_id for external_id in feed_2.external_ids]))
#         self.assertEquals(["source3", "source4"],
#                           sorted([external_id.source for external_id in feed_2.external_ids]))
#         self.assertEquals(self._DATASET_ID_4, feed_2.latest_dataset.id)
#         self.assertEquals([self._FEED_ID_3, self._FEED_ID_4], sorted([redirect for redirect in feed_2.redirects]))
