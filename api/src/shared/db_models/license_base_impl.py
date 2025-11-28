from __future__ import annotations

from typing import Optional

from feeds_gen.models.license_base import LicenseBase
from pydantic import ConfigDict

from shared.database_gen.sqlacodegen_models import License as LicenseOrm


class LicenseBaseImpl(LicenseBase):
    """Pydantic model hydratable directly from a License ORM row."""

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, license_orm: Optional[LicenseOrm]) -> Optional[LicenseBase]:
        """Convert a SQLAlchemy License row into the base License model."""
        if not license_orm:
            return None

        return cls(
            id=license_orm.id,
            type=license_orm.type,
            is_spdx=license_orm.is_spdx,
            name=license_orm.name,
            url=license_orm.url,
            description=license_orm.description,
            created_at=license_orm.created_at,
            updated_at=license_orm.updated_at,
        )
