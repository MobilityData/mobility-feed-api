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

Buffered `Response` only, never `StreamingResponse`: the WSGI-to-ASGI shim in
`operations_api/src/main.py` overwrites the body per message instead of appending, so a
multi-chunk body is truncated to its last chunk.
"""

import csv
import io
from typing import Any, Dict, List, Sequence

from fastapi import Response

CSV_FORMAT = "csv"
JSON_FORMAT = "json"


def rows_to_csv(fieldnames: Sequence[str], rows: List[Dict[str, Any]]) -> str:
    """CSV text with a header row. Explicit `fieldnames` keeps column order stable."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _cell(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def csv_response(
    filename: str, fieldnames: Sequence[str], rows: List[Dict[str, Any]]
) -> Response:
    """A `text/csv` attachment. FastAPI skips response-model validation for a raw Response, so
    this is safe to return from a route annotated with a Pydantic model."""
    return Response(
        content=rows_to_csv(fieldnames, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cell(value: Any) -> str:
    """Blank cell for None rather than the text 'None'."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
