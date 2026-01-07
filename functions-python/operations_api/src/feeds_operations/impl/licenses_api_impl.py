#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
from typing import List, Optional

from fastapi import HTTPException
from pydantic import StrictStr
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from feeds_gen.apis.licenses_api_base import BaseLicensesApi
from feeds_gen.models.license_base import LicenseBase
from feeds_gen.models.license_with_rules import LicenseWithRules
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import License as OrmLicense
from shared.db_models.license_base_impl import LicenseBaseImpl
from shared.db_models.license_with_rules_impl import LicenseWithRulesImpl


class LicensesApiImpl(BaseLicensesApi):
    """Implementation of the Licenses API.

    This class provides concrete implementations for the generated
    `BaseLicensesApi` methods, mirroring the style used in
    `OperationsApiImpl` and relying on the shared SQLAlchemy models.
    """

    @with_db_session
    def handle_get_license(
        self,
        id: StrictStr,
        db_session: Session = None,
    ) -> LicenseWithRules:
        """Get the specified license from the Mobility Database.

        Raises 404 if the license is not found.
        """
        logging.info("Fetching license with id: %s", id)

        license_orm: Optional[OrmLicense] = db_session.get(OrmLicense, id)
        if license_orm is None:
            logging.warning("License not found: %s", id)
            raise HTTPException(status_code=404, detail="License not found")

        # Build Pydantic model from ORM object attributes
        return LicenseWithRulesImpl.from_orm(license_orm)

    async def get_license(
        self,
        id: StrictStr,
    ) -> LicenseWithRules:
        """Get the specified license from the Mobility Database.

        Raises 404 if the license is not found.
        """
        return self.handle_get_license(id)

    @with_db_session
    def handle_get_licenses(
        self,
        offset: str = "0",
        limit: str = "100",
        search_query: Optional[StrictStr] = None,
        is_spdx: Optional[bool] = None,
        db_session: Session = None,
    ) -> List[LicenseBase]:
        """Get the list of licenses from the Mobility Database.

        Supports pagination via `limit` and `offset`, optional
        case-insensitive text search on license name / id, and
        optional filtering by SPDX status.
        """

        logging.info(
            "Fetching licenses with limit=%s offset=%s search_query=%s is_spdx=%s",
            limit,
            offset,
            search_query,
            is_spdx,
        )

        limit_int = int(limit)
        offset_int = int(offset)
        query = db_session.query(OrmLicense)

        # Text search by name or id
        if search_query and search_query.strip():
            pattern = f"%{search_query.strip()}%"
            try:
                conditions = [
                    func.lower(OrmLicense.name).like(func.lower(pattern)),
                    func.lower(OrmLicense.id).like(func.lower(pattern)),
                ]
                query = query.filter(or_(*conditions))
            except Exception as exc:  # defensive; shouldn't normally trigger
                logging.error("Failed applying search filter: %s", exc)

        # Optional SPDX filter
        if is_spdx is not None:
            query = query.filter(OrmLicense.is_spdx == is_spdx)

        query = query.order_by(OrmLicense.id).offset(offset_int).limit(limit_int)
        items: List[OrmLicense] = query.all()

        logging.info("Fetched %d licenses", len(items))

        return [LicenseBaseImpl.from_orm(item) for item in items]

    async def get_licenses(
        self,
        offset: str = "0",
        limit: str = "100",
        search_query: Optional[StrictStr] = None,
        is_spdx: Optional[bool] = None,
    ) -> List[LicenseBase]:
        """Get the list of licenses from the Mobility Database.

        Supports pagination via `limit` and `offset`, optional
        case-insensitive text search on license name / id, and
        optional filtering by SPDX status.
        """
        return self.handle_get_licenses(offset, limit, search_query, is_spdx)
