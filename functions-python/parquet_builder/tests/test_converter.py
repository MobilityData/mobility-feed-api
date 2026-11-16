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
"""The properties a Parquet reader depends on, pinned.

These exist because the conversion is reproduced here rather than imported from
gtfs-garage, so nothing else would notice if the output drifted from what its reader
expects. Two of them fail silently rather than loudly if broken, which is the whole
reason they are asserted: a typed column breaks filtering but still renders, and an
empty string where a NULL belongs makes "is empty" quietly miss rows.
"""

import json
from pathlib import Path

import pytest

from converter import (
    MANIFEST,
    SourceFacts,
    _ident,
    convert_to_parquet,
    extract_feed,
    zip_member_sizes,
)

duckdb = pytest.importorskip("duckdb")


AGENCY = "agency_id,agency_name,agency_url,agency_timezone\n1,Test Transit,https://example.org,UTC\n"
STOPS = (
    "stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
    "S1,First,45.5,-73.6,\n"
    "S2,Second,45.6,-73.7,S1\n"
)
ROUTES = "route_id,agency_id,route_short_name,route_type\nR1,1,1,3\n"

LOCATIONS = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "zone-a",
                "properties": {"stop_name": "Zone A", "stop_desc": "on demand"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                },
            },
            {
                "id": "zone-b",
                "properties": {"stop_name": "Zone B"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 0]]]],
                },
            },
        ],
    }
)


@pytest.fixture
def feed(tmp_path) -> Path:
    data = tmp_path / "extracted"
    data.mkdir()
    (data / "agency.txt").write_text(AGENCY)
    (data / "stops.txt").write_text(STOPS)
    (data / "routes.txt").write_text(ROUTES)
    return data


def _describe(path: Path) -> dict:
    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        con.close()


def test_one_parquet_per_table_named_after_the_file_stem(feed, tmp_path):
    out = tmp_path / "parquet"
    tables = convert_to_parquet(feed, out)

    assert [t.name for t in tables] == ["agency", "routes", "stops"]
    assert sorted(p.name for p in out.glob("*.parquet")) == [
        "agency.parquet",
        "routes.parquet",
        "stops.parquet",
    ]


def test_a_table_name_cannot_escape_its_identifier(feed, tmp_path):
    """Table names come from archive member filenames, which a producer controls."""
    hostile = 'stops" AS SELECT 1; DROP TABLE agency; --'
    (feed / f"{hostile}.txt").write_text(AGENCY)

    out = tmp_path / "parquet"
    tables = convert_to_parquet(feed, out)

    assert hostile in [t.name for t in tables]
    assert "agency" in [t.name for t in tables]
    assert (out / f"{hostile}.parquet").exists()


def test_ident_doubles_embedded_quotes():
    assert _ident("stops") == '"stops"'
    assert _ident('a"b') == '"a""b"'


def test_every_column_is_text(feed, tmp_path):
    """The reader filters with ILIKE and `= ''`. A typed column breaks that silently."""
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    for parquet in out.glob("*.parquet"):
        types = set(_describe(parquet).values())
        assert types == {"VARCHAR"}, f"{parquet.name} has non-text columns: {types}"


def test_empty_fields_become_null_not_empty_string(feed, tmp_path):
    """The reader rewrites `= ''` into `IS NULL OR = ''` on this basis."""
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    con = duckdb.connect(database=":memory:")
    try:
        nulls = con.execute(
            f"SELECT count(*) FROM read_parquet('{out / 'stops.parquet'}') "
            "WHERE parent_station IS NULL"
        ).fetchone()[0]
        empties = con.execute(
            f"SELECT count(*) FROM read_parquet('{out / 'stops.parquet'}') "
            "WHERE parent_station = ''"
        ).fetchone()[0]
    finally:
        con.close()

    assert nulls == 1
    assert empties == 0


def test_an_unreadable_file_is_skipped_not_fatal(feed, tmp_path):
    """Most GTFS files are optional; one bad extra must not cost the whole feed."""
    (feed / "broken.txt").write_text("")
    out = tmp_path / "parquet"

    tables = convert_to_parquet(feed, out)

    assert "agency" in [t.name for t in tables]
    assert not (out / "broken.parquet").exists()


def test_a_header_only_file_is_still_a_table(feed, tmp_path):
    """An optional file present but empty of rows is a real, empty GTFS table."""
    (feed / "frequencies.txt").write_text("trip_id,start_time,end_time,headway_secs\n")
    out = tmp_path / "parquet"

    tables = {t.name: t for t in convert_to_parquet(feed, out)}

    assert "frequencies" in tables
    assert tables["frequencies"].rows == 0
    assert list(_describe(out / "frequencies.parquet")) == [
        "trip_id",
        "start_time",
        "end_time",
        "headway_secs",
    ]


def test_apple_double_resource_forks_are_not_tables(feed, tmp_path):
    """`__MACOSX/._stops.txt` flattens to something that looks like a table."""
    (feed / "._stops.txt").write_text(STOPS)
    (feed / ".DS_Store").write_text("junk")
    out = tmp_path / "parquet"

    tables = convert_to_parquet(feed, out)

    assert [t.name for t in tables] == ["agency", "routes", "stops"]
    assert not (out / "._stops.parquet").exists()


