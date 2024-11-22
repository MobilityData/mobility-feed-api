from contextlib import contextmanager
import itertools
import os
import threading
import uuid
from typing import Type, Callable
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import load_only, Query, class_mapper, Session
from database_gen.sqlacodegen_models import Base, Feed, Gtfsfeed, Gtfsrealtimefeed, Gbfsfeed
from sqlalchemy.orm import sessionmaker
import logging
from typing import Final

lock = threading.Lock()


def generate_unique_id() -> str:
    """
    Generates a unique ID of 36 characters
    :return: the ID
    """
    return str(uuid.uuid4())


def configure_polymorphic_mappers():
    """
    Configure the polymorphic mappers allowing polymorphic values on relationships.
    """
    feed_mapper = class_mapper(Feed)
    # Configure the polymorphic mapper using date_type as discriminator for the Feed class
    feed_mapper.polymorphic_on = Feed.data_type
    feed_mapper.polymorphic_identity = Feed.__tablename__.lower()

    gtfsfeed_mapper = class_mapper(Gtfsfeed)
    gtfsfeed_mapper.inherits = feed_mapper
    gtfsfeed_mapper.polymorphic_identity = Gtfsfeed.__tablename__.lower()

    gtfsrealtimefeed_mapper = class_mapper(Gtfsrealtimefeed)
    gtfsrealtimefeed_mapper.inherits = feed_mapper
    gtfsrealtimefeed_mapper.polymorphic_identity = Gtfsrealtimefeed.__tablename__.lower()

    gbfsfeed_mapper = class_mapper(Gbfsfeed)
    gbfsfeed_mapper.inherits = feed_mapper
    gbfsfeed_mapper.polymorphic_identity = Gbfsfeed.__tablename__.lower()


def with_db_session(func):
    """
    Decorator to handle the session management
    :param func: the function to decorate
    :return: the decorated function
    """

    def wrapper(*args, **kwargs):
        db_session = kwargs.get("db_session")
        if db_session is None:
            db = Database()
            with db.start_db_session() as session:
                kwargs["db_session"] = session
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper


class Database:
    """
    This class represents a database instance
    """

    instance = None
    initialized = False
    lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.instance, cls):
            with lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, echo_sql=False):
        """
        Initializes the database instance
        :param echo_sql: whether to echo the SQL queries or not
        echo_sql set to False reduces the amount of information and noise going to the logs.
        In case of errors, the exceptions will still contain relevant information about the failing queries.
        """

        # This init function is called each time we call Database(), but in the case of a singleton, we only want to
        # initialize once, so we need to use a lock and a flag
        with Database.lock:
            if Database.initialized:
                return

            Database.initialized = True
            load_dotenv()
            self.logger = logging.getLogger(__name__)
            self.connection_attempts = 0
            database_url = os.getenv("FEEDS_DATABASE_URL")
            if database_url is None:
                raise Exception("Database URL not provided.")
            self.engine = create_engine(database_url, echo=echo_sql, pool_size=10, max_overflow=0)
            self.Session = sessionmaker(bind=self.engine, autoflush=False)

    def is_connected(self):
        """
        Checks the connection status
        :return: True if the database is accessible False otherwise
        """
        return self.engine is not None or self.session is not None

    @contextmanager
    def start_db_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # def close_session(self):
    #     """
    #     Closes a session
    #     :return: True if the session was started, False otherwise
    #     """
    #     try:
    #         should_close = self.should_close_db_session()
    #         if should_close and self.session is not None and self.session.is_active:
    #             self.session.close()
    #             self.logger.info("Database session closed.")
    #     except Exception as e:
    #         self.logger.error(f"Session closing failed with exception: \n {e}")
    #     return self.is_connected()

    def select(
        self,
        session: "Session",
        model: Type[Base] = None,
        query: Query = None,
        conditions: list = None,
        attributes: list = None,
        limit: int = None,
        offset: int = None,
        group_by: Callable = None,
    ):
        """
        Executes a query on the database
        :param model: the sqlalchemy model to query
        :param query: the sqlalchemy ORM query execute
        :param conditions: list of conditions (filters for the query)
        :param attributes: list of model's attribute names that you want to fetch. If not given, fetches all attributes.
        :param update_session: option to update session before running the query (defaults to True)
        :param limit: the optional number of rows to limit the query with
        :param offset: the optional number of rows to offset the query with
        :param group_by: an optional function, when given query results will group by return value of group_by function.
        Query needs to order the return values by the key being grouped by
        :return: None if database is inaccessible, the results of the query otherwise
        """
        try:
            if query is None:
                query = session.query(model)
            if conditions:
                for condition in conditions:
                    query = query.filter(condition)
            if attributes is not None:
                query = query.options(load_only(*attributes))
            if limit is not None:
                query = query.limit(limit)
            if offset is not None:
                query = query.offset(offset)
            results = session.execute(query).all()
            if group_by:
                return [list(group) for _, group in itertools.groupby(results, group_by)]
            return results
        except Exception as e:
            self.logger.error(f"SELECT query failed with exception: \n{e}")
            return None

    # def get_session(self) -> Session:
    #     """
    #     :return: the current session
    #     """
    #     return self.session

    def get_query_model(self, session: Session, model: Type[Base]) -> Query:
        """
        :param model: the sqlalchemy model to query
        :return: the query model
        """
        return session.query(model)
