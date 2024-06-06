from database_gen.sqlacodegen_models import Redirectingid
from feeds_gen.models.redirect import Redirect


class RedirectImpl(Redirect):
    """Implementation of the `Redirect` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, redirect: Redirectingid | None) -> Redirect | None:
        if not redirect:
            return None
        return cls(
            target_id=redirect.target_id,
            comment=redirect.redirect_comment,
        )
