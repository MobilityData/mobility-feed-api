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

from converter import MANIFEST, convert_to_parquet

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

    assert manifest["version"] == 1
    assert [t["name"] for t in manifest["tables"]] == [t.name for t in tables]
    stops = next(t for t in manifest["tables"] if t["name"] == "stops")
    assert stops["file"] == "stops.parquet"
    assert stops["rows"] == 2
    assert stops["bytes"] == (out / "stops.parquet").stat().st_size


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