def test_locations_geojson_becomes_a_table_with_stable_columns(feed, tmp_path):
    """Polygon and MultiPolygon in one feed must not change the column set."""
    (feed / "locations.geojson").write_text(LOCATIONS)
    out = tmp_path / "parquet"

    tables = convert_to_parquet(feed, out)

    assert "locations" in [t.name for t in tables]
    columns = _describe(out / "locations.parquet")
    assert list(columns) == [
        "id",
        "stop_name",
        "stop_desc",
        "geometry_type",
        "geometry",
    ]
    assert set(columns.values()) == {"VARCHAR"}

    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(
            f"SELECT id, geometry_type FROM read_parquet('{out / 'locations.parquet'}') ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    assert rows == [("zone-a", "Polygon"), ("zone-b", "MultiPolygon")]


def test_malformed_locations_geojson_is_ignored(feed, tmp_path):
    """A broken optional file loses the zones, not the feed."""
    (feed / "locations.geojson").write_text("{not json at all")
    out = tmp_path / "parquet"

    tables = convert_to_parquet(feed, out)

    assert "locations" not in [t.name for t in tables]
    assert "stops" in [t.name for t in tables]


def test_manifest_describes_what_was_written(feed, tmp_path):
    out = tmp_path / "parquet"
    tables = convert_to_parquet(feed, out)

    manifest = json.loads((out / MANIFEST).read_text())

    assert manifest["version"] == 2
    assert [t["name"] for t in manifest["tables"]] == [t.name for t in tables]
    stops = next(t for t in manifest["tables"] if t["name"] == "stops")
    assert stops["file"] == "stops.parquet"
    assert stops["rows"] == 2
    assert stops["columns"] == 5


def test_bytes_is_the_source_size_and_parquet_bytes_the_converted_one(feed, tmp_path):
    """The v1 -> v2 trap: `bytes` used to mean the Parquet size and now means the
    source's. Asserting both, and that they differ, is what catches a swap."""
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    manifest = json.loads((out / MANIFEST).read_text())
    stops = next(t for t in manifest["tables"] if t["name"] == "stops")

    assert stops["bytes"] == (feed / "stops.txt").stat().st_size
    assert stops["parquet_bytes"] == (out / "stops.parquet").stat().st_size
    assert stops["bytes"] != stops["parquet_bytes"]


def test_the_totals_add_up(feed, tmp_path):
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    manifest = json.loads((out / MANIFEST).read_text())
    entries = manifest["tables"]

    assert manifest["totals"]["stored_bytes"] == sum(
        t["parquet_bytes"] for t in entries
    )
    assert manifest["totals"]["uncompressed_bytes"] == sum(t["bytes"] for t in entries)


def test_a_folder_source_reports_no_compressed_sizes(feed, tmp_path):
    """A member's compressed size exists only inside an archive."""
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    manifest = json.loads((out / MANIFEST).read_text())

    assert manifest["source"]["kind"] == "folder"
    assert manifest["source"]["bytes"] > 0
    assert all(t["compressed_bytes"] is None for t in manifest["tables"])


def test_a_zip_source_records_what_each_file_weighed_inside_it(tmp_path):
    """The Zipped column can never come back if this is not captured up front."""
    import zipfile

    archive = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        # Repetitive content so compression is unambiguously smaller.
        zf.writestr("stops.txt", "stop_id,stop_name\n" + "S1,First\n" * 500)
        zf.writestr("agency.txt", AGENCY)

    data_dir = extract_feed(archive, tmp_path / "extracted")
    out = tmp_path / "parquet"
    convert_to_parquet(
        data_dir,
        out,
        source=SourceFacts(
            kind="zip",
            bytes=archive.stat().st_size,
            compressed_sizes=zip_member_sizes(archive),
        ),
    )

    manifest = json.loads((out / MANIFEST).read_text())
    assert manifest["source"]["kind"] == "zip"
    assert manifest["source"]["bytes"] == archive.stat().st_size

    stops = next(t for t in manifest["tables"] if t["name"] == "stops")
    assert stops["compressed_bytes"] > 0
    assert stops["compressed_bytes"] < stops["bytes"], "a zipped file should be smaller"


def test_zip_member_sizes_is_empty_for_a_non_archive(tmp_path):
    not_a_zip = tmp_path / "feed.zip"
    not_a_zip.write_text("definitely not a zip")

    assert zip_member_sizes(not_a_zip) == {}


def test_row_counts_are_reported(feed, tmp_path):
    tables = {t.name: t for t in convert_to_parquet(feed, tmp_path / "parquet")}

    assert tables["stops"].rows == 2
    assert tables["agency"].rows == 1


def test_progress_is_reported_once_per_table(feed, tmp_path):
    seen = []
    convert_to_parquet(
        feed, tmp_path / "parquet", on_progress=lambda *args: seen.append(args)
    )

    assert [s[0] for s in seen] == ["convert"] * 3
    assert [s[1] for s in seen] == [1, 2, 3]
    assert all(s[2] == 3 for s in seen)
    assert [s[3] for s in seen] == ["agency", "routes", "stops"]


def test_a_feed_with_nothing_readable_is_an_error(tmp_path):
    """Every table failing means a wrong location, not a feed with no files."""
    empty = tmp_path / "extracted"
    empty.mkdir()

    with pytest.raises(ValueError, match="No readable GTFS files"):
        convert_to_parquet(empty, tmp_path / "parquet")


def test_output_reopens_as_a_parquet_feed(feed, tmp_path):
    """The round trip the viewer performs: open the directory, get the same tables."""
    out = tmp_path / "parquet"
    convert_to_parquet(feed, out)

    con = duckdb.connect(database=":memory:")
    try:
        for parquet in out.glob("*.parquet"):
            table = parquet.stem
            con.execute(
                f"""CREATE VIEW "{table}" AS SELECT * FROM read_parquet('{parquet}')"""
            )
        names = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert names == {"agency", "routes", "stops"}
        assert con.execute(
            'SELECT stop_name FROM "stops" ORDER BY stop_id'
        ).fetchall() == [
            ("First",),
            ("Second",),
        ]
    finally:
        con.close()
