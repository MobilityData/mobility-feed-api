from typing import Optional
import json
from sqlalchemy import func, select, or_
from shared.database.database import Database
from shared.database.sql_functions.unaccent import unaccent
from shared.database_gen.sqlacodegen_models import t_feedsearch

feed_search_columns = [col for col in t_feedsearch.columns if col.name != "document"]


def get_parsed_search_tsquery(search_query: str):
    parsed_query = f"{search_query.strip()}:*" if search_query and len(search_query.strip()) > 0 else ""
    return func.plainto_tsquery("english", unaccent(parsed_query))


def search_feeds_tool(
    search_query: str,
    data_type: Optional[str] = "gtfs",
    is_official: Optional[bool] = None,
    limit: Optional[int] = 30,
) -> str:
    """
    Search the Mobility Database for GTFS/GBFS/GTFS-RT feeds.

    Returns rich location and metadata context so the AI can disambiguate between results
    (e.g., Montreal Quebec vs Montréal-du-Gers France).

    Args:
        search_query: Free-text search (e.g., "Montreal", "Japan", "STM")
        data_type: One of: gtfs, gtfs_rt, gbfs. Default: gtfs
        is_official: Filter for official feeds only
        limit: Max results to return. Default: 30

    Returns:
        JSON string with query, total_matches, and results array with feed metadata
    """
    db = Database()
    with db.start_db_session() as session:
        ts_query = get_parsed_search_tsquery(search_query)
        rank_expr = func.ts_rank(t_feedsearch.c.document, ts_query).label("rank")

        query = select(rank_expr, *feed_search_columns)

        # Always filter to published feeds only (public MCP — no auth context)
        query = query.filter(t_feedsearch.c.operational_status == "published")

        if data_type:
            data_types = [dt.strip().lower() for dt in data_type.split(",")]
            query = query.where(t_feedsearch.c.data_type.in_(data_types))

        if is_official is not None:
            if is_official:
                query = query.where(t_feedsearch.c.official.is_(True))
            else:
                query = query.where(
                    or_(t_feedsearch.c.official.is_(False), t_feedsearch.c.official.is_(None))
                )

        if search_query and len(search_query.strip()) > 0:
            query = query.filter(t_feedsearch.c.document.op("@@")(ts_query))

        if search_query and len(search_query.strip()) > 0:
            query = query.order_by(t_feedsearch.c.created_at.desc(), rank_expr.desc())
        else:
            query = query.order_by(t_feedsearch.c.created_at.desc())

        # Build parallel count query with same filters
        count_query = select(func.count(t_feedsearch.c.feed_id))
        count_query = count_query.filter(t_feedsearch.c.operational_status == "published")
        if data_type:
            count_query = count_query.where(t_feedsearch.c.data_type.in_(data_types))
        if is_official is not None:
            if is_official:
                count_query = count_query.where(t_feedsearch.c.official.is_(True))
            else:
                count_query = count_query.where(
                    or_(t_feedsearch.c.official.is_(False), t_feedsearch.c.official.is_(None))
                )
        if search_query and len(search_query.strip()) > 0:
            count_query = count_query.filter(t_feedsearch.c.document.op("@@")(ts_query))

        rows = session.execute(query.limit(limit)).fetchall()
        total_count_result = session.execute(count_query).fetchone()
        total_count = total_count_result[0] if total_count_result else 0

    results = []
    for row in rows:
        row_dict = dict(row._mapping)
        result = {
            "feed_id": row_dict.get("feed_stable_id"),
            "provider": row_dict.get("provider"),
            "feed_name": row_dict.get("feed_name"),
            "data_type": row_dict.get("data_type"),
            "status": row_dict.get("status"),
            "is_official": row_dict.get("official"),
            "locations": row_dict.get("locations") or [],
            "latest_dataset": {
                "id": row_dict.get("latest_dataset_id"),
                "hosted_url": row_dict.get("latest_dataset_hosted_url"),
                "downloaded_at": str(row_dict.get("latest_dataset_downloaded_at"))
                if row_dict.get("latest_dataset_downloaded_at")
                else None,
                "service_date_range_start": str(row_dict.get("latest_dataset_service_date_range_start"))
                if row_dict.get("latest_dataset_service_date_range_start")
                else None,
                "service_date_range_end": str(row_dict.get("latest_dataset_service_date_range_end"))
                if row_dict.get("latest_dataset_service_date_range_end")
                else None,
            },
            "validation_summary": {
                "total_error": row_dict.get("latest_total_error"),
                "total_warning": row_dict.get("latest_total_warning"),
                "total_info": row_dict.get("latest_total_info"),
            },
            "features": row_dict.get("latest_dataset_features") or [],
            "search_rank": float(row_dict.get("rank", 0)),
        }
        results.append(result)

    return json.dumps(
        {
            "query": search_query,
            "total_matches": total_count,
            "results": results,
        },
        default=str,
    )
