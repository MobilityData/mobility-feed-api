import csv

from base_processor import BaseProcessor
from csv_cache import ROUTES_FILE


class RoutesProcessorForColors(BaseProcessor):
    """Read routes.txt to map route_id → route_color for later use.
    Routes processing is split in two to avoid circular dependencies: StopsProcessor can rely on route colors
    without requiring the full routes build to have run.
    The input file is retained for the next pass over routes.txt in RoutesProcessor (no_delete=True).
    """

    def __init__(
        self,
        csv_cache,
        logger=None,
    ):
        super().__init__(ROUTES_FILE, csv_cache, logger, no_delete=True)
        self.route_colors_map = {}

    def process_file(self):
        with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))

            route_id_index = self.csv_cache.get_index(columns, "route_id")
            route_color_index = self.csv_cache.get_index(columns, "route_color")

            for line in f:
                if not line.strip():
                    continue

                row = self.csv_parser.parse(line)
                route_id = self.csv_cache.get_safe_value_from_index(row, route_id_index)
                route_color = self.csv_cache.get_safe_value_from_index(
                    row, route_color_index, ""
                )

                if route_id:
                    self.route_colors_map[route_id] = route_color
