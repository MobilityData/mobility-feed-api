import csv
from collections import defaultdict
from typing import Dict, List

from csv_cache import STOP_TIMES_FILE
from fast_csv_parser import FastCsvParser
from shared.helpers.utils import detect_encoding


class StopTimesProcessor:
    def __init__(self, csv_cache, logger=None, trips_processor=None):
        self.csv_cache = csv_cache
        self.logger = logger or csv_cache.logger
        self.stop_to_routes = defaultdict(set)
        self.trip_to_stops: Dict[str, List[str]] = {}
        self.trip_same_as: Dict[str, str] = None

    def process(self, trips_processor):
        trip_to_stops: Dict[str, List[str]] = {}
        filepath = self.csv_cache.get_path(STOP_TIMES_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)
        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))
            stop_id_index = self.csv_cache.get_index(columns, "stop_id")
            trip_id_index = self.csv_cache.get_index(columns, "trip_id")
            for line in f:
                if not line.strip():
                    continue
                row = csv_parser.parse(line)
                stop_id = self.csv_cache.get_safe_value_from_index(row, stop_id_index)
                trip_id = self.csv_cache.get_safe_value_from_index(row, trip_id_index)
                if trip_id and stop_id:
                    trip_to_stops.setdefault(trip_id, []).append(stop_id)
                    route_id = trips_processor.trip_to_route.get(trip_id)
                    if route_id:
                        self.stop_to_routes[stop_id].add(route_id)

            if trips_processor.has_trips_without_route():
                canonical: Dict[str, List[str]] = {}
                aliases: Dict[str, str] = {}
                seq_key_to_canonical_trip: Dict[tuple, str] = {}
                for trip_id, stops in trip_to_stops.items():
                    key = tuple(stops)
                    if key in seq_key_to_canonical_trip:
                        can_trip = seq_key_to_canonical_trip[key]
                        aliases[trip_id] = can_trip
                        self.logger.debug(
                            "Trip %s has identical stops as canonical trip %s; alias recorded",
                            trip_id,
                            can_trip,
                        )
                    else:
                        seq_key_to_canonical_trip[key] = trip_id
                        canonical[trip_id] = stops
                self.trip_to_stops = canonical
                self.trip_same_as = aliases

    def get_trip_alias(self, trip_id: str) -> str | None:
        """
        Return the direct canonical trip_id for an aliased trip.

        - If `trip_id` is present in `_trip_same_as`, returns its direct canonical trip_id.
        - If not aliased or the mapping is not built, returns None.
        - Does not resolve chained aliases.
        """
        mapping = self.trip_same_as
        if not mapping:
            return None
        return mapping.get(trip_id)

    def get_stops_from_trip(self, trip_id):
        return self.trip_to_stops.get(trip_id, [])
