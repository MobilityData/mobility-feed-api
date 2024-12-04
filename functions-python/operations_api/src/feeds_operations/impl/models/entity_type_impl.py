from feeds_operations_gen.models.entity_type import EntityType
from database_gen.sqlacodegen_models import Entitytype as EntityTypeOrm


class EntityTypeImpl(EntityType):
    """Implementation of the EntityType model.
    This class converts a SQLAlchemy row DB object with the gtfs feed fields to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object.
        """

        from_attributes = True

    @classmethod
    def from_orm(cls, obj: EntityTypeOrm | None) -> EntityType | None:
        """
        Convert a SQLAlchemy row object to a Pydantic model.
        """
        if obj is None:
            return None
        return EntityType(obj.name)

    @classmethod
    def to_orm(cls, entity_type: EntityType) -> EntityTypeOrm:
        """
        Convert a Pydantic model to a SQLAlchemy row object.
        """
        return EntityTypeOrm(name=entity_type.name)
