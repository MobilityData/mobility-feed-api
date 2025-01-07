from typing import Type

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsrealtimefeed,
    Gtfsfeed,
    Gbfsfeed,
)

feed_mapping = {"gtfs_rt": Gtfsrealtimefeed, "gtfs": Gtfsfeed, "gbfs": Gbfsfeed}


def get_model(data_type: str | None) -> Type[Feed]:
    """
    Get the model based on the data type
    """
    return feed_mapping.get(data_type, Feed)


def query_feed_by_stable_id(
    session, stable_id: str, data_type: str | None
) -> Gtfsrealtimefeed | Gtfsfeed | Gbfsfeed:
    """
    Query the feed by stable id
    """
    model = get_model(data_type)
    return session.query(model).filter(model.stable_id == stable_id).first()
