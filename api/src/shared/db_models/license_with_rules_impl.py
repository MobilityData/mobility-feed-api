from __future__ import annotations

from typing import List, Optional

from feeds_gen.models.license_rule import LicenseRule
from feeds_gen.models.license_with_rules import LicenseWithRules
from pydantic import ConfigDict

from shared.database_gen.sqlacodegen_models import License as LicenseOrm
from shared.db_models.license_base_impl import LicenseBaseImpl


class LicenseWithRulesImpl(LicenseWithRules):
    """Pydantic model that can be hydrated directly from a License ORM row."""

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, license_orm: Optional[LicenseOrm]) -> Optional[LicenseWithRules]:
        """Convert a SQLAlchemy License row into a LicenseWithRules model."""
        if not license_orm:
            return None

        base_license = LicenseBaseImpl.from_orm(license_orm)
        rules: List[LicenseRule] = [
            LicenseRule(
                name=rule.name,
                label=rule.label,
                description=rule.description,
                type=rule.type,
            )
            for rule in getattr(license_orm, "rules", [])
        ]

        return cls(
            **base_license.model_dump(),
            license_rules=rules or [],
        )
