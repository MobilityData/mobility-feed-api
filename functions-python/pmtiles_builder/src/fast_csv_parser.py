import csv
from typing import List


class FastCsvParser:
    """Fast CSV line parser with simple heuristic: if a line contains quotes, fall back to csv.reader, else split.
    Tracks number of quoted lines encountered.
    """

    def __init__(self) -> None:
        self._lines_with_quotes = 0

    @property
    def lines_with_quotes(self) -> int:
        return self._lines_with_quotes

    def parse(
        self, line: str
    ) -> List[str]:  # pragma: no cover (behavior tested indirectly)
        if '"' in line:
            self._lines_with_quotes += 1
            row = next(
                csv.reader([line]), []
            )  # default to empty list if iterator is exhausted
        else:
            row = line.rstrip("\r\n").split(",")

        return [c.strip() for c in row]

    @staticmethod
    def parse_header(header: str) -> List[str]:
        """Parse a CSV header line into a list of column names.
        Ignore leading/trailing whitespace around column names.

        """
        if not header:
            return []
        columns = next(csv.reader([header]))
        return [c.strip() for c in columns]
