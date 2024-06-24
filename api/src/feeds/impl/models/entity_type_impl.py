from enum import Enum
from typing import Optional
from database_gen.sqlacodegen_models import Entitytype as EntitytypeOrm

class EntitytypeEnum(Enum):
    sa = "sa"
    tu = "tu"
    vp = "vp"

Entitytype = str

class EntitytypeImpl(Entitytype):
    class Config:
        """Pydantic configuration.
        Enabling `from_orm` method to create a model instance from a SQLAlchemy row object."""
        from_attributes = True
        orm_mode = True

    @classmethod
    def from_orm(cls, entitytype: Optional[EntitytypeOrm]) -> Optional[Entitytype]:
        if not entitytype:
            return None
        
        try:
            valid_name = EntitytypeEnum(entitytype.name).value
        except ValueError:
            raise ValueError(f"Unknown name: {entitytype.name}")
        
        return valid_name