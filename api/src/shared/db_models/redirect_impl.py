from sqlalchemy.orm import Session

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Redirectingid, Feed
from feeds_gen.models.redirect import Redirect


class RedirectImpl(Redirect):
    """Implementation of the `Redirect` model.
    This class converts a SQLAlchemy row DB object to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, redirect: Redirectingid | None) -> Redirect | None:
        if not redirect:
            return None
        return cls(
            target_id=redirect.target.stable_id,
            comment=redirect.redirect_comment,
        )

    @classmethod
    @with_db_session
    def to_orm_from_dict(cls, redirect_dict: dict | None, db_session: Session = None) -> Redirectingid | None:
        # Return None if no payload or missing target_id
        if not redirect_dict or redirect_dict.get("target_id") is None:
            return None
        target = db_session.query(Feed).filter_by(stable_id=redirect_dict.get("target_id")).first()
        if not target:
            return None
        return Redirectingid(
            target_id=target.id,
            target=target,
            redirect_comment=redirect_dict.get("comment"),
        )
