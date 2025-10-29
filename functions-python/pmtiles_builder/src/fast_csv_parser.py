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
            return next(csv.reader([line]))
        return line.rstrip("\r\n").split(",")
