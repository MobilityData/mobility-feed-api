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
from typing import List

from fastapi import HTTPException

from garage.impl.error_handling import not_implemented
from garage_gen.apis.garage_api_base import BaseGarageApi
from garage_gen.models.create_user_dataset_request import CreateUserDatasetRequest
from garage_gen.models.create_user_dataset_response import CreateUserDatasetResponse
from garage_gen.models.user_dataset import UserDataset


def _not_implemented() -> HTTPException:
    return HTTPException(status_code=501, detail=not_implemented)


class GarageApiImpl(BaseGarageApi):
    """
    Implementation of the `/v1/garage` endpoints.
    Access (MDB token and the user datasets feature flag) is checked by GarageAccessMiddleware before any of these
    run. The endpoints themselves are not implemented yet.
    """

    def get_user_datasets(self, limit: int, offset: int) -> List[UserDataset]:
        raise _not_implemented()

    def create_user_dataset(
        self, create_user_dataset_request: CreateUserDatasetRequest
    ) -> CreateUserDatasetResponse:
        raise _not_implemented()

    def get_user_dataset(self, id: str) -> UserDataset:
        raise _not_implemented()

    def delete_user_dataset(self, id: str) -> None:
        raise _not_implemented()
