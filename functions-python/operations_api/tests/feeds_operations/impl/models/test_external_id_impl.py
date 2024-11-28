from database_gen.sqlacodegen_models import Externalid, Gtfsfeed
from operations_api.src.feeds_operations_gen.models.external_id import ExternalId
from operations_api.src.feeds_operations.impl.models.external_id_impl import (
    ExternalIdImpl,
)


def test_from_orm():
    external_id = Externalid(associated_id="12345", source="test_source")
    result = ExternalIdImpl.from_orm(external_id)
    assert result.external_id == "12345"
    assert result.source == "test_source"


def test_from_orm_none():
    result = ExternalIdImpl.from_orm(None)
    assert result is None


def test_to_orm():
    external_id = ExternalId(external_id="12345", source="test_source")
    feed = Gtfsfeed(id=1)
    result = ExternalIdImpl.to_orm(external_id, feed)
    assert result.feed_id == 1
    assert result.associated_id == "12345"
    assert result.source == "test_source"
