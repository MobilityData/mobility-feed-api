import csv
from collections import defaultdict
from typing import Dict, List

from base_processor import BaseProcessor
from csv_cache import STOP_TIMES_FILE


class StopTimesProcessor(BaseProcessor):
    def __init__(self, csv_cache, logger=None, trips_processor=None):
        super().__init__(STOP_TIMES_FILE, csv_cache, logger)
        self.trips_processor = trips_processor
        self.stop_to_routes = defaultdict(set)
        self.trip_with_no_shape_to_stops: Dict[str, List[str]] = {}
        self.trip_with_no_shape_same_as: Dict[str, str] = {}

    def process_file(self):
        # store (stop_sequence, stop_id) per trip so we can sort by sequence
        trip_to_stops: Dict[str, List[tuple]] = {}
        with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))
            stop_id_index = self.csv_cache.get_index(columns, "stop_id")
            trip_id_index = self.csv_cache.get_index(columns, "trip_id")
            seq_index = self.csv_cache.get_index(columns, "stop_sequence")

            # Collect unique trips without shapes across all routes
            # (trip_id should be unique in trips file according to specs)
            trips_without_shape_set = set()
            for trip_list in self.trips_processor.trips_no_shapes_per_route.values():
                trips_without_shape_set.update(trip_list)

            line_count = 0
            # fallback counter per trip when stop_sequence is missing or malformed
            seq_fallback_counter = defaultdict(int)

            for line in f:
                if not line.strip():
                    continue
                row = self.csv_parser.parse(line)
                stop_id = self.csv_cache.get_safe_value_from_index(row, stop_id_index)
                trip_id = self.csv_cache.get_safe_value_from_index(row, trip_id_index)

                line_count += 1
                if line_count % 100_000 == 0:
                    self.logger.debug(
                        "Processed %d lines of %s", line_count, self.filepath
                    )

                if trip_id and stop_id:
                    # attempt to read numeric stop_sequence, fallback to incremental per trip
                    seq = None
                    if seq_index is not None:
                        seq = self.csv_cache.get_safe_int_from_index(row, seq_index)
                    if seq is None:
                        seq_fallback_counter[trip_id] += 1
                        seq = seq_fallback_counter[trip_id]

                    # Collect trips to stop for trips with shape so we can fall back on using the stops as geometry.
                    if trip_id in trips_without_shape_set:
                        trip_to_stops.setdefault(trip_id, []).append((seq, stop_id))
                    route_id = self.trips_processor.trip_to_route.get(trip_id)
                    if route_id:
                        # Used for stops pmtiles
                        self.stop_to_routes[stop_id].add(route_id)

            # Since memory is limited, clear the data after use.
            self.trips_processor.clear_trip_to_route()

            # Convert to a sorted list for deterministic iteration
            trips_without_shape = sorted(trips_without_shape_set)
            canonical: Dict[str, List[str]] = {}
            aliases: Dict[str, str] = {}
            seq_key_to_canonical_trip: Dict[tuple, str] = {}
            for trip_id in trips_without_shape:
                items = trip_to_stops.get(trip_id, [])
                if not items:
                    continue

                # sort by numeric stop_sequence to normalize inverted rows
                items_sorted = sorted(items, key=lambda x: x[0])
                stops_for_trip = [stop for _, stop in items_sorted]

                key = tuple(stops_for_trip)
                if key in seq_key_to_canonical_trip:
                    can_trip = seq_key_to_canonical_trip[key]
                    aliases[trip_id] = can_trip
                else:
                    seq_key_to_canonical_trip[key] = trip_id
                    canonical[trip_id] = stops_for_trip
            self.trip_with_no_shape_to_stops = canonical
            self.trip_with_no_shape_same_as = aliases

    def get_trip_alias(self, trip_id: str) -> str | None:
        """
        Return the direct canonical trip_id for an aliased trip.

        - If `trip_id` is present in `_trip_same_as`, returns its direct canonical trip_id.
        - If not aliased or the mapping is not built, returns None.
        - Does not resolve chained aliases.
        """
        mapping = self.trip_with_no_shape_same_as
        if not mapping:
            return None
        return mapping.get(trip_id)

    def get_stops_from_trip(self, trip_id):
        return self.trip_with_no_shape_to_stops.get(trip_id, [])
