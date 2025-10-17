import csv

from csv_cache import ROUTES_FILE
from fast_csv_parser import FastCsvParser
from shared.helpers.logger import get_logger
from shared.helpers.utils import detect_encoding


class RoutesProcessorForColors:
    def __init__(
        self,
        csv_cache,
        logger=None,
    ):
        self.csv_cache = csv_cache
        if logger:
            self.logger = logger
        else:
            self.logger = get_logger(RoutesProcessorForColors.__name__)
        self.route_colors_map = {}

    def process(self):
        filepath = self.csv_cache.get_path(ROUTES_FILE)
        csv_parser = FastCsvParser()
        encoding = detect_encoding(filename=filepath, logger=self.logger)

        with open(filepath, "r", encoding=encoding, newline="") as f:
            header = f.readline()
            if not header:
                return
            columns = next(csv.reader([header]))

            route_id_index = self.csv_cache.get_index(columns, "route_id")
            route_color_index = self.csv_cache.get_index(columns, "route_color")

            for line in f:
                if not line.strip():
                    continue

                row = csv_parser.parse(line)
                route_id = self.csv_cache.get_safe_value_from_index(row, route_id_index)
                route_color = self.csv_cache.get_safe_value_from_index(
                    row, route_color_index
                )

                if route_id:
                    self.route_colors_map[route_id] = route_color
