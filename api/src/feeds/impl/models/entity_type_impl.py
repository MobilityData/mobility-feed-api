from database_gen.sqlacodegen_models import Entitytype as EntitytypeOrm
from feeds_gen.models.Entitytype import Entitytype


class EntitytypeImpl:
    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""
        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, entitytype: EntitytypeOrm | None) -> Entitytype | None:
        if not entitytype:
            return None
        return cls(name = entitytype.name)