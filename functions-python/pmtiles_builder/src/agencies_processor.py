from base_processor import BaseProcessor
from csv_cache import AGENCY_FILE


class AgenciesProcessor(BaseProcessor):
    def __init__(
        self,
        csv_cache,
        logger=None,
    ):
        super().__init__(AGENCY_FILE, csv_cache, logger)
        self.agencies = {}

    def process_file(self):
        with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
            header = f.readline()
            columns = self.csv_parser.parse_header(header)
            if not columns:
                return

            agency_id_index = self.csv_cache.get_index(columns, "agency_id")
            agency_name_index = self.csv_cache.get_index(columns, "agency_name")

            for line in f:
                if not line.strip():
                    continue

                row = self.csv_parser.parse(line)
                agency_id = self.csv_cache.get_safe_value_from_index(
                    row, agency_id_index
                )
                agency_name = self.csv_cache.get_safe_value_from_index(
                    row, agency_name_index
                )

                if agency_id:
                    self.agencies[agency_id] = agency_name
