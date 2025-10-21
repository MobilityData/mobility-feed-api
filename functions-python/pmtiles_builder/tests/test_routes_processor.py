import os
import tempfile
import unittest
from unittest.mock import MagicMock

from csv_cache import CsvCache
from routes_processor import RoutesProcessor


class DummyShapesProcessor:
    def __init__(self, points_map):
        # points_map: shape_id -> list of [lon, lat]
        self.points_map = points_map

    def get_shape_points(self, shape_id):
        return self.points_map.get(shape_id, [])


class DummyTripsProcessor:
    def __init__(self, shape_map=None, trips_no_shapes=None):
        # shape_map: route_id -> {shape_id: {"shape_id":..., "trip_ids": [...]}}
        self._shape_map = shape_map or {}
        self.trips_no_shapes_per_route = trips_no_shapes or {}

    def get_shape_from_route(self, route_id):
        return self._shape_map.get(route_id, {})


class DummyAgenciesProcessor:
    def __init__(self, agencies):
        self.agencies = agencies


class DummyStopsProcessor:
    def __init__(self, coords):
        # coords: stop_id -> (lon, lat)
        self.coords = coords

    def get_coordinates_for_stop(self, stop_id):
        return self.coords.get(stop_id)


class DummyStopTimesProcessor:
    def __init__(self, trip_stops=None, aliases=None):
        # trip_stops: trip_id -> [stop_ids]
        self._trip_stops = trip_stops or {}
        self._aliases = aliases or {}

    def get_trip_alias(self, trip_id):
        return self._aliases.get(trip_id)

    def get_stops_from_trip(self, trip_id):
        return self._trip_stops.get(trip_id, [])


class DummyRoutesColors:
    def __init__(self, route_colors_map):
        self.route_colors_map = route_colors_map


