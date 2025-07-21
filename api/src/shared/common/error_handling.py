from typing import Final

invalid_date_message: Final[
    str
] = "Invalid date format for '{}'. Expected ISO 8601 format, example: '2021-01-01T00:00:00Z'"
invalid_bounding_coordinates: Final[str] = "Invalid bounding coordinates {} {}"
invalid_bounding_method: Final[str] = "Invalid bounding_filter_method {}"
feed_not_found: Final[str] = "Feed '{}' not found"
gtfs_feed_not_found: Final[str] = "GTFS feed '{}' not found"
gtfs_rt_feed_not_found: Final[str] = "GTFS realtime Feed '{}' not found"
gbfs_feed_not_found: Final[str] = "GBFS feed '{}' not found"
dataset_not_found: Final[str] = "Dataset '{}' not found"


class InternalHTTPException(Exception):
    """
    This class is used instead of the HTTPException because we don't want to depend on fastapi and have to deploy it.
    At one point this exception needs to be caught and converted to a fastapi HTTPException,
    """

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Status Code: {status_code}, Detail: {detail}")


def raise_internal_http_error(status_code: int, error: str):
    """Raise a InternalHTTPException.
    :param status_code: The status code of the error.
    :param error: The error message to be raised.
    example of output:
    {
        "detail": "Invalid date format for 'field_name'. Expected ISO 8601 format, example: '2021-01-01T00:00:00Z'"
    }
    """
    raise InternalHTTPException(
        status_code=status_code,
        detail=error,
    )


def raise_internal_http_validation_error(error: str):
    """Raise a InternalHTTPException with status code 422 and the error message.
    :param error: The error message to be raised.
    example of output:
    {
        "detail": "Invalid date format for 'field_name'. Expected ISO 8601 format, example: '2021-01-01T00:00:00Z'"
    }
    """
    raise_internal_http_error(422, error)
