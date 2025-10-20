from src.shapes_processor import ShapesProcessor
from src.csv_cache import CsvCache


def test_shapes_processor_builds_arrays_and_sorts(tmp_path):
    # Prepare a workdir and shapes.txt with out-of-order sequences for shape s1
    workdir = tmp_path / "workdir_shapes"
    workdir.mkdir()

    shapes_path = workdir / "shapes.txt"
    # header order doesn't matter; use canonical names
    shapes_content = """shape_id,shape_pt_lon,shape_pt_lat,shape_pt_sequence
s1,-122.0,37.0,2
s1,-122.5,37.5,1
s2,-123.0,38.0,1
"""
    shapes_path.write_text(shapes_content)

    csv_cache = CsvCache(str(workdir))
    processor = ShapesProcessor(csv_cache)
    # run processing (BaseProcessor.process sets up parser and encoding)
    processor.process()

    # ensure counts observed
    assert processor.unique_shape_id_counts.get("s1") == 2
    assert processor.unique_shape_id_counts.get("s2") == 1

    # s1 should be sorted by sequence (sequence 1 then 2)
    s1_points = processor.get_shape_points("s1")
    assert s1_points == [[-122.5, 37.5], [-122.0, 37.0]]

    # s2 single point
    s2_points = processor.get_shape_points("s2")
    assert s2_points == [[-123.0, 38.0]]


def test_get_shape_points_empty(tmp_path):
    workdir = tmp_path / "workdir_empty"
    workdir.mkdir()

    csv_cache = CsvCache(str(workdir))
    processor = ShapesProcessor(csv_cache)
    # no shapes.txt present -> processing should be fine but produce empty arrays
    # call process() which will attempt to open the file; create empty file to be explicit
    (workdir / "shapes.txt").write_text("")

    processor.process()

    assert processor.get_shape_points("missing") == []