class TestRoutesProcessor(unittest.TestCase):
    def test_with_shapes_writes_geojson_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            # create routes.txt with a single route
            routes_path = csv_cache.get_path("routes.txt")
            with open(routes_path, "w", encoding="utf-8") as f:
                f.write(
                    "route_id,agency_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("r1,ag1,Route 1,00FF00,FFFFFF,3\n")

            # set up dummy collaborators
            shapes = DummyShapesProcessor({"s1": [[-73.0, 45.0], [-73.1, 45.1]]})
            trips = DummyTripsProcessor(
                shape_map={"r1": {"s1": {"shape_id": "s1", "trip_ids": ["t1"]}}}
            )
            agencies = DummyAgenciesProcessor({"ag1": "Agency One"})
            stops = DummyStopsProcessor({})
            stop_times = DummyStopTimesProcessor()
            colors = DummyRoutesColors({"r1": "00FF00"})

            processor = RoutesProcessor(
                csv_cache=csv_cache,
                logger=MagicMock(),
                agencies_processor=agencies,
                shapes_processor=shapes,
                trips_processor=trips,
                stops_processor=stops,
                stop_times_processor=stop_times,
                routes_processor_for_colors=colors,
            )

            # Call processing (uses BaseProcessor.process to set up parser/encoding)
            processor.process()

            # Validate outputs
            geojson_path = csv_cache.get_path("routes-output.geojson")
            json_path = csv_cache.get_path("routes.json")
            self.assertTrue(os.path.exists(geojson_path))
            self.assertTrue(os.path.exists(json_path))

            import json

            with open(geojson_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data.get("type"), "FeatureCollection")
            features = data.get("features", [])
            self.assertEqual(len(features), 1)
            feat = features[0]
            self.assertEqual(feat.get("properties", {}).get("route_id"), "r1")
            self.assertEqual(
                feat.get("properties", {}).get("agency_name"), "Agency One"
            )

            # check routes.json contains the color with leading #
            with open(json_path, "r", encoding="utf-8") as jf:
                jdata = json.load(jf)
            self.assertEqual(jdata[0].get("color"), "#00FF00")

    def test_fallback_to_stops_coordinates_and_aliasing(self):
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            with open(csv_cache.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,agency_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("r2,ag2,Route 2,FF0000,FFFFFF,3\n")

            # no shapes, but trips_no_shapes contains tA (canonical) and tB (alias)
            trips = DummyTripsProcessor(
                shape_map={}, trips_no_shapes={"r2": ["tA", "tB"]}
            )
            agencies = DummyAgenciesProcessor({"ag2": "Agency Two"})
            # Stop times: tA -> [s1, s2], tB alias should map to tA
            stop_times = DummyStopTimesProcessor(
                trip_stops={"tA": ["s1", "s2"]}, aliases={"tB": "tA"}
            )
            stops = DummyStopsProcessor({"s1": [-73.0, 45.0], "s2": [-73.1, 45.1]})
            colors = DummyRoutesColors({"r2": "FF0000"})
            shapes = DummyShapesProcessor({})

            processor = RoutesProcessor(
                csv_cache=csv_cache,
                logger=MagicMock(),
                agencies_processor=agencies,
                shapes_processor=shapes,
                trips_processor=trips,
                stops_processor=stops,
                stop_times_processor=stop_times,
                routes_processor_for_colors=colors,
            )

            processor.process()

            # Read geojson and ensure one feature produced with coordinates from stops
            import json

            with open(
                csv_cache.get_path("routes-output.geojson"), "r", encoding="utf-8"
            ) as fh:
                data = json.load(fh)
            features = data.get("features", [])
            self.assertEqual(len(features), 1)
            feat = features[0]
            self.assertEqual(feat.get("properties", {}).get("route_id"), "r2")
            coords = feat.get("geometry", {}).get("coordinates")
            self.assertEqual(coords, [[-73.0, 45.0], [-73.1, 45.1]])
            # Ensure alias was added to trip_ids
            self.assertIn("tB", feat.get("properties", {}).get("trip_ids", []))

    def test_mixed_shapes_and_stops_fallback(self):
        """Route has both shape-backed trips and trips without shapes; ensure both feature types are emitted."""
        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            # create routes file with route r3
            with open(csv_cache.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,agency_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("r3,ag3,Route 3,ABCDEF,000000,3\n")

            # shapes: s1 used by trip t1
            shapes = DummyShapesProcessor({"s1": [[-73.5, 45.5], [-73.6, 45.6]]})
            # trips: route r3 has shape s1 for trip t1; trips without shapes: t2 and t3
            trips = DummyTripsProcessor(
                shape_map={"r3": {"s1": {"shape_id": "s1", "trip_ids": ["t1"]}}},
                trips_no_shapes={"r3": ["t2", "t3"]},
            )
            agencies = DummyAgenciesProcessor({"ag3": "Agency Three"})
            # stop_times: t2 canonical, t3 alias of t2
            stop_times = DummyStopTimesProcessor(
                trip_stops={"t2": ["sx1", "sx2"]}, aliases={"t3": "t2"}
            )
            stops = DummyStopsProcessor({"sx1": [-74.0, 46.0], "sx2": [-74.1, 46.1]})
            colors = DummyRoutesColors({"r3": "ABCDEF"})

            processor = RoutesProcessor(
                csv_cache=csv_cache,
                logger=MagicMock(),
                agencies_processor=agencies,
                shapes_processor=shapes,
                trips_processor=trips,
                stops_processor=stops,
                stop_times_processor=stop_times,
                routes_processor_for_colors=colors,
            )

            processor.process()

            import json

            with open(
                csv_cache.get_path("routes-output.geojson"), "r", encoding="utf-8"
            ) as fh:
                data = json.load(fh)
            features = data.get("features", [])
            # Expect two features: one from the shape (t1) and one from stops fallback (t2 canonical)
            self.assertEqual(len(features), 2)

            # find shape-based feature by seeing shape_id property
            shape_feat = next(
                (
                    f
                    for f in features
                    if f.get("properties", {}).get("shape_id") == "s1"
                ),
                None,
            )
            self.assertIsNotNone(shape_feat)
            self.assertEqual(shape_feat.get("properties", {}).get("trip_ids"), ["t1"])

            # find stops-based feature (shape_id == "")
            stops_feat = next(
                (f for f in features if f.get("properties", {}).get("shape_id") == ""),
                None,
            )
            self.assertIsNotNone(stops_feat)
            self.assertEqual(
                stops_feat.get("properties", {}).get("trip_ids", [])[0], "t2"
            )
            self.assertEqual(
                stops_feat.get("geometry", {}).get("coordinates"),
                [[-74.0, 46.0], [-74.1, 46.1]],
            )

    def test_disjoint_routes_same_stops_no_shapes_produce_separate_features(self):
        """
        Two different routes (r1, r2) each have a trip without shape (t1, t2) that share the same stops sequence.
        We expect separate features per route and that t1 doesn't appear under r2's feature and vice versa.
        """
        from stop_times_processor import StopTimesProcessor

        class DummyTripsProcessorWithRoutes:
            def __init__(self):
                # trips without shapes per route
                self.trips_no_shapes_per_route = {"r1": ["t1"], "r2": ["t2"]}
                # mapping needed for stop_to_routes and to be cleared at end
                self.trip_to_route = {"t1": "r1", "t2": "r2"}

            def clear_trip_to_route(self):
                self.trip_to_route = {}

            def get_shape_from_route(self, route_id):
                return {}

        with tempfile.TemporaryDirectory() as td:
            csv_cache = CsvCache(workdir=td, logger=MagicMock())
            # routes.txt with r1 and r2
            with open(csv_cache.get_path("routes.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "route_id,agency_id,route_long_name,route_color,route_text_color,route_type\n"
                )
                f.write("r1,ag1,Route 1,00AA00,FFFFFF,3\n")
                f.write("r2,ag2,Route 2,AA0000,FFFFFF,3\n")

            # stop_times.txt with identical stops for t1 and t2
            with open(csv_cache.get_path("stop_times.txt"), "w", encoding="utf-8") as f:
                f.write("trip_id,stop_id,stop_sequence\n")
                f.write("t1,sA,1\n")
                f.write("t1,sB,2\n")
                f.write("t2,sA,1\n")
                f.write("t2,sB,2\n")

            # set up processors
            trips = DummyTripsProcessorWithRoutes()
            stop_times = StopTimesProcessor(
                csv_cache, logger=MagicMock(), trips_processor=trips
            )
            stop_times.process()

            # provide coordinates for the stops
            stops = DummyStopsProcessor({"sA": [-73.0, 45.0], "sB": [-73.1, 45.1]})
            shapes = DummyShapesProcessor({})
            agencies = DummyAgenciesProcessor(
                {"ag1": "Agency One", "ag2": "Agency Two"}
            )
            colors = DummyRoutesColors({"r1": "00AA00", "r2": "AA0000"})

            rp = RoutesProcessor(
                csv_cache=csv_cache,
                logger=MagicMock(),
                agencies_processor=agencies,
                shapes_processor=shapes,
                trips_processor=trips,
                stops_processor=stops,
                stop_times_processor=stop_times,
                routes_processor_for_colors=colors,
            )

            rp.process()

            import json

            with open(
                csv_cache.get_path("routes-output.geojson"), "r", encoding="utf-8"
            ) as fh:
                data = json.load(fh)

            features = data.get("features", [])
            # Expect two features (one per route)
            self.assertEqual(len(features), 2)
            # Group by route_id
            feats_by_route = {}
            for feat in features:
                rid = feat.get("properties", {}).get("route_id")
                feats_by_route.setdefault(rid, []).append(feat)

            self.assertIn("r1", feats_by_route)
            self.assertIn("r2", feats_by_route)
            self.assertEqual(len(feats_by_route["r1"]), 1)
            self.assertEqual(len(feats_by_route["r2"]), 1)

            r1_trip_ids = (
                feats_by_route["r1"][0].get("properties", {}).get("trip_ids", [])
            )
            r2_trip_ids = (
                feats_by_route["r2"][0].get("properties", {}).get("trip_ids", [])
            )

            # Ensure trips are not merged across routes
            self.assertIn("t1", r1_trip_ids)
            self.assertNotIn("t2", r1_trip_ids)
            self.assertIn("t2", r2_trip_ids)
            self.assertNotIn("t1", r2_trip_ids)


if __name__ == "__main__":
    unittest.main()
