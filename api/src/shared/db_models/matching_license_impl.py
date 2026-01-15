from __future__ import annotations

from typing import Optional

from feeds_gen.models.matching_license import MatchingLicense as ApiMatchingLicense
from shared.common.license_utils import MatchingLicense as DomainMatchingLicense


class MatchingLicenseImpl(ApiMatchingLicense):
    """Adapter between the internal MatchingLicense representation and the OpenAPI model.

    This class converts the internal/shared ``MatchingLicense`` object (used by
    ``shared.common.license_utils``) into the corresponding OpenAPI-generated
    ``feeds_gen.models.matching_license.MatchingLicense`` model.
    """

    @classmethod
    def from_domain(
        cls,
        matching_license: Optional[DomainMatchingLicense],
    ) -> Optional[ApiMatchingLicense]:
        """Convert a domain ``MatchingLicense`` into the OpenAPI model.

        Returns ``None`` if ``matching_license`` is ``None``.
        """
        if matching_license is None:
            return None

        return cls(
            license_id=matching_license.license_id,
            license_url=matching_license.license_url,
            normalized_url=matching_license.normalized_url,
            match_type=matching_license.match_type,
            confidence=matching_license.confidence,
            spdx_id=matching_license.spdx_id,
            matched_name=matching_license.matched_name,
            matched_catalog_url=matching_license.matched_catalog_url,
            matched_source=matching_license.matched_source,
            regional_id=matching_license.regional_id,
            notes=matching_license.notes,
        )
