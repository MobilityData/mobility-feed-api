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
"""CSV responses for Operations API list endpoints.

Callers pass an explicit `fieldnames` list rather than letting the writer infer columns from the
data, so column order is stable and adding a field to a row dict cannot silently reorder or
introduce columns. Same approach as `export_csv/src/main.py`.

Returns a single buffered `Response`, never a `StreamingResponse`: `operations_api` runs behind a
WSGI-to-ASGI shim (`operations_api/src/main.py`) whose `send()` overwrites the response body per
message instead of appending, so a multi-chunk body would be truncated to its last chunk.
"""

import csv
import io
from typing import Any, Dict, List, Sequence

from fastapi import Response

CSV_FORMAT = "csv"
JSON_FORMAT = "json"


def rows_to_csv(fieldnames: Sequence[str], rows: List[Dict[str, Any]]) -> str:
    """Render `rows` as CSV text with a header row. Keys absent from a row become empty cells."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _cell(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def csv_response(
    filename: str, fieldnames: Sequence[str], rows: List[Dict[str, Any]]
) -> Response:
    """A `text/csv` attachment response. Returning a raw Response from an impl whose generated
    route is annotated with a Pydantic model is supported: FastAPI skips response-model
    validation when the handler returns a Response instance."""
    return Response(
        content=rows_to_csv(fieldnames, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cell(value: Any) -> str:
    """Empty string for None so a missing value is a blank cell rather than the text 'None'."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
