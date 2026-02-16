from contextlib import contextmanager
import itertools
import os
import threading
import uuid
from typing import Type, Callable
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, event, func, select
from sqlalchemy.orm import load_only, Query, class_mapper, Session, mapper
from shared.database_gen.sqlacodegen_models import (
    Base,
    Feed,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsrealtimefeed,
    Gbfsversion,
    Gbfsfeed,
    Gbfsvalidationreport,
    Osmlocationgroup,
    Validationreport,
)
from sqlalchemy.orm import sessionmaker
import logging


from shared.common.logging_utils import get_env_logging_level


def generate_unique_id() -> str:
    """
    Generates a unique ID of 36 characters
    :return: the ID
    """
    return str(uuid.uuid4())


def get_db_timestamp(db_session: Session) -> func.current_timestamp():
    """Get the current time from the database."""
    return db_session.execute(select(func.current_timestamp())).scalar()


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


# The `cascade_entities` dictionary maps SQLAlchemy models to lists of their relationship attributes
# that should have cascading delete-orphan behavior. When a parent entity (such as `Feed`, `Gbfsfeed`, etc.)
# is deleted, any related child entities listed here will also be deleted if they become orphans.
# The `set_cascade` function applies this configuration by setting the `cascade` property to "all, delete-orphan"
# and enabling `passive_deletes` for each specified relationship. This leverages the database's ON DELETE CASCADE
# constraints and ensures that related records are cleaned up automatically when a parent is removed.
cascade_entities = {
    Feed: [
        Feed.externalids,  # externalid_feed_id_fkey
        Feed.feedlocationgrouppoints,
        Feed.feedosmlocationgroups,  # feedosmlocation_feed_id_fkey
        Feed.gtfsdatasets,  # gtfsdataset_feed_id_fkey
        Feed.officialstatushistories,  # officialstatushistory_feed_id_fkey
        Feed.redirectingids,  # redirectingid_source_id_fkey
        Feed.redirectingids_,  # redirectingid_target_id_fkey
        Feed.feed_license_changes,
    ],
    Gbfsfeed: [
        Gbfsfeed.gbfsversions,  # gbfsversion_feed_id_fkey
    ],
    Gbfsvalidationreport: [
        Gbfsvalidationreport.gbfsnotices,  # gbfsnotice_validation_report_id_fkey
    ],
    Gbfsversion: [
        Gbfsversion.gbfsendpoints,  # gbfsendpoint_gbfs_version_id_fkey
        Gbfsversion.gbfsvalidationreports,  # gbfsvalidationreport_gbfs_version_id_fkey
    ],
    Osmlocationgroup: [
        Osmlocationgroup.feedlocationgrouppoints,
        Osmlocationgroup.feedosmlocationgroups,  # feedosmlocation_group_id_fkey
    ],
    Validationreport: [
        Validationreport.notices,  # notice_validation_report_id_fkey
    ],
    Gtfsdataset: [
        Gtfsdataset.gtfsfiles,
    ],
}


def set_cascade(mapper, class_):
    """
    Set cascade for relationships in Gtfsfeed.
    This allows to delete/add the relationships when their respective relation array changes.
    """
    mapper.confirm_deleted_rows = False  # Disable confirm_deleted_rows to avoid warnings in logs with delete-orphan
    if class_ in cascade_entities:
        relationship_keys = {rel.prop.key for rel in cascade_entities[class_]}
        for rel in class_.__mapper__.relationships:
            if rel.key in relationship_keys:
                rel.cascade = "all, delete-orphan"
                rel.passive_deletes = True


def mapper_configure_listener(mapper, class_):
    """
    Mapper configure listener
    """
    set_cascade(mapper, class_)
    configure_polymorphic_mappers()


# Add the mapper_configure_listener to the mapper_configured event
event.listen(mapper, "mapper_configured", mapper_configure_listener)


