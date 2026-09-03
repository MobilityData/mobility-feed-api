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
"""The CSV arrives as a raw `text/csv` body, not a multipart upload: the generator renders a
binary multipart part as `str = Form(...)`, which FastAPI then rejects with 422 because a part
carrying a filename becomes an UploadFile. These drive a real request through the generated
router to prove the body arrives intact, which the impl-level tests cannot show.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from feeds_gen.apis.early_access_api import router
from feeds_gen.models.early_access_import_category_summary import (
    EarlyAccessImportCategorySummary,
)
from feeds_gen.models.extra_models import TokenModel
from feeds_gen.models.import_early_access_invited_emails_response import (
    ImportEarlyAccessInvitedEmailsResponse,
)
from feeds_gen.security_api import get_token_ApiKeyAuth

PROGRAM_ID = "program-under-test"
UPLOAD_URL = f"/v1/operations/early-access-programs/{PROGRAM_ID}/invited-emails:upload"


def _empty_response():
    """A valid response, so the route's response validation does not mask what is asserted."""
    empty = EarlyAccessImportCategorySummary(count=0, sample=[])
    return ImportEarlyAccessInvitedEmailsResponse(
        program_id=PROGRAM_ID,
        dry_run=True,
        matched_existing_account=empty,
        no_account_yet=empty,
        already_invited=empty,
        already_enrolled=empty,
        invalid=[],
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_ApiKeyAuth] = lambda: TokenModel(sub="test")
    return TestClient(app)


def _post(client, csv_text, **params):
    return client.post(
        UPLOAD_URL,
        content=csv_text,
        headers={"Content-Type": "text/csv"},
        params=params,
    )


def test_raw_csv_body_reaches_the_impl_intact(client):
    # CRLF and a quoted comma are exactly what a spreadsheet export produces, and are the
    # characters most likely to be mangled in transit.
    csv_text = 'Name,EMAIL\r\n"Doe, Ada",ada@example.com\r\n'

    with patch(
        "feeds_operations.impl.early_access_impl.EarlyAccessApiImpl"
        ".upload_early_access_invited_emails_csv",
        return_value=_empty_response(),
    ) as upload:
        response = _post(client, csv_text, dry_run="false")

    assert response.status_code != 422, response.text
    assert upload.called
    program_id, body = upload.call_args[0][:2]
    assert program_id == PROGRAM_ID
    assert body == csv_text
    assert upload.call_args[0][2] is False


def test_dry_run_defaults_to_true_when_the_query_param_is_omitted(client):
    with patch(
        "feeds_operations.impl.early_access_impl.EarlyAccessApiImpl"
        ".upload_early_access_invited_emails_csv",
        return_value=_empty_response(),
    ) as upload:
        _post(client, "email\na@example.com\n")

    assert upload.call_args[0][2] is True


def test_a_request_with_no_body_is_rejected(client):
    response = client.post(UPLOAD_URL, headers={"Content-Type": "text/csv"})
    assert response.status_code == 422
