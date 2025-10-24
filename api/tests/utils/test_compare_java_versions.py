import unittest
from shared.db_models.model_utils import compare_java_versions


class TestCompareJavaVersions(unittest.TestCase):
    def test_compare_versions_equal(self):
        self.assertEqual(compare_java_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_java_versions("1.0.0-SNAPSHOT", "1.0.0-SNAPSHOT"), 0)

    def test_compare_versions_v1_greater(self):
        self.assertEqual(compare_java_versions("1.0.1", "1.0.0"), 1)
        self.assertEqual(compare_java_versions("1.0.0", "0.9.9"), 1)
        self.assertEqual(compare_java_versions("1.0.0", "1.0.0-SNAPSHOT"), 1)

    def test_compare_versions_v2_greater(self):
        self.assertEqual(compare_java_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_java_versions("0.9.9", "1.0.0"), -1)
        self.assertEqual(compare_java_versions("1.0.0-SNAPSHOT", "1.0.0"), -1)

    def test_compare_versions_with_none(self):
        self.assertEqual(compare_java_versions(None, None), 0)
        self.assertEqual(compare_java_versions(None, "1.0.0"), -1)
        self.assertEqual(compare_java_versions("1.0.0", None), 1)


if __name__ == "__main__":
    unittest.main()
