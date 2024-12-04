from unittest.mock import Mock

from database_gen.sqlacodegen_models import Entitytype
from feeds_operations.impl.models.entity_type_impl import EntityTypeImpl
from feeds_operations_gen.models.entity_type import EntityType


def test_from_orm():
    entity_type = Entitytype(name="VP")
    result = EntityTypeImpl.from_orm(entity_type)
    assert result.name == "VP"


def test_from_orm_none():
    result = EntityTypeImpl.from_orm(None)
    assert result is None


def test_to_orm():
    entity_type = EntityType("vp")
    session = Mock()
    mock_query = Mock()
    resulting_entity = Mock()
    mock_query.filter.return_value.first.return_value = resulting_entity
    session.query.return_value = mock_query
    result = EntityTypeImpl.to_orm(entity_type, session)
    assert result == resulting_entity