def refresh_materialized_view(session: "Session", view_name: str) -> bool:
    """
    Refresh Materialized view by name.
    @return: True if the view was refreshed successfully, False otherwise
    """
    try:
        session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
        return True
    except Exception as error:
        logging.error("Error raised while refreshing view: %s", error)
        return False


def with_db_session(func=None, db_url: str | None = None):
    """
    Decorator to handle the session management for the decorated function.

    This decorator ensures that a database session is properly created, committed, rolled back in case of an exception,
    and closed. It uses the @contextmanager decorator to manage the lifecycle of the session, providing a clean and
    efficient way to handle database interactions.

    How it works:
        - The decorator checks if a 'db_session' keyword argument is provided to the decorated function.
        - If 'db_session' is not provided, it creates a new Database instance and starts a new session using the
          start_db_session context manager.
        - The context manager ensures that the session is properly committed if no exceptions occur, rolled back if an
          exception occurs, and closed in either case.
        - The session is then passed to the decorated function as the 'db_session' keyword argument.
        - If 'db_session' is already provided, it simply calls the decorated function with the existing session.
        - The echoed SQL queries will be logged if the environment variable LOGGING_LEVEL is set to DEBUG.
    """
    if func is None:
        return lambda f: with_db_session(f, db_url=db_url)

    def wrapper(*args, **kwargs):
        db_session = kwargs.get("db_session")
        if db_session is None:
            db = Database(echo_sql=get_env_logging_level() == logging.getLevelName("DEBUG"), feeds_database_url=db_url)
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
            with cls.lock:
                if not isinstance(cls.instance, cls):
                    cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, echo_sql=False, feeds_database_url: str | None = None):
        """
        Initializes the database instance

        :param echo_sql: whether to echo the SQL queries or not echo_sql.
            False reduces the amount of information and noise going to the logs.
            In case of errors, the exceptions will still contain relevant information about the failing queries.

        :param feeds_database_url: The URL of the target database.
            If it's None the URL will be assigned from the environment variable FEEDS_DATABASE_URL.
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
            database_url = feeds_database_url if feeds_database_url else os.getenv("FEEDS_DATABASE_URL")
            if database_url is None:
                raise Exception("Database URL not provided.")
            self.pool_size = int(os.getenv("DB_POOL_SIZE", 10))
            self.engine = create_engine(database_url, echo=echo_sql, pool_size=self.pool_size, max_overflow=0)
            # creates a session factory
            self.Session = sessionmaker(bind=self.engine, autoflush=False)

    def is_connected(self):
        """
        Checks the connection status
        :return: True if the database is accessible False otherwise
        """
        return self.engine is not None or self.session is not None

    @contextmanager
    def start_db_session(self):
        """
        Context manager to start a database session with optional echo.

        This method manages the lifecycle of a database session, ensuring that the session is properly created,
        committed, rolled back in case of an exception, and closed. The @contextmanager decorator simplifies
        resource management by handling the setup and cleanup logic within a single function.
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
        Executes a query on the database.

        :param session: The SQLAlchemy session object used to interact with the database.
        :param model: The SQLAlchemy model to query. If not provided, the query parameter must be given.
        :param query: The SQLAlchemy ORM query to execute. If not provided, a query will be created using the model.
        :param conditions: A list of conditions (filters) to apply to the query. Each condition should be a SQLAlchemy
                        expression.
        :param attributes: A list of model's attribute names to fetch. If not provided, all attributes will be fetched.
        :param limit: An optional integer to limit the number of rows returned by the query.
        :param offset: An optional integer to offset the number of rows returned by the query.
        :param group_by: An optional function to group the query results by the return value of the function. The query
                        needs to order the return values by the key being grouped by.
        :return: None if the database is inaccessible, otherwise the results of the query.
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

    def get_query_model(self, session: Session, model: Type[Base]) -> Query:
        """
        :param model: the sqlalchemy model to query
        :return: the query model
        """
        return session.query(model)
