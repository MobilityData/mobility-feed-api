from typing import List

from feeds.impl.error_handling import raise_http_error
from garage_gen.apis.garage_api_base import BaseGarageApi
from garage_gen.models.upload_user_dataset_request import UploadUserDatasetRequest
from garage_gen.models.upload_user_dataset_response import UploadUserDatasetResponse
from garage_gen.models.user_dataset import UserDataset
from shared.common.error_handling import endpoint_not_implemented


class GarageApiImpl(BaseGarageApi):
    """
    Implementation of the `/v1/garage` endpoints.
    Access is checked by the `require_garage_access` dependency attached to the router in main.py before any of
    these run. The endpoints themselves are not implemented yet.
    """

    def get_user_datasets(self, limit: int, offset: int) -> List[UserDataset]:
        raise_http_error(501, endpoint_not_implemented)

    def upload_user_dataset(self, upload_user_dataset_request: UploadUserDatasetRequest) -> UploadUserDatasetResponse:
        raise_http_error(501, endpoint_not_implemented)

    def get_user_dataset(self, id: str) -> UserDataset:
        raise_http_error(501, endpoint_not_implemented)

    def delete_user_dataset(self, id: str) -> None:
        raise_http_error(501, endpoint_not_implemented)
