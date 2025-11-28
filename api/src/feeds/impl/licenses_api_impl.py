from typing import List, Optional

from feeds_gen.apis.licenses_api_base import BaseLicensesApi
from feeds_gen.models.license_with_rules import LicenseWithRules
from feeds_gen.models.license_base import LicenseBase
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import License as LicenseOrm
from feeds.impl.error_handling import raise_http_error
from shared.db_models.license_with_rules_impl import LicenseWithRulesImpl
from shared.db_models.license_base_impl import LicenseBaseImpl


class LicensesApiImpl(BaseLicensesApi):
    """
    Implementation for the Licenses API.
    """

    @with_db_session
    def get_license(self, id: str, db_session) -> LicenseWithRules:
        """Return the license with the provided id."""
        try:
            lic: Optional[LicenseOrm] = db_session.query(LicenseOrm).filter(LicenseOrm.id == id).one_or_none()
            if not lic:
                raise_http_error(404, f"License '{id}' not found")

            return LicenseWithRulesImpl.from_orm(lic)
        except Exception as e:
            # Use raise_http_error to convert into an HTTPException with proper logging
            raise_http_error(500, f"Error retrieving license: {e}")

    @with_db_session
    def get_licenses(self, limit: int, offset: int, db_session) -> List[LicenseBase]:
        """Return a list of licenses (paginated)."""
        try:
            query = db_session.query(LicenseOrm).order_by(LicenseOrm.id)
            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)
            results = query.all()

            return [LicenseBaseImpl.from_orm(lic) for lic in results]
        except Exception as e:
            raise_http_error(500, f"Error retrieving licenses: {e}")
