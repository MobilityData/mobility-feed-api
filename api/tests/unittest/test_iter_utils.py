import unittest

from shared.common.iter_utils import batched


class TestBatched(unittest.TestCase):
    def test_evenly_divisible(self):
        result = list(batched([1, 2, 3, 4], 2))
        self.assertEqual(result, [(1, 2), (3, 4)])

    def test_last_batch_shorter(self):
        result = list(batched([1, 2, 3, 4, 5], 2))
        self.assertEqual(result, [(1, 2), (3, 4), (5,)])

    def test_batch_larger_than_iterable(self):
        result = list(batched([1, 2], 10))
        self.assertEqual(result, [(1, 2)])

    def test_empty_iterable(self):
        result = list(batched([], 3))
        self.assertEqual(result, [])

    def test_batch_size_one(self):
        result = list(batched([1, 2, 3], 1))
        self.assertEqual(result, [(1,), (2,), (3,)])

    def test_works_with_strings(self):
        result = list(batched("abcde", 2))
        self.assertEqual(result, [("a", "b"), ("c", "d"), ("e",)])


if __name__ == "__main__":
    unittest.main()
