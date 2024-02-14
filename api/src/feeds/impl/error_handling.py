from dataclasses import dataclass, asdict

from fastapi import HTTPException


@dataclass
class HttpError:
    """A generic HTTP error."""
    message: str


@dataclass
class ValidationError(HttpError):
    """A validation error."""
    field: str
    message: str


def raise_http_errors(errors: [HttpError]):
    """Raise a HTTPException with a list of errors."""
    errors = [asdict(error) for error in errors]
    raise HTTPException(
        status_code=422,
        detail=errors,
    )
