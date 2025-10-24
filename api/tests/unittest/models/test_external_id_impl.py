import unittest

from shared.database_gen.sqlacodegen_models import Externalid
from shared.db_models.external_id_impl import ExternalIdImpl

external_id_orm = Externalid(
    feed_id="feed_id",
    associated_id="associated_id",
    source="source",
)

expected_external_id = ExternalIdImpl(
    external_id="associated_id",
    source="source",
)


class TestExternalIdImpl(unittest.TestCase):
    """Test the `ExternalIdImpl` model."""

    def test_external_id_impl(self):
        assert ExternalIdImpl.from_orm(external_id_orm) == expected_external_id

    def test_external_id_impl_none_empty(self):
        """Test the `from_orm` method with empty and none value fields."""
        external_id_orm_empty = Externalid(
            feed_id="feed_id",
            associated_id="",
            source=None,
        )

        expected_external_id_empty = ExternalIdImpl(
            external_id="",
            source=None,
        )

        assert ExternalIdImpl.from_orm(external_id_orm_empty) == expected_external_id_empty

    def test_external_id_impl_none(self):
        """Test the `from_orm` method with None."""
        assert ExternalIdImpl.from_orm(None) is None
