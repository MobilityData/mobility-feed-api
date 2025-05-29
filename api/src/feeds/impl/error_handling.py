import logging

from fastapi import HTTPException

from shared.common.error_handling import InternalHTTPException


def convert_exception(input_exception: InternalHTTPException) -> HTTPException:
    """Convert an InternalHTTPException to an HTTPException.
    HTTPException is dependent on fastapi, and we don't necessarily want to deploy it with python functions.
    That's why InternalHTTPException (a class that we deploy) is thrown instead of HTTPException.
    Since InternalHTTPException is internal, it needs to be converted before being sent up.
    """
    return HTTPException(status_code=input_exception.status_code, detail=input_exception.detail)


def raise_http_error(status_code: int, error: str):
    """Raise a HTTPException.
    :param status_code: The status code of the error.
    :param error: The error message to be raised.
    example of output:
    {
        "detail": "Invalid date format for 'field_name'. Expected ISO 8601 format, example: '2021-01-01T00:00:00Z'"
    }
    """
    exception = HTTPException(
        status_code=status_code,
        detail=error,
    )
    logging.error(exception)
    raise exception


def raise_http_validation_error(error: str):
    """Raise a HTTPException with status code 422 and the error message.
    :param error: The error message to be raised.
    example of output:
    {
        "detail": "Invalid date format for 'field_name'. Expected ISO 8601 format, example: '2021-01-01T00:00:00Z'"
    }
    """
    raise_http_error(422, error)
