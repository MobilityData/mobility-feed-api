import logging
from datetime import datetime
from typing import Type

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.query import Query

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsrealtimefeed,
    Gtfsfeed,
    Gbfsfeed,
    Gtfsdataset,
    Validationreport,
)

feed_mapping = {"gtfs_rt": Gtfsrealtimefeed, "gtfs": Gtfsfeed, "gbfs": Gbfsfeed}


def get_model(data_type: str | None) -> Type[Feed]:
    """
    Get the model based on the data type
    """
    return feed_mapping.get(data_type, Feed)


def query_feed_by_stable_id(
    session: Session, stable_id: str, data_type: str | None
) -> Gtfsrealtimefeed | Gtfsfeed | Gbfsfeed:
    """
    Query the feed by stable id
    """
    model = get_model(data_type)
    return session.query(model).filter(model.stable_id == stable_id).first()


def get_eager_loading_options(model: Type[Feed]):
    """
    Get the appropriate eager loading options based on the model type.

    Args:
        model: The SQLAlchemy model class

    Returns:
        List of joinedload options for the query
    """
    if model == Gtfsrealtimefeed:
        logging.info("Adding GTFS-RT specific eager loading")
        return [
            joinedload(Gtfsrealtimefeed.locations),
            joinedload(Gtfsrealtimefeed.entitytypes),
            joinedload(Gtfsrealtimefeed.gtfs_feeds),
            joinedload(Gtfsrealtimefeed.externalids),
            joinedload(Gtfsrealtimefeed.redirectingids),
        ]
    elif model == Gtfsfeed:
        logging.info("Adding GTFS specific eager loading")
        return [
            joinedload(Gtfsfeed.locations),
            joinedload(Gtfsfeed.externalids),
            joinedload(Gtfsfeed.redirectingids),
        ]
    else:
        logging.info("Adding base Feed eager loading")
        return [
            joinedload(Feed.locations),
            joinedload(Feed.externalids),
            joinedload(Feed.redirectingids),
            joinedload(Gtfsrealtimefeed.entitytypes),
            joinedload(Gtfsrealtimefeed.gtfs_feeds),
        ]


def get_feeds_query(
    db_session: Session,
    operation_status: str | None = None,
    data_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> Query:
    """
    Build a consolidated query for feeds with filtering options.

    Args:
        db_session: SQLAlchemy session
        operation_status: Optional filter for operational status (wip or published)
        data_type: Optional filter for feed type (gtfs or gtfs_rt)
        limit: Maximum number of items to return
        offset: Number of items to skip

    Returns:
        Query: SQLAlchemy query object
    """
    try:
        logging.info(
            "Building query with params: data_type=%s, operation_status=%s",
            data_type,
            operation_status,
        )

        if data_type == "gtfs":
            model = Gtfsfeed
        elif data_type == "gtfs_rt":
            model = Gtfsrealtimefeed  # Force concrete model
        else:
            model = Feed

        logging.info(f"Using concrete model: {model.__name__}")

        conditions = []

        if data_type is None:
            conditions.append(model.data_type.in_(["gtfs", "gtfs_rt"]))
            logging.info("Added filter to exclude gbfs feeds")

        if operation_status:
            conditions.append(model.operational_status == operation_status)
            logging.info("Added operational_status filter: %s", operation_status)

        query = db_session.query(model)
        logging.info("Created base query with model %s", model.__name__)

        eager_loading_options = get_eager_loading_options(model)
        query = query.options(*eager_loading_options)

        if conditions:
            query = query.filter(and_(*conditions))
            logging.info("Applied conditions: %s", conditions)

        query = query.order_by(model.provider, model.stable_id)

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        logging.info("Generated SQL Query: %s", query)
        return query

    except Exception as e:
        logging.error("Error building query: %s", str(e))
        raise


def get_datasets_with_missing_reports_query(
    db_session: Session,
    filter_after: datetime | None = None,
) -> Query:
    """
    Get datasets with missing validation reports.

    Args:
        db_session: SQLAlchemy session
        filter_after: Optional date to filter datasets

    Returns:
        A SQLAlchemy query object for datasets with missing validation reports order by feed and dataset stable id.
    """
    query = (
        db_session.query(
            Gtfsfeed.stable_id,
            Gtfsdataset.stable_id,
        )
        .select_from(Gtfsfeed)
        .join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)
        .outerjoin(Validationreport, Gtfsdataset.validation_reports)
        .filter(Validationreport.id.is_(None))
    )
    if filter_after:
        query = query.filter(Gtfsdataset.downloaded_at >= filter_after)
    query = query.distinct(Gtfsfeed.stable_id, Gtfsdataset.stable_id).order_by(
        Gtfsdataset.stable_id, Gtfsfeed.stable_id
    )
    return query


# def get_feeds_ids_with_missing_bounding_boxes_query(
#     db_session: Session,
# ) -> Query:
#     """
#     Get GTFS feeds ids where the dataset is missing a bounding box.

#     Args:
#         db_session: SQLAlchemy session

#     Returns:
#         A SQLAlchemy query object for GTFS feeds with datasets missing bounding boxes
#         ordered by dataset and feed stable id.
#     """
#     query = (
#         db_session.query(
#             Gtfsfeed.stable_id,
#             Gtfsdataset.stable_id,
#         )
#         .select_from(Gtfsfeed)
#         .join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)
#         .filter(Gtfsdataset.bounding_box.is_(None))
#         .filter(
#             ~Gtfsfeed.feedlocationgrouppoints.any()
#         )  # Only feeds with no location group points
#         .distinct(Gtfsfeed.stable_id, Gtfsdataset.stable_id)
#         .order_by(Gtfsdataset.stable_id, Gtfsfeed.stable_id)
#     )

#     return query


def get_feeds_with_missing_bounding_boxes_query(
    db_session: Session,
) -> Query:
    """
    Get GTFS feeds with datasets missing bounding boxes.

    Args:
        db_session: SQLAlchemy session

    Returns:
        A SQLAlchemy query object for GTFS feeds with datasets missing bounding boxes
        ordered by feed stable id.
    """
    query = (
        db_session.query(Gtfsfeed)
        .join(Gtfsdataset, Gtfsdataset.feed_id == Gtfsfeed.id)
        .filter(Gtfsdataset.bounding_box.is_(None))
        .filter(~Gtfsfeed.feedlocationgrouppoints.any())
        .distinct(Gtfsfeed.stable_id, Gtfsdataset.stable_id)
        .order_by(Gtfsdataset.stable_id, Gtfsfeed.stable_id)
    )
    return query
