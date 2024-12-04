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
    result = EntityTypeImpl.to_orm(entity_type)
    assert result.name == "VP"
