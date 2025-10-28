import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.shapes_processor import ShapesProcessor
from src.csv_cache import CsvCache


class TestShapesProcessor(unittest.TestCase):
    def test_shapes_processor_builds_arrays_and_sorts(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "workdir_shapes"
            workdir.mkdir()

            shapes_path = workdir / "shapes.txt"
            shapes_content = (
                "shape_id,shape_pt_lon,shape_pt_lat,shape_pt_sequence\n"
                "s1,-122.0,37.0,2\n"
                "s1,-122.5,37.5,1\n"
                "s2,-123.0,38.0,1\n"
            )
            shapes_path.write_text(shapes_content)

            csv_cache = CsvCache(str(workdir))
            processor = ShapesProcessor(csv_cache, logger=MagicMock())
            processor.process()

            # ensure counts observed
            self.assertEqual(processor.unique_shape_id_counts.get("s1"), 2)
            self.assertEqual(processor.unique_shape_id_counts.get("s2"), 1)

            # s1 should be sorted by sequence (sequence 1 then 2)
            s1_points = processor.get_shape_points("s1")
            self.assertEqual(s1_points, [[-122.5, 37.5], [-122.0, 37.0]])

            # s2 single point
            s2_points = processor.get_shape_points("s2")
            self.assertEqual(s2_points, [[-123.0, 38.0]])

    def test_get_shape_points_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "workdir_empty"
            workdir.mkdir()

            # create empty shapes.txt explicitly
            (workdir / "shapes.txt").write_text("")

            csv_cache = CsvCache(str(workdir))
            processor = ShapesProcessor(csv_cache, logger=MagicMock())
            processor.process()

            # no shapes present
            self.assertEqual(processor.get_shape_points("missing"), [])

    def test_missing_file_is_handled_gracefully(self):
        # If shapes.txt does not exist, processor should not raise and queries return empty
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())

            proc = ShapesProcessor(csv_cache, logger=MagicMock())
            # Should not raise even though shapes.txt is missing
            proc.process()

            self.assertEqual(proc.get_shape_points("any"), [])
            self.assertEqual(proc.unique_shape_id_counts, {})


if __name__ == "__main__":
    unittest.main()
