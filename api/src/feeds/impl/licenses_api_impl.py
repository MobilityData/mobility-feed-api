from typing import List, Optional

from feeds_gen.apis.licenses_api_base import BaseLicensesApi
from feeds_gen.models.license import License as LicenseModel
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import License as LicenseOrm
from feeds.impl.error_handling import raise_http_error


class LicensesApiImpl(BaseLicensesApi):
    """
    Implementation for the Licenses API.
    """

    @with_db_session
    def get_license(self, id: str, db_session) -> LicenseModel:
        """Return the license with the provided id."""
        try:
            lic: Optional[LicenseOrm] = db_session.query(LicenseOrm).filter(LicenseOrm.id == id).one_or_none()
            if not lic:
                raise_http_error(404, f"License '{id}' not found")

            # Map ORM to generated model and include license_rules (list of rule names)
            lic_dict = {
                "id": lic.id,
                "type": lic.type,
                "is_spdx": lic.is_spdx,
                "name": lic.name,
                "url": lic.url,
                "description": lic.description,
                "license_rules": [r.name for r in getattr(lic, "rules", [])],
                "created_at": lic.created_at,
                "updated_at": lic.updated_at,
            }
            return LicenseModel.from_dict(lic_dict)
        except Exception as e:
            # Use raise_http_error to convert into an HTTPException with proper logging
            raise_http_error(500, f"Error retrieving license: {e}")

    @with_db_session
    def get_licenses(self, limit: int, offset: int, db_session) -> List[LicenseModel]:
        """Return a list of licenses (paginated)."""
        try:
            query = db_session.query(LicenseOrm).order_by(LicenseOrm.id)
            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)
            results = query.all()

            licenses: List[LicenseModel] = []
            for lic in results:
                lic_dict = {
                    "id": lic.id,
                    "type": lic.type,
                    "is_spdx": lic.is_spdx,
                    "name": lic.name,
                    "url": lic.url,
                    "description": lic.description,
                    "license_rules": [r.name for r in getattr(lic, "rules", [])],
                    "created_at": lic.created_at,
                    "updated_at": lic.updated_at,
                }
                licenses.append(LicenseModel.from_dict(lic_dict))

            return licenses
        except Exception as e:
            raise_http_error(500, f"Error retrieving licenses: {e}")
