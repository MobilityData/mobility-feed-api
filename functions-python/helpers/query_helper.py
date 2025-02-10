from typing import Type
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.query import Query

from shared.database_gen.sqlacodegen_models import (
    Feed,
    Gtfsrealtimefeed,
    Gtfsfeed,
    Gbfsfeed,
    Location,
    Entitytype,
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


def get_operations_gtfs_feeds_query(
    db_session: Session,
    operation_status: str | None = None,
    provider: str | None = None,
    producer_url: str | None = None,
    country_code: str | None = None,
    subdivision_name: str | None = None,
    municipality: str | None = None,
    is_official: bool = False,
    dataset_latitudes: str | None = None,
    dataset_longitudes: str | None = None,
    bounding_filter_method: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> Query:
    """Build query for GTFS feeds with operations-specific filters."""
    query = db_session.query(Feed).outerjoin(Location, Feed.locations)
    
    # Build base conditions
    conditions = [Feed.data_type == "gtfsfeed"]
    
    if operation_status:
        conditions.append(Feed.operational_status == operation_status)
    
    if provider:
        conditions.append(Feed.provider.ilike(f"%{provider}%"))
    
    if producer_url:
        conditions.append(Feed.producer_url.ilike(f"%{producer_url}%"))
    
    if country_code:
        conditions.append(Location.country_code == country_code)
    
    if subdivision_name:
        conditions.append(Location.subdivision_name.ilike(f"%{subdivision_name}%"))
    
    if municipality:
        conditions.append(Location.municipality.ilike(f"%{municipality}%"))
    
    if is_official:
        conditions.append(Feed.official.is_(True))

    # Handle bounding box filtering for GTFS feeds
    if dataset_latitudes and dataset_longitudes:
        try:
            min_lat, max_lat = map(float, dataset_latitudes.split(","))
            min_lon, max_lon = map(float, dataset_longitudes.split(","))
            
            if bounding_filter_method == "completely_enclosed":
                conditions.extend([
                    Feed.latest_dataset_min_lat >= min_lat,
                    Feed.latest_dataset_max_lat <= max_lat,
                    Feed.latest_dataset_min_lon >= min_lon,
                    Feed.latest_dataset_max_lon <= max_lon,
                ])
            elif bounding_filter_method == "partially_enclosed":
                conditions.extend([
                    Feed.latest_dataset_min_lat <= max_lat,
                    Feed.latest_dataset_max_lat >= min_lat,
                    Feed.latest_dataset_min_lon <= max_lon,
                    Feed.latest_dataset_max_lon >= min_lon,
                ])
            elif bounding_filter_method == "disjoint":
                conditions.append(
                    or_(
                        Feed.latest_dataset_max_lat < min_lat,
                        Feed.latest_dataset_min_lat > max_lat,
                        Feed.latest_dataset_max_lon < min_lon,
                        Feed.latest_dataset_min_lon > max_lon,
                    )
                )
        except ValueError:
            raise ValueError("Invalid bounding box parameters. Format should be 'min,max' for both latitudes and longitudes.")

    # Apply all conditions
    query = query.filter(and_(*conditions))
    
    # Add pagination
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)
        
    return query

def get_operations_gtfs_rt_feeds_query(
    db_session: Session,
    operation_status: str | None = None,
    provider: str | None = None,
    producer_url: str | None = None,
    entity_types: str | None = None,
    country_code: str | None = None,
    subdivision_name: str | None = None,
    municipality: str | None = None,
    is_official: bool = False,
    limit: int | None = None,
    offset: int | None = None,
) -> Query:
    """Build query for GTFS-RT feeds with operations-specific filters."""
    query = db_session.query(Feed).outerjoin(Location, Feed.locations)
    
    # Build base conditions
    conditions = [Feed.data_type == "gtfsrealtimefeed"]
    
    if operation_status:
        conditions.append(Feed.operational_status == operation_status)
    
    if provider:
        conditions.append(Feed.provider.ilike(f"%{provider}%"))
    
    if producer_url:
        conditions.append(Feed.producer_url.ilike(f"%{producer_url}%"))
    
    if country_code:
        conditions.append(Location.country_code == country_code)
    
    if subdivision_name:
        conditions.append(Location.subdivision_name.ilike(f"%{subdivision_name}%"))
    
    if municipality:
        conditions.append(Location.municipality.ilike(f"%{municipality}%"))
    
    if is_official:
        conditions.append(Feed.official.is_(True))

    # Handle entity types for GTFS-RT feeds
    if entity_types:
        entity_type_list = [t.strip() for t in entity_types.split(",")]
        if entity_type_list:
            query = query.join(Entitytype, Feed.entitytypes)
            conditions.append(Entitytype.name.in_(entity_type_list))

    # Apply all conditions
    query = query.filter(and_(*conditions))
    
    # Add pagination
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)
        
    return query
