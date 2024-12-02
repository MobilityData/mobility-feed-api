#
#   MobilityData 2024
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

import pytest
from pydantic import BaseModel
from fastapi import HTTPException
from feeds_operations.impl.request_validator import validate_request


class MockImplModel(BaseModel):
    name: str
    age: int


@validate_request(MockImplModel, "data")
async def sample_function(data: MockImplModel):
    return data


@pytest.mark.asyncio
async def test_valid_request():
    data = MockImplModel(name="John Doe", age=30)
    result = await sample_function(data)
    assert result == data


@pytest.mark.asyncio
async def test_invalid_request():
    data = {"name": "John Doe", "age": "invalid_age"}
    with pytest.raises(HTTPException) as exc_info:
        await sample_function(data)
    assert exc_info.value.status_code == 400
    assert "Input should be a valid integer" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_missing_parameter():
    with pytest.raises(HTTPException) as exc_info:
        await sample_function(None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Missing parameter"
