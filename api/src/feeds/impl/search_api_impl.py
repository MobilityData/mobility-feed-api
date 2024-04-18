from sqlalchemy import func, select
from sqlalchemy.orm import Query

from database.database import Database
from database_gen.sqlacodegen_models import t_feedsearch
from feeds.impl.models.search_feeds200_response_results_inner_impl import SearchFeeds200ResponseResultsInnerImpl
from feeds_gen.apis.search_api_base import BaseSearchApi
from feeds_gen.models.search_feeds200_response import SearchFeeds200Response

feed_search_columns = [column for column in t_feedsearch.columns if column.name != "document"]


class SearchApiImpl(BaseSearchApi):
    """
    This class represents the implementation of the `/search` endpoints.
    """

    @staticmethod
    def get_parsed_search_tsquery(search_query: str) -> str:
        """
        Parse the search query to be used in the database query.
        The resulting query will be in the form of `search_query:*` if the search query is not empty.
        Spaces are trimmed from the search query.
        """
        parsed_query = f"{search_query.strip()}:*" if search_query and len(search_query.strip()) > 0 else ""
        return func.plainto_tsquery("english", parsed_query)

    @staticmethod
    def add_search_query_filters(query, search_query, data_type, feed_id, status) -> Query:
        """
        Add filters to the search query.
        Filter values are trimmed and converted to lowercase.
        """
        if feed_id:
            query = query.where(t_feedsearch.c.feed_stable_id == feed_id.strip().lower())
        if data_type:
            query = query.where(t_feedsearch.c.data_type == data_type.strip().lower())
        if status:
            query = query.where(t_feedsearch.c.status == status.strip().lower())
        if search_query and len(search_query.strip()) > 0:
            query = query.filter(
                t_feedsearch.c.document.op("@@")(SearchApiImpl.get_parsed_search_tsquery(search_query))
            )
        return query

    @staticmethod
    def create_count_search_query(status: str, feed_id: str, data_type: str, search_query: str) -> Query:
        """
        Create a search query for the database.
        """
        query = select(func.count(t_feedsearch.c.feed_id))
        return SearchApiImpl.add_search_query_filters(query, search_query, data_type, feed_id, status)

    @staticmethod
    def create_search_query(status: str, feed_id: str, data_type: str, search_query: str) -> Query:
        """
        Create a search query for the database.
        """
        # TODO: Add sorting and keep the rank sorting by default
        rank_expression = func.ts_rank(
            t_feedsearch.c.document, SearchApiImpl.get_parsed_search_tsquery(search_query)
        ).label("rank")
        query = select(
            rank_expression,
            *feed_search_columns,
        )
        query = SearchApiImpl.add_search_query_filters(query, search_query, data_type, feed_id, status)
        return query.order_by(rank_expression.desc())

    def search_feeds(
        self,
        limit: int,
        offset: int,
        status: str,
        feed_id: str,
        data_type: str,
        search_query: str,
    ) -> SearchFeeds200Response:
        """Search feeds using full-text search on feed, location and provider&#39;s information."""
        query = self.create_search_query(status, feed_id, data_type, search_query)
        feed_rows = Database().select(
            query=query,
            limit=limit,
            offset=offset,
        )
        feed_total_count = Database().select(
            query=self.create_count_search_query(status, feed_id, data_type, search_query),
        )
        if feed_rows is None or feed_total_count is None:
            return SearchFeeds200Response(
                results=[],
                total=0,
            )

        results = list(map(lambda feed: SearchFeeds200ResponseResultsInnerImpl.from_orm(feed), feed_rows))
        return SearchFeeds200Response(
            results=results,
            total=feed_total_count[0][0] if feed_total_count and feed_total_count[0] else 0,
        )
