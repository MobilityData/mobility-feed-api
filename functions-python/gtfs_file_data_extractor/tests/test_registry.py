import unittest

from extractors.feed_info_extractor import FeedInfoExtractor
from extractors.registry import EXTRACTORS, get_extractor


class TestRegistry(unittest.TestCase):
    def test_known_file_returns_extractor(self):
        self.assertIsInstance(get_extractor("feed_info.txt"), FeedInfoExtractor)

    def test_unknown_file_returns_none(self):
        self.assertIsNone(get_extractor("stops.txt"))

    def test_registry_keys_match_extractor_file_name(self):
        for file_name, extractor in EXTRACTORS.items():
            self.assertEqual(file_name, extractor.file_name)


if __name__ == "__main__":
    unittest.main()
